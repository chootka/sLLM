#!/usr/bin/env node
//
// The piece's audio, outside the browser.
//
//   node exhibit/synth/synth.js [--replay FILE] [--speed N] [--port N] [--device D]
//
// Why this exists. Chromium on the Pi 4 cannot hold an audio stream: a native
// OscillatorNode, with no JavaScript anywhere in the audio path, drives the
// ALSA device into repeated XRUN and SETUP exactly as the piece does, while
// aplay writing to the same DAC is clean for five minutes. The browser takes
// the hardware directly and ignores both the ALSA default and PULSE_SERVER, so
// it cannot be moved onto a gentler path. See exhibit_object.md.
//
// This runs the same ring-processor.js against the same replay.json and writes
// raw PCM into aplay. The browser keeps the visuals and takes the synth's state
// over Server-Sent Events, so both come off one clock instead of two.
//
// No dependencies: node's own http and child_process, and aplay.

const fs = require('fs')
const http = require('http')
const path = require('path')
const { spawn } = require('child_process')

const { execFile } = require('child_process')

const arg = (name, dflt) => {
  const i = process.argv.indexOf('--' + name)
  return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : dflt
}

// Defaults are siblings, because build.sh drops this next to the recording and
// the worklet in the shipped object. The worklet is never copied -- one file,
// so the browser and the synth cannot drift into two different instruments.
const HERE = __dirname
const REPLAY = arg('replay', path.join(HERE, 'replay.json'))
const WORKLET = arg('worklet', path.join(HERE, 'ring-processor.js'))
// --wav FILE renders to a file and exits instead of playing. For testing on a
// machine with no aplay, and for auditioning a stretch without the object.
const WAV = arg('wav', null)
const WAV_SECS = Number(arg('secs', 30))
// --dry runs everything except aplay: the render loop and the state server,
// with the audio discarded. For working on the page on a machine with no ALSA.
const DRY = process.argv.includes('--dry')
// A flag with a missing or unparseable value used to reach the worklet as NaN,
// which propagates through every sample and silences the piece with no error
// anywhere. Falls back to the default and says so.
function mixArg () {
  const raw = arg('mix', '')
  if (!raw) return [0.45, 1, 1]
  const p = String(raw).split(',').map(Number)
  if (p.length !== 3 || !p.every(Number.isFinite)) {
    console.error('synth: --mix wants three numbers, e.g. 1,0.35,0.35')
    return [0.45, 1, 1]
  }
  return p.map(v => Math.max(0, Math.min(2, v)))
}

function num (name, def) {
  const v = Number(arg(name, def))
  if (Number.isFinite(v)) return v
  console.error(`synth: --${name} is not a number, using ${def}`)
  return def
}

const SEEK = Number(arg('seek', 0))          // 0..1 through the recording
const SPEED = Number(arg('speed', 12))
const PORT = Number(arg('port', 8081))
const DEVICE = arg('device', 'plughw:0,0')
const CARD = arg('card', '0')
const MIXER = arg('mixer', 'Digital')
const RATE = 48000
const BLOCK = 128

// --- the worklet, loaded as-is -------------------------------------------
// ring-processor.js is written for the AudioWorklet global scope. Give it the
// three globals it expects and it runs unmodified, which is the point: the
// object and the browser cannot drift apart into two different instruments.
let Processor = null
global.AudioWorkletProcessor = class {
  constructor () { this.port = { onmessage: null, postMessage: () => {} } }
}
global.registerProcessor = (name, cls) => { Processor = cls }
global.sampleRate = RATE
new Function(fs.readFileSync(WORKLET, 'utf8'))()

// --- the recording --------------------------------------------------------
const FREE_RUN = 0.12
const DEPTH = 0.62
const SCALE_MV = 2.0

const rec = JSON.parse(fs.readFileSync(REPLAY, 'utf8'))
const N = rec.n
const chans = rec.channels.map(ch => {
  const gate = new Uint8Array(N)
  for (const r of ch.gate_runs || []) gate.fill(1, r[0], r[1])
  const signal = new Float32Array(N)
  const src = ch.signal || []
  for (let i = 0; i < N; i++) signal[i] = src[i] || 0
  const pn = Math.ceil(N / 60)
  const period = new Float32Array(pn)
  const psrc = ch.period || []
  for (let i = 0; i < pn; i++) period[i] = psrc[i] || 0
  return { gate, signal, period }
})

