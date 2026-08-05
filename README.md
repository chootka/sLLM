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
llm/filters/     the model-side instrument (the part under active development)
api/             Flask + Socket.IO server, runs on the Pi inside the enclosure
frontend/        Vue 3 + Vite interface — live video, readings, timelapse
arduino/         ADS1118 ADC read over SPI, streamed to the Pi over serial
processing/      earlier Processing sketches for graphing voltage and FFT
scripts/         deployment and monitoring for the Raspberry Pi
documentation/   hardware setup, deployment, Tailscale networking
etc/             nginx config
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

### The enclosure

A modular compartmented enclosure with stackable boxes and sliding trays, with
separate sections for camera and lighting, the slime mould habitat, and the
electronics. Ports are sealed with rubber stoppers for power, ethernet, and
electrode wires.

Inside it: a Raspberry Pi 5, Ag/AgCl electrodes, an ADS1118 ADC read by an
Arduino over SPI, an SHT31 temperature and humidity sensor, a macro camera, an
adjustable ring light, and a repurposed fish feeder for oats.

`api/app.py` serves electrical readings, environmental data, still capture and
an MJPEG stream, and light control, pushing live data to the frontend over
Socket.IO. See `documentation/hardware_setup.md` and
`documentation/DEPLOYMENT.md`.

### Not in this repo

The CMOS oscillator circuits. They exist and they work — they came out of an
earlier *Physarum* practice, where the organism sits in the circuit as a living
wire — but they are analog hardware with no code, and they have not yet been
integrated into the sLLM enclosure. Doing that integration, and building the
sonic loop on top of it, is the next substantial piece of work.

## WHERE IT STANDS

Working: the enclosure, electrode readings from the Pi, the live stream and
timelapse, the web interface, and remote deployment.

Working separately: the *Physarum* oscillator circuits, as an independent
practice.

Under development: `llm/filters/`, the model-side instrument.

Not yet built: the coupling between them, which is the actual instrument.

## BACKGROUND

The oscillator practice grew out of a chapter co-authored by Sarah Grant and
Lara Grant on e-textile interfaces to sound circuits, for the third edition of
Nic Collins' *Handmade Electronic Music*. Working with *Physarum* as a living
component in those circuits came directly out of it.

The installation could be exhibited in various contexts including galleries,
science museums, or your local forest.

---

*Contact: com@chootka.com*
