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
const SEEK = Number(arg('seek', 0))          // 0..1 through the recording
const SPEED = Number(arg('speed', 12))
const PORT = Number(arg('port', 8081))
const DEVICE = arg('device', 'plughw:0,0')
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
  cursor: 0, n: N, t0: rec.t0, speed: SPEED, sound: false,
  note: rec.note || ''
}

const p = new Processor()
p.port.onmessage({ data: {
  gain: 0.22, running: true, capScale: 2.13, mix: [0.45, 1, 1], vco: 0.35
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
  aplay = spawn('aplay', [
    '-D', DEVICE, '-f', 'S16_LE', '-r', String(RATE), '-c', '2', '-t', 'raw', '-'
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
const L = new Float32Array(BLOCK)
const R = new Float32Array(BLOCK)
const outs = [[L, R]]
const pcm = Buffer.alloc(BLOCK * 4)

let cursor = Math.floor(N * Math.max(0, Math.min(0.999, SEEK)))
let nextDrive = 0
let generated = 0            // seconds of audio written
const started = Date.now()
const AHEAD = 1.5            // keep this many seconds in flight

let soundOn = false
let paused = false
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
  p.process([], outs, {})
  const gain = soundOn ? 1 : 0
  for (let s = 0; s < BLOCK; s++) {
    let l = L[s] * gain, r = R[s] * gain
    if (l > 1) l = 1; else if (l < -1) l = -1
    if (r > 1) r = 1; else if (r < -1) r = -1
    pcm.writeInt16LE((l * 32767) | 0, s * 4)
    pcm.writeInt16LE((r * 32767) | 0, s * 4 + 2)
  }
  generated += BLOCK / RATE
  return pcm
}

function pump () {
  while (!paused) {
    const elapsed = (Date.now() - started) / 1000
    if (generated > elapsed + AHEAD) break
    const b = block()
    if (aplay && !aplay.stdin.write(b)) { paused = true; return }
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

setInterval(pump, 20)
pump()

// --- state to the browser -------------------------------------------------
const clients = new Set()
setInterval(() => {
  const line = 'data: ' + JSON.stringify(state) + '\n\n'
  for (const res of clients) { try { res.write(line) } catch (e) { clients.delete(res) } }
}, 33)

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
    req.on('close', () => clients.delete(res))
    return
  }
  if (url.pathname === '/sound') {
    soundOn = url.searchParams.get('on') === '1'
    state.sound = soundOn
    res.writeHead(200, { 'Content-Type': 'application/json' })
    return res.end(JSON.stringify({ sound: soundOn }))
  }
  res.writeHead(404); res.end()
}).listen(PORT, '127.0.0.1', () => {
  console.error(`synth: ${(N / 3600).toFixed(1)} h at speed ${SPEED}, ` +
                `one pass every ${(N / 3600 / SPEED).toFixed(1)} h`)
  console.error(`synth: pcm -> aplay ${DEVICE}, state -> http://127.0.0.1:${PORT}/state`)
})
