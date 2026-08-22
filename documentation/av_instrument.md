# A/V instrument — design direction

Written 2026-08-22. Direction, not a spec.

## Principle

**Isomorphic, not representational.** The synthesis engine is the same kind of
object as the organism — a population of coupled oscillators with no
controller. The organism's measured phase relationships set the **coupling**
between synthesis voices, not their pitch. Sound emerges from the same
mechanism rather than describing it.

The same move already exists elsewhere in the project: the `mimic` prompt
variant in `llm/filters/prompts.md` gives the model Physarum's architecture
instead of telling it about Physarum. Same method, different substrate.

## What the organism is

Facts the design has to respect:

- **No events.** No spikes, no onsets, no attacks. Signalling is by protoplasmic
  flow, not action potentials (Alim et al. 2017, PNAS 114(20)).
- **Contraction fronts propagate at ~13 µm/s**, range 1-20 µm/s (Alim 2017).
  Across 30 mm of dish that is ~38 min between two electrodes.
- **Period 50-200 s**, typically ~80-120 s. Amplitude 0.1-5 mV through agar.
- **Phase, not amplitude, carries the structure.** Adamatzky and Jones 2011
  report slow anti-phase potential changes between neighbouring electrodes,
  reflecting protoplasm transport, and synchronous changes when two electrodes
  are colonised together.
- **A single cell, many nuclei, no nervous system.** Nothing coordinates the
  oscillators except flow between them.

Mapping voltage to pitch and thresholds to triggers imposes event-thinking on a
system that has none. Rejected.

## Consequences for the instrument

| organism | synthesis |
|---|---|
| oscillator per region | voice per channel |
| coupling by protoplasmic flow | coupling coefficient between voices |
| phase relationship between sites | phase relationship between voices |
| slow reconfiguration of the network | slow reconfiguration of the coupling matrix |
| period 50-200 s | see timescale below |

The measured quantity that drives the instrument is **inter-channel phase**,
and how it changes. Amplitude is secondary. Absolute voltage is not used.

## Timescale

Periods of 50-200 s are ~3 orders of magnitude below audio rate.

**Primary: do not transpose.** The organism's timescale is the structural
timescale — it modulates timbre and texture over minutes. The audience
experiences duration.

**Optional layer: transposed to audio rate.** Immediate, but it is a
frequency-shifted artifact, not the organism. Not the whole piece.

## Build against the existing contract

`frontend/src/viz/synthField.js` already emits frames shaped like the real
feed, with constants measured from real data, so the renderer can be tuned
without the organism:

```
{ t, channels: [ { ch, mv, envelope, phase, polarity, period, bursting } ] }
```

`phase` is already in there, in radians. Build the instrument against this and
it plugs into the live feed unchanged.

`frontend/src/viz/skeletonGraph.js` assigns skeleton points to electrode
territories by **geodesic** distance along the tubes, not screen distance,
because the organism conducts along its body. Keep that: the visual treats the
plasmodium as a topology, not an image.

Prior Processing work with FFT is in `processing/phygraph/` and
`processing/_old/Physarum_Project/`.

## Constraint: the A/V is a physical stimulus

Blue light is a documented Physarum stimulus. If the instrument runs in the
same space as the chamber, light and sound are uncontrolled variables in the
experiment the paper depends on.

Either the two artifacts are physically separated, or the instrument runs only
outside experiment windows. Decide before building the enclosure.

## Project artifacts

1. **The loop.** Slime and LLM as two disparate systems in exchange. This is
   what the paper is about. Evidential standards, pre-registered tests — see
   `growth_run.md`.
2. **The instrument.** Slime modulating sound and visuals. Expressive
   standards. Not part of the paper's evidential chain.

Keep them separate. The instrument must not feed back into the experiment.

## Open

- Venue: gallery installation, web, live performance, screen? **TBC**
- Is the dish present with the audience, or is the A/V the only access? **TBC**
- Realtime off the live organism, or composed from recordings? **TBC**
- Synthesis platform: Web Audio in the existing Vue frontend, or a separate
  engine? **TBC**
- Coupling model: which oscillator network (Kuramoto, relaxation oscillators,
  the particle model from Adamatzky and Jones 2011)? **TBC**