const driveAt = (c, i) => chans[c].gate[i]
  ? FREE_RUN + DEPTH * Math.max(0, Math.min(1, chans[c].signal[i] / SCALE_MV + 0.5))
  : FREE_RUN

// --- state the visuals need ----------------------------------------------
const state = {
  coh: [0, 0, 0], freq: [0, 0, 0], lum: [0, 0, 0],
  addr: 0, vcoHz: 0, locked: false,
  drives: [FREE_RUN, FREE_RUN, FREE_RUN],
  gates: [0, 0, 0], period: [0, 0, 0],
  seen: [false, false, false],
  flash: [0, 0, 0],
  cursor: 0, n: N, t0: rec.t0, speed: SPEED, sound: true,
  note: rec.note || ''
}

// Declared up here, not beside the server that consumes them: block() calls
// snapshot() and block() runs from the WAV path and the first pump(), both of
// which are above the server. Left below, they are in the temporal dead zone
// and the process dies on its first sample.
const clients = new Set()
const timeline = []
let lastSnap = -1

const p = new Processor()
p.port.onmessage({ data: {
  // These override the worklet's own defaults, so they are the values that
  // actually ship -- editing the constructor alone does nothing.
  gain: num('gain', 1.0), running: true, capScale: 1.0,
  // Per-oscillator level. osc0 runs about an octave above the other two (its
  // timing resistor is half theirs) and the coupling pulls it further than
  // either, so it is the voice that rises and falls over the drone. At 0.45 it
  // sits behind them; raise it to bring that voice forward.
  //   --mix 1,0.35,0.35
  mix: mixArg(),
  vco: num('vco', 0.55),
  tri: num('tri', 1),                  // the body: capacitor ramp
  sqr: num('sqr', 1),                  // the edge: comparator square
  ghost: num('ghost', 0),              // the difference tone, as a voice
  amp: num('amp', 1.0),                // organism drives level, not just pitch
  ring: num('ring', 0)                 // real sum/difference tones off the bank
} })
p.port.postMessage = d => {
  if (d.coh) state.coh = d.coh
  if (d.freq) state.freq = d.freq
  if (d.lum) state.lum = d.lum
  if (typeof d.addr === 'number') state.addr = d.addr
  if (typeof d.vcoHz === 'number') state.vcoHz = d.vcoHz
  if (typeof d.locked === 'boolean') state.locked = d.locked
}

// --- output ---------------------------------------------------------------
let aplay = null
if (!WAV && !DRY) {
  // A large ALSA buffer is the whole point of being out here. 131072 frames
  // is 2.7 s for aplay to coast on, which is what makes this robust: with the
  // generation bound in place, feeding depends on this process's timer firing,
  // and anything shorter starves the moment that timer is late. 680 ms was not
  // enough. The cost is only latency, and nothing here is interactive.
  aplay = spawn('aplay', [
    '-D', DEVICE, '-f', 'S16_LE', '-r', String(RATE), '-c', '2', '-t', 'raw',
    '--buffer-size=32768', '--period-size=4096', '-'
  ], { stdio: ['pipe', 'ignore', 'inherit'] })
  aplay.on('exit', (code, sig) => {
    console.error('aplay exited', code, sig, '-- exiting so systemd restarts us')
    process.exit(1)
  })
}

