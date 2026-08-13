# sLLM (slimey Large Language Model)

**Public URLs:**
- https://sllm.visceral.systems/

A closed-circuit instrument for cross-substrate dialogue: a living slime mould
(*Physarum polycephalum*) and a large language model, put in recursive exchange
with each other through sound.

---

## PROJECT OVERVIEW

This project explores whether meaningful patterns of communication can emerge
between radically different forms of intelligence. By mapping electrical
responses from a non-human living organism to a computational language model,
sLLM questions our understanding of communication, intelligence, and the
boundaries between biological and artificial systems.

## WHAT? WHY?

Slime moulds occupy a special biological niche — despite being single-celled
organisms, they exhibit surprisingly complex behaviors including problem-solving
capabilities and environmental adaptation. Scientists study them for their
prototypical neuron-like behaviors, drawing parallels to much more complex
nervous systems.

Meanwhile, Large Language Models attempt to simulate human-like reasoning and
communication through computational means. Both systems represent different
approaches to "intelligence" — one evolved through billions of years of
biological processes, the other engineered through mathematical models and
trained on human-created data.

sLLM began conceptually as a playful response to the widespread cultural
fascination with artificial intelligence. The initial idea was simply to place a
live-streamed slime mould beside a chat interface, creating a satirical
juxtaposition between responsive AI chat experiences and the slow, alien
intelligence of a simple organism.

However, this evolved into a more substantive exploration of cross-species
communication. The project doesn't claim to achieve "true" communication with
slime moulds, but instead examines what happens when we create systems that
translate between fundamentally different modes of being. The human has since
stepped out of the loop. The organism is now exposed to controlled stimuli in
response to the language model — which is itself responding to the organism's
electrical activity and to the sound the instrument is making. Each half acts on
what the other just did, and the question is whether consistent patterns emerge
in the organism's electrical activity as a result.

This isn't traditional scientific research but rather an artistic experiment
that prods us to question our assumptions about communication, consciousness,
and the increasingly blurry line between biological and artificial intelligence.
Like how animal trackers can read stories and patterns in seemingly random
broken twigs, disturbed leaves, and subtle marks in soil, the project looks for
meaningful communication patterns in the subtle electrical fluctuations of slime
moulds that would otherwise be overlooked.

## THE INSTRUMENT

The project builds on years of growing *Physarum* and patching it into
oscillators built from CMOS chips, where the organism functions as a creeping
component of the analog circuit. sLLM closes the loop around that practice. It
asks what it sounds like when an organism that deliberates slowly, in chemical
gradients, over minutes and hours, is put into exchange with a language model
that responds in milliseconds.

The instrument has two halves.

**A living analog core.** The cycling of cytoplasm through the slime mould's
protoplasmic tubes sets the rhythm of the piece. Microtonal pitch and timbre
shifts give voice to the changing voltage potentials across its cell membrane.
An array of CMOS oscillators carries the logical component of an otherwise
organic synthesis. Electrodes and a camera read the organism's electrical
activity and the growth of its network.

**A digital interlocutor.** The language model is not there to control the
system. It participates in it. It listens to the sound and to the slime's
electrical activity, answers in generated sound and short text, and acts back on
the organism only through things the slime can actually sense: patterned light,
which it avoids, and placement of oat attractants. Temperature and humidity are
held steady as conditions rather than used as messages. The organism responds
over the next minutes and hours by reconfiguring where it grows and which tubes
it keeps. That changes the sound, which influences what the model says next.

The mismatch of timescales — the model's fast verbosity against the organism's
slow reconfiguration — is the material, not a problem to engineer around. Sound
is the shared medium because the ear catches subtleties in shifting signals that
the eye misses, and because slime-mould-driven oscillators are where the
*Physarum* practice began.

Once the loop is running, who is leading and who is following becomes unclear,
or unimportant.

## THE OTHER HALF OF THE TRACKER'S PROBLEM

A tracker who reads too much into a broken twig invents an animal. The organism
has no representation of the model; it responds to light and food as conditions,
not as messages. Any sense that the two are *conversing* is produced by the
instrument, and the honest version of this project has to know how much of it the
instrument is inventing.

That is what `llm/filters/` is for. It is a measuring instrument aimed at the
model rather than at the slime. Synthetic sessions are generated with events
planted at known times, so anything else the model reports is confabulation, and
anything planted that it fails to report is signal the reduction threw away.
Neither number can be established from real recordings, because there you never
know the ground truth.

Reading meaning into faint traces is the whole appeal of this project and also
its central risk. The work is in telling those two apart.

## TECHNICAL COMPONENTS

```
llm/             the model-side instrument, and the live loop that runs on the Pi
gpio/            every piece of hardware: ADC, sensor, camera, matrix, matrixd
api/             Flask + Socket.IO server and admin backend, runs on the Pi
frontend/        Vue 3 + Vite interface: live video, readings, timelapse, admin
deploy/          systemd units, udev rules, nginx config for the Pi
scripts/         deployment, monitoring, and passkey enrolment
documentation/   bring-up checklist, hardware setup, deployment, LED matrix
arduino/         legacy: ADS1118 over SPI, superseded by the ADS1115 in gpio/
processing/      legacy: Processing sketches for graphing voltage and FFT
```

