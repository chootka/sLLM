# synth.js flags

Every flag the standalone synth takes. They exist so the sound can be hunted by
ear on the object without editing code and redeploying between each try.

Run it by hand, which needs the service to let go of the DAC first:

    sudo systemctl stop drift-synth
    cd ~/drift && node synth.js --speed 12 --seek 0.02 --ghost 0.6 --amp 0.8

Ctrl-C when done, then `sudo systemctl start drift-synth` to put it back. The
service always runs the defaults; nothing typed here persists.

Values are read once at startup. A flag with a missing or unparseable value
falls back to its default and says so on stderr -- it used to reach the worklet
as `NaN` and silence the piece with no error anywhere.

## Finding your way through the recording

| flag | default | what it does |
|---|---|---|
| `--seek` | `0` | 0 to 1 through the recording. Skips the wait. |
| `--speed` | `12` | Times realtime. 12 is what ships. |

The recording is 53.2 h, one pass every 4.4 h at speed 12. Connections fall at
roughly **0.00** (29 s in), **0.20**, and **0.61**. `--seek 0.19` puts you just
before the second one.

## The bank

The three oscillators, and the landscape they make.

| flag | default | what it does |
|---|---|---|
| `--tri` | `1` | **The body.** Level of the capacitor ramp -- the sustained weight underneath. This is the whole bed at rest. |
| `--sqr` | `1` | **The edge.** Level of the comparator square -- the hard slap on top, heard mostly once contact is in. |
| `--mix` | `0.45,1,1` | Per-oscillator level. osc0 runs about an octave above the other two and the coupling pulls it further, so it is the voice that moves over the drone; at 0.45 it sits behind them. |
| `--gain` | `1.0` | Master. Raising it past this clips into the soft knee rather than distorting, but there is not much room left. |

`--tri` alone changes the bed. `--sqr` alone changes what a connection sounds
like and leaves the bed untouched.

## The other voices

| flag | default | what it does |
|---|---|---|
| `--vco` | `0.55` | The PLL: the voice that chases the oscillators, never settles, and goes raspy while hunting. |
| `--ghost` | `0` (off) | The difference tone as an actual voice -- a sine tracking the gap between the two fastest oscillators, folded up into hearing and glided rather than stepped. This is the thing that rises and falls in the distance; it belongs to no oscillator, so it can only be heard by generating it. |
| `--amp` | `1.0` | Sends the organism's rise and fall to **level** as well as pitch, per channel. Whichever electrode is being pushed hardest is the voice that comes up, so a contraction is a swell and not only a bend. At 1.0 the piece breathes over 4.7 dB on the organism's own cycle -- about 8 s at speed 12. `AMP_FLOOR` in the worklet sets how far down a voice goes when its electrode is quiet; the signal only ever spans part of its range, so a shallow floor is what makes this audible rather than a wobble. |
| `--ring` | `0` (off) | The real sum and difference tones, by multiplying the oscillators against each other. Where `--ghost` reconstructs one artifact from measured frequencies, this **is** the interaction, taken off the signals -- so all the swooping comes free. Measured at contact: 70 Hz goes from 0.0005 to 0.0194 and 210 Hz from 0.0012 to 0.0107, content belonging to no oscillator. |

`--ring` and `--ghost` overlap. `--ring` is the truer of the two; `--ghost` is
worth keeping only if a single clean sine reads better than the real cluster.

## Measured combinations

RMS of the left channel, bed against contact, from a 45 s render:

| | bed | contact | |
|---|---|---|---|
| defaults | 0.399 | 0.290 | drops at contact -- wrong way round |
| `--ghost 0.6` | 0.403 | 0.342 | rises |
| `--amp 0.8` | 0.212 | 0.242 | bed recedes, contact arrives |
| `--ghost 0.6 --amp 0.8` | 0.220 | 0.303 | +2.8 dB at contact |

## Rendering to a file instead of the speakers

Does not touch the DAC, so the service can keep running. Roughly 100x realtime.

    node synth.js --wav /tmp/t.wav --secs 45 --speed 12 --ghost 0.6

| flag | default | what it does |
|---|---|---|
| `--wav` | none | Write a WAV here instead of playing. |
| `--secs` | `30` | How long to render. |
| `--dry` | off | Generate but do not open the audio device. |

Worth doing before trusting your ears on level: check **where** the energy is,
not just how much. It is entirely possible to make the piece twice as loud and
completely inaudible, which happened -- see `exhibit_object.md`.

## Plumbing

Rarely needed; the defaults are what the object uses.

| flag | default |
|---|---|
| `--replay` | `./replay.json` |
| `--worklet` | `./ring-processor.js` |
| `--port` | `8081` |
| `--device` | `plughw:0,0` |
| `--card` | `0` |
| `--mixer` | `Digital` |

## Where the rest of the numbers live

Anything not on a flag is a constant at the top of `ring-processor.js`:
`REST_LEVEL`, `FC_BED`, `FC_OPEN`, `BED_DRIVE`, `TRI_FWD`, `SWELL_UP`,
`SWELL_DN`, `BED_DROP`, `LANDSCAPE`, `BIRD`, `ECHO_MS`, `ECHO_FB`, `ECHO_MIX`,
`ECHO_DARK`, `ECHO_SPREAD`, `GHOST_MULT`, `GHOST_FMIN`.

Two traps worth knowing. `synth.js` posts `gain`, `vco`, `mix`, `capScale`,
`tri`, `sqr`, `ghost` and `amp` to the worklet at startup, and those **override
the processor's own defaults** -- editing the constructor alone does nothing.
And `FLASH_MS` in `Drift.vue` is tied to `SWELL_UP` here: both 1.5 s, so the
bloom travels out over exactly the time the sound takes to come forward.