// --- render ---------------------------------------------------------------
// Generate ahead of the clock and let aplay's buffer absorb jitter. Nothing
// here has to meet a deadline the way a browser callback does: if this process
// is late, the pipe simply drains a little, and aplay is holding a large
// buffer. That is the whole reason for moving out of the browser.
// Write in chunks, not in 128-frame blocks: 512 bytes per write is thousands
// of syscalls a second for no reason.
//
// 8 blocks is 21 ms, just over one pump tick, so in steady state this writes
// one chunk per tick and the feed is even. At 32 blocks it was 85 ms a write
// and the loop ran several in a row to catch up, so writes came in clumps --
// and the underruns arrived on a regular five-second cycle rather than at
// random, which is the signature of something bursty rather than something
// overloaded.
const CHUNK = 8
const L = new Float32Array(BLOCK)
const R = new Float32Array(BLOCK)
const outs = [[L, R]]
const pcm = Buffer.alloc(BLOCK * 4)
// A ring of buffers, not one reused buffer. write() does not copy: a queued
// write still points at the buffer it was handed. With one buffer and hundreds
// of writes in flight, every pending write sees whatever was last written into
// it -- which sounds like the audio stretching and sticking in long buzzes,
// because that is exactly what it is.
//
// 1024 chunks is 21 s, comfortably more than the queue can hold, so a buffer
// is never rewritten while a write on it is still pending. Preallocated, so
// there is no per-write allocation in the one process that must not stall.
const CHUNK_BYTES = BLOCK * 4 * CHUNK
const RING = 1024
const ring = []
for (let i = 0; i < RING; i++) ring.push(Buffer.alloc(CHUNK_BYTES))
let ringAt = 0
// process() was being called as p.process([], outs, {}) -- two fresh objects
// every 128 samples, hundreds a second, all garbage in the one process that
// must not stall. The collector runs, this stalls, aplay starves.
const NO_INPUT = []
const NO_PARAMS = {}

let cursor = Math.floor(N * Math.max(0, Math.min(0.999, SEEK)))
let nextDrive = 0
let generated = 0            // seconds of audio written
const started = Date.now()
// How far ahead of the speakers to generate.
//
// Long on purpose. With a big lead, node holds seconds of PCM in its own write
// buffer and libuv drains it into the pipe on OS events, independent of
// whether this process's timer fires on schedule. With a short one, feeding
// depends on setInterval running promptly and any event-loop stall starves
// aplay -- which is exactly what happened at 0.5 s and again at 2 s, while an
// unbounded lead was clean.
//
// It costs nothing now. The visuals stay in step because snapshots are held
// until their audio actually plays, so any lead is fine as long as it is
// stable. And SOUND OFF is not a gain change buried in the queue any more; it
// mutes at the mixer and is instant however much audio is committed.
//
// The bound exists only to stop it running away to 94 s and eating memory.
// 10 s is about 2 MB of PCM in flight.
const AHEAD = 5.0

let soundOn = false             // the object starts silent; a tap starts it
let paused = false
let written = 0                 // bytes handed to aplay, for the rate check
if (aplay) {
  aplay.stdin.on('drain', () => { paused = false; pump() })
  aplay.stdin.on('error', () => {})
}

function block () {
  const t = generated
  if (t >= nextDrive) {
    nextDrive += 0.05
    cursor += 0.05 * SPEED
    if (cursor > N - 1) { cursor = 0; state.seen = [false, false, false] }
    const i = Math.floor(cursor)
    const drives = [driveAt(0, i), driveAt(1, i), driveAt(2, i)]
    let slime = 0
    for (let c = 0; c < 3; c++) {
      slime += chans[c].signal[i]
      const g = chans[c].gate[i]
      if (g > 0.5 && !state.seen[c]) state.seen[c] = true
      if (g > 0.5 && state.gates[c] <= 0.5) state.flash[c] = Date.now()
      state.gates[c] = g
      state.period[c] = chans[c].period[(i / 60) | 0] || 0
    }
    state.drives = drives
    state.cursor = cursor
    p.port.onmessage({ data: { drives, slime } })
  }
  p.process(NO_INPUT, outs, NO_PARAMS)
  // No gain applied here on purpose. Muting is done at the mixer so it takes
  // effect immediately rather than after the queue drains, and the piece keeps
  // running whether or not anyone is listening.
  for (let s = 0; s < BLOCK; s++) {
    let l = L[s], r = R[s]
    if (l > 1) l = 1; else if (l < -1) l = -1
    if (r > 1) r = 1; else if (r < -1) r = -1
    pcm.writeInt16LE((l * 32767) | 0, s * 4)
    pcm.writeInt16LE((r * 32767) | 0, s * 4 + 2)
  }
  generated += BLOCK / RATE
  snapshot()
  return pcm
}