### `llm/filters/` — the model-side instrument

| file | what it does |
| --- | --- |
| `reducer.py` | Reduces raw electrode traces to the state description handed to the model: dominant period, amplitude, baseline drift, inter-channel phase lag, and a coarse waveform. |
| `harness.py` | Generates a synthetic session with known planted events, slides a window along it, and runs each window through the model with conversation history intact. A twelve-hour session takes about two minutes. |
| `noise_floor.py` | Feeds one identical snapshot to the model fifty times. The counterpart to recording an empty chamber: it tells you how much apparent responsiveness you get from nothing at all. |
| `prompts.md` | Three system-prompt variants — BLIND, INFORMED, NULL — and notes on running them. |

Much of `reducer.py` exists to stop the model narrating measurement noise as an
event: period and phase lag are quantized to their real resolution, drift is
suppressed unless it clears a significance test corrected for autocorrelation,
and amplitude uses the interquartile range rather than peak-to-peak. Without
these, quantities that are merely jittering get read downstream as developments.

Requires `numpy` and `requests`, and a local [Ollama](https://ollama.com)
serving `qwen2.5:14b`.

```sh
cd llm/filters
python reducer.py                   # sanity-check the reduction against synthetic input
python harness.py                   # 24 turns, BLIND prompt, history on
python harness.py --prompt null     # describe-only, no actions
python harness.py --no-history      # ablation: does history change anything?
python noise_floor.py blind         # model noise floor
```

### `llm/loop.py` — the live loop

The same shape as `harness.py`, but against real electrodes: the window comes
off the CSV that `gpio/adc.py` writes, so a restart picks up mid-run, and the
action is applied to the matrix. Reduction and prompts are imported from
`llm/filters/` rather than reimplemented, so the replay harness stays evidence
about what the live loop actually does.

Some fraction of turns are sham blocks, logged as actions and never applied. The
model is never told which turn it is in. Every turn is appended to a JSONL log
whether or not anything happened.

```sh
./scripts/py llm/loop.py --check    # connectivity and window, no turns
```

### The enclosure

A single sealed tub with a clear lid, holding only what has to be wet. All the
electronics live outside it, on a PVC backplane mounted below the chamber, so
bare boards never sit in the humid volume.

Inside: a 100 mm petri dish on a thin agar sheet, with three Ag/AgCl electrodes
in a line and a reference in the deep corner. A 16x16 WS2812B matrix sits
face-up directly under the dish, sealed in a clear moisture pouch behind a
diffuser. A jar and wick hold humidity
passively. An SHT31 temperature and humidity sensor hangs from a sealed hole
high on the wall, above the mist line and out of both the intake stream and the
camera's view. A wall-mounted Noctua fan blows in through a filter to keep the
chamber at positive pressure, exhausting through filtered vents on the far wall.

Outside: a Pi NoIR camera with 850 nm illumination looks down through the clear
lid from a gantry. On the backplane, the three electrodes and the reference
arrive over shielded Cat6 into four MCP604 unity-gain followers biased to
mid-rail, and from there into an ADS1115. The SHT31 shares that I2C bus. A
74AHCT125 on a second board lifts the Pi's data line to 5 V to drive the matrix,
and a relay switches fan power while a separate PWM line sets its speed. Then
the Raspberry Pi 5 and a 5 V supply.

The matrix brightness cap is a power constraint, not an aesthetic one: 256 LEDs
at full white would draw roughly four times what the supply can deliver, so the
rail would sag and the panel would brown out.

Two rules organise the rest of it, both about keeping switched current away from
a microvolt front end. The two cable runs leave the chamber through grommets at
opposite ends of the wall, signal to the left and power and light to the right,
so the electrode run and the switching harness never share an exit. And the
grounds meet at a single point rather than daisy-chaining, with the Cat6 shield
and the Faraday layer outside the tub both landing at the buffer board.

Full build documentation is in the parent project directory, outside this repo:
`enclosure/physarum-chamber-layout.html` for the section, plan, and drilling
templates, and `schematics/0_physarum-full-schematic.html` for the wiring, pin
map, and design notes.

`api/app.py` is the web layer only, serving electrode readings, chamber
environment, camera, and matrix stimulus, and pushing live data to the frontend
over Socket.IO. Every device it touches lives in `gpio/`. Nothing fabricates
data: if a device is absent its readings are null and the frontend shows dashes.
See `documentation/bring_up.md` for the current build and
`documentation/DEPLOYMENT.md` for deployment.

### Not in this repo

The CMOS oscillator circuits. They exist and they work, and they came out of an
earlier *Physarum* practice where the organism sits in the circuit as a living
wire. But they are analog hardware with no code, and they have not yet been
integrated into the sLLM enclosure. Doing that integration, and building the
sonic loop on top of it, is the next substantial piece of work.

## BACKGROUND

The oscillator practice grew out of a chapter I co-authored with Lara Grant on
e-textile interfaces to sound circuits, for the third edition of Nic Collins'
*Handmade Electronic Music*. Working with *Physarum* as a living component in
those circuits developed in parallel with that writing.

---

*Contact: com@chootka.com*