// Two limits, both needed. The pipe says when to stop writing, which is the
// fine pacing. The clock says how far ahead to work at all, which is what
// stops the queue running away -- aplay reads eagerly into its own buffer, so
// backpressure alone does not bound this.
// Paced by how much is still queued, not by the clock.
//
// The clock was wrong as a pacer. Date.now() and the DAC's crystal are not the
// same rate, and the DAC wins: producing 48000 samples per second of *system*
// time is slightly less than it consumes, so the buffer drained until it ran
// dry, over and over. The interval between underruns scaled with buffer size
// -- one a second at 680 ms, one every five at 2.7 s -- which is drift, not
// stalling. Nothing was ever late: there was simply less audio than the card
// wanted.
//
// writableLength is what is still waiting to reach aplay. Filling to a byte
// target means the consumer sets the rate, whatever its crystal actually does,
// and bounds memory at the same time -- which is what the clock bound was
// really for, since without any limit the queue grew a second per second until
// the state timeline overflowed and the visuals jumped ahead.
const QUEUE_BYTES = 2 * RATE * 4         // two seconds of audio in flight

function pump () {
  while (!paused) {
    if (aplay && aplay.stdin.writableLength >= QUEUE_BYTES) return
    const out = ring[ringAt]
    ringAt = (ringAt + 1) % RING
    for (let i = 0; i < CHUNK; i++) block().copy(out, i * BLOCK * 4)
    if (!aplay) {
      if (generated > (Date.now() - started) / 1000 + AHEAD) return
      continue
    }
    aplay.stdin.write(out)
    written += CHUNK_BYTES
  }
}

if (WAV) {
  // Offline render, as fast as the machine allows.
  soundOn = true
  const frames = Math.floor(WAV_SECS * RATE / BLOCK)
  const body = Buffer.alloc(frames * BLOCK * 4)
  const t0 = Date.now()
  for (let i = 0; i < frames; i++) block().copy(body, i * BLOCK * 4)
  const bytes = body.length
  const head = Buffer.alloc(44)
  head.write('RIFF', 0); head.writeUInt32LE(36 + bytes, 4); head.write('WAVE', 8)
  head.write('fmt ', 12); head.writeUInt32LE(16, 16); head.writeUInt16LE(1, 20)
  head.writeUInt16LE(2, 22); head.writeUInt32LE(RATE, 24)
  head.writeUInt32LE(RATE * 4, 28); head.writeUInt16LE(4, 32); head.writeUInt16LE(16, 34)
  head.write('data', 36); head.writeUInt32LE(bytes, 40)
  fs.writeFileSync(WAV, Buffer.concat([head, body]))
  const ms = Date.now() - t0
  console.error(`wrote ${WAV}: ${WAV_SECS}s in ${ms}ms (${(WAV_SECS * 1000 / ms).toFixed(0)}x realtime)`)
  process.exit(0)
}

// pump() is started at the bottom of the file, once the state timeline it
// writes into has actually been declared.

// --- state to the browser -------------------------------------------------
//
// The synth runs ahead of the speakers: it keeps aplay's 680 ms buffer full,
// so a sample computed now is heard about a second from now. Broadcasting
// state the moment it is computed puts the visuals that far ahead of the
// sound, which shows most on the pin-connect flashes.
//
// So each snapshot is stamped with its position in the audio and held until
// that audio has actually played.
//
// Playback position comes from bytes that have actually drained, never from
// the clock. The DAC does not run at exactly 48000 -- it was 100% fast before
// the overlay was fixed, and still measures a few percent off -- so any
// wall-clock estimate drifts against the audio without bound, and the only
// symptom is the visuals sliding away from the sound hours later. Counting
// what aplay has swallowed self-corrects against whatever rate the hardware
// actually runs at. What remains is a constant offset -- aplay's own ring plus
// the OS pipe -- which shifts A/V by a fixed amount rather than a growing one.
const ALSA_BUF = 32768 / RATE           // --buffer-size, in seconds

let playedSm = 0
let lastPlayed = 0
let lastAt = 0
const TAU = 0.4                        // smoothing, and the lag it costs back

// ALSA publishes exactly how many frames are still to be played, so the
// hardware side of the latency is a measurement rather than an assumption.
// Read a few times a second; it moves on the period boundary, not per sample.
const STATUS = `/proc/asound/card${CARD}/pcm0p/sub0/status`
let alsaDelay = ALSA_BUF               // seconds, until the first good read
let alsaSeen = false
let hwSec = 0                          // frames the card has actually played
let hwAt = 0                           // when that was read

function readAlsaDelay () {
  try {
    const txt = fs.readFileSync(STATUS, 'utf8')
    const d = /^\s*delay\s*:\s*(-?\d+)/m.exec(txt)
    if (d) {
      const v = parseInt(d[1], 10) / RATE
      // A stopped or draining device reports 0 or nonsense; keep the last good
      // value rather than yanking the visuals forward.
      if (v > 0 && v < 30) alsaDelay = v
    }
    // hw_ptr is the number of frames the DAC has actually clocked out. That is
    // the playback position outright -- no subtracting Node's queue, the OS
    // pipe or the card's buffer, and nothing left to estimate wrongly. It only
    // moves on period boundaries, so it is interpolated between reads below.
    const h = /^\s*hw_ptr\s*:\s*(\d+)/m.exec(txt)
    if (h) {
      const v = parseInt(h[1], 10) / RATE
      if (v >= hwSec) { hwSec = v; hwAt = Date.now(); alsaSeen = true }
    }
  } catch (e) { /* no status file: fall back to the byte estimate */ }
}
setInterval(readAlsaDelay, 100)
readAlsaDelay()

function playedSeconds () {
  if (!aplay) return (Date.now() - started) / 1000
  const queued = aplay.stdin.writableLength / (RATE * 4)
  // Ground truth when the card is reporting: frames actually played, plus the
  // time since that reading, since hw_ptr only advances once per period.
  // Otherwise fall back to counting backwards from what has been written.
  const raw = alsaSeen
    ? hwSec + (Date.now() - hwAt) / 1000
    : Math.max(0, written / (RATE * 4) - queued - alsaDelay)
  // The raw figure jitters by as much as the whole queue depth, because the
  // pump fills to the cap and then coasts down. Fed straight into the release
  // index that makes the field jump between states instead of moving through
  // them, so it is smoothed -- but a one-pole tracking a steadily rising value
  // sits behind it by exactly its own time constant, which is real lag. The
  // position advances at about a second per second, so adding TAU back
  // cancels that to first order. Time-based rather than per-call, so the rate
  // the emitter happens to run at cannot change the tuning.
  const now = Date.now()
  const dt = lastAt ? Math.min(1, (now - lastAt) / 1000) : 0
  lastAt = now
  if (playedSm === 0) playedSm = raw
  else playedSm += (raw - playedSm) * (1 - Math.exp(-dt / TAU))
  let p = playedSm + TAU
  // Never step backwards: rewinding the field reads far worse than being
  // slightly late.
  if (p < lastPlayed) p = lastPlayed
  lastPlayed = p
  return p
}
function snapshot () {
  if (generated - lastSnap < 0.033) return
  lastSnap = generated
  timeline.push({
    at: generated,
    coh: state.coh.slice(), freq: state.freq.slice(), lum: state.lum.slice(),
    addr: state.addr, vcoHz: state.vcoHz, locked: state.locked,
    drives: state.drives.slice(), gates: state.gates.slice(),
    period: state.period.slice(), seen: state.seen.slice(),
    flash: state.flash.slice(), cursor: state.cursor,
    n: state.n, t0: state.t0, speed: state.speed, sound: state.sound,
    note: state.note
  })
  if (timeline.length > 4000) timeline.splice(0, timeline.length - 4000)
}

let sent = 0
let skipped = 0
setInterval(() => {
  if (!clients.size || !timeline.length) { skipped++; return }
  const played = playedSeconds()
  // Start at the oldest snapshot rather than at "nothing to send". For the
  // first seconds after start, played is 0 while aplay's buffer fills, and the
  // oldest unplayed snapshot is exactly the right visual state for audio that
  // is about to be heard. Skipping instead meant silence on the stream long
  // enough for the browser's watchdog to give up and fall back.
  let pick = 0
  while (pick + 1 < timeline.length && timeline[pick + 1].at <= played) pick++
  const snap = timeline[pick]
  if (pick > 0) timeline.splice(0, pick)
  // Everything else in a snapshot describes a moment in the audio and is
  // deliberately held back until that audio plays. `sound` is not that: it is
  // the current state of a control, and sending the value captured a second
  // ago flipped the button back the instant after it was pressed.
  snap.sound = soundOn
  const line = 'data: ' + JSON.stringify(snap) + '\n\n'
  for (const res of clients) { try { res.write(line) } catch (e) { clients.delete(res) } }
  sent++
}, 33)

// Every 30 s, one line saying whether the stream is actually flowing. Lead is
// how far ahead of the speakers the synth is generating; it should sit around
// a second and stay put. A climbing lead means the timeline is filling faster
// than it drains and the visuals will fall behind the sound.
setInterval(() => {
  const played = playedSeconds()
  const wall = (Date.now() - started) / 1000
  const inflight = aplay ? (aplay.stdin.writableLength / (RATE * 4)).toFixed(2) : 'n/a'
  // Bytes actually handed to aplay per second of wall clock. 192000 is
  // realtime for 48 kHz stereo 16-bit. If this reads ~384000 then aplay really
  // is consuming at double rate and the audio is playing twice as fast; if it
  // reads 192000 while `lead` still climbs, then `generated` is being counted
  // twice somewhere and the fault is my accounting, not the device.
  const rate = wall > 0 ? Math.round(written / wall) : 0
  // played vs the oldest snapshot still held: if played sits behind
  // timeline[0].at the release loop can never advance past entry 0, and the
  // stream wedges on one snapshot forever. gen - played is the assumed
  // latency; if it exceeds the span the timeline actually holds, that is the
  // wedge.
  const oldest = timeline.length ? timeline[0].at.toFixed(2) : 'n/a'
  // Total latency actually in the pipe: what Node still holds plus what ALSA
  // says is still to be played. This is the number that decides A/V sync.
  const nodeQ = aplay ? aplay.stdin.writableLength / (RATE * 4) : 0
  const lat = (nodeQ + alsaDelay).toFixed(2)
  console.error(`synth: clients ${clients.size}, sent ${sent}/30s, idle ${skipped}, ` +
                `queue ${timeline.length}, lead ${(generated - played).toFixed(2)}s, ` +
                `inflight ${inflight}s, bytes/s ${rate} (realtime ${RATE * 4}), ` +
                `gen ${generated.toFixed(2)} played ${played.toFixed(2)} oldest ${oldest}, ` +
                `latency ${lat}s (alsa ${alsaDelay.toFixed(2)}s ${alsaSeen ? 'measured' : 'ASSUMED'})`)
  sent = 0; skipped = 0
}, 30000)

http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost')
  res.setHeader('Access-Control-Allow-Origin', '*')
  if (url.pathname === '/state') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive'
    })
    clients.add(res)
    console.error(`synth: client connected (${clients.size})`)
    req.on('close', () => {
      clients.delete(res)
      console.error(`synth: client gone (${clients.size})`)
    })
    return
  }
  if (url.pathname === '/sound') {
    soundOn = url.searchParams.get('on') === '1'
    state.sound = soundOn
    console.error('synth: sound ' + (soundOn ? 'on' : 'off'))
    // Instant, and independent of everything already committed to aplay.
    if (!WAV && !DRY) {
      execFile('amixer', ['-c', CARD, 'sset', MIXER, soundOn ? 'unmute' : 'mute'],
        err => { if (err) console.error('amixer:', err.message) })
    }
    res.writeHead(200, { 'Content-Type': 'application/json' })
    return res.end(JSON.stringify({ sound: soundOn }))
  }
  res.writeHead(404); res.end()
}).listen(PORT, '127.0.0.1', () => {
  // Start muted: the piece opens silent and the visitor starts the sound.
  // The synth still generates from the first second, so the audio a visitor
  // hears on tapping is where the recording has actually got to, not the
  // beginning. Note this puts the object's only sound behind one working
  // request -- acceptable now that the button always tries the synth first
  // and falls back to the in-page worklet, but it is the thing to check if a
  // sealed unit ever arrives silent and stays that way.
  if (!WAV && !DRY) {
    execFile('amixer', ['-c', CARD, 'sset', MIXER, 'mute'], () => {})
  }
  console.error(`synth: ${(N / 3600).toFixed(1)} h at speed ${SPEED}, ` +
                `one pass every ${(N / 3600 / SPEED).toFixed(1)} h`)
  console.error(`synth: pcm -> aplay ${DEVICE}, state -> http://127.0.0.1:${PORT}/state`)
})

setInterval(pump, 20)
pump()
