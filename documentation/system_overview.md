# System overview

Written 2026-09-08. Plain-English account of the whole system, for reporting.
Current-state authority remains `STATUS.md`; where this file and that one
disagree, that one is right.

Component detail lives in `method_basis.md` (why the rig is shaped this way),
`signal_processing.md` (the reduction chain), `metered_loop.md` (the model's
budget coupling), `av_instrument.md` (sound and image) and `description.md`
(the framing of the work).

## Plain English

A slime mould grows in a sealed chamber. Metal probes under it record its
electrical activity once a second. Software reduces half an hour of that
recording to a few numbers and hands them to a language model running on a
local machine. The model has exactly one thing it can do: switch on a blue
light over part of the chamber. Light is something the organism responds to, so
the organism changes, so the readings change, so what the model sees next
changes. That circle is the work.

The model is never told whether anything it did had an effect. It has to work
that out from the record, or fail to.

As of 2026-09-08 the loop's newest property is that the organism's speed
governs how much the model gets to think with. A faster organism buys the model
a bigger working memory; a slower one shrinks it. Blue light is assumed to slow
the organism down, which means every light pulse the model orders costs it
capacity. The model is not told this part. Whether it works it out is the thing
being measured.

## The physical rig

A Raspberry Pi 5 in a sealed chamber at roughly 95% relative humidity and 24 C.

- **Electrodes.** Three recording probes and one reference, each under its own
  small block of non-nutrient agar, in a 150 mm dish. Separate blocks rather
  than a continuous bed: a bed conducts, and the divider it forms drops a 5 mV
  signal to well under a millivolt at the amplifier. This follows Adamatzky and
  Jones (2011), and is the leading explanation for the project's earlier
  no-signal history. See `method_basis.md`.
- **Measurement.** An ADS1115 converter reads each probe against the reference
  once a second at gain 16 (+-0.256 V full scale). Surface potentials here are
  single-digit millivolts.
- **Light.** A nine-zone LED matrix over the dish, arranged as a three by three
  grid. Blue light is the only thing the system can do to the organism.
- **Camera.** A still of the dish every two minutes, encoded into a timelapse.
- **Environment.** Temperature and humidity logged every second. A fan runs on
  a timed cycle for airflow, to prevent mould. Humidity is not a setpoint.

## What the electrodes record, and what is established

Most of what the probes record is not the organism: agar settling, the chamber
warming and cooling, condensation, and the electronics. Separating the organism
from that is the first problem, and the reduction layer was built and tested
against synthetic data with planted events before anything else was built.

Two things announce the organism, and both are required at once:

1. **The recording gets quieter.** When the organism forms a conductive path
   between a probe and the reference, per-sample noise drops by roughly a
   hundredfold in power. A better connection carries less noise.
2. **A rhythm appears at about 2.2 minutes**, standing above the surrounding
   speeds, at up to 1.8 thousandths of a volt.

**What holds.** All three probes have been reached by the organism. Runs 7 and
8 were the same dish twice: one day with no organism on fresh agar, then the
organism returned to the same blocks and probes. The two-minute rhythm is
absent for all 14 hours of the empty day on every probe, present in 19 of 21
hours with the organism in, and absent again after removal. When one
protoplasmic tube retracted on 2026-08-26, that channel's rhythm fell below
every prior hour while a neighbouring channel that kept its tube did not
(exact rank test, p = 0.012).

**What does not hold.** The half-hour rhythm the rig was originally designed
around is not present. It is roughly ten times smaller than expected, and is
established as absent rather than merely unfound.

**What is unresolved.** Whether the two-minute rhythm is the organism's own
electrical activity or chemistry at the metal surface where the organism
touches it. Both fit everything measured, and removing the organism removes
both at once. As of 2026-09-06 this question is deliberately no longer the
project's driving goal.

## The reduction layer

Half an hour of one-second samples becomes a small set of quantities: the
oscillation period, its amplitude, the phase lag between probes, and baseline
drift. The layer refuses to report anything it cannot distinguish from noise.

Phase relationships are handled separately, in `phaselock.py`. Entrainment
there is defined narrowly and measured, not asserted: for every moment the
light switched on, take the organism's contraction phase at that instant. If
those phases are spread evenly, the light is landing anywhere in the cycle,
which is what a driver on a fixed clock produces. If they cluster, it is
arriving at a preferred point. The statistic is vector strength, always
compared against a null built from random times in the same recording, because
a handful of events clusters by chance.

Two systems can entrain without either representing the other. That is the only
claim the module makes.

## The model loop

A language model runs locally through Ollama. Each turn it receives the reduced
state and chooses a zone, an intensity and a duration for the light, plus how
long to wait before it is shown the state again.

- **Turns are not on a clock.** One fires when the state has changed by more
  than the measurement can be sure of, or when the delay the model asked for
  has elapsed. Long gaps mean the organism has been quiet, so how often the
  model speaks is partly the organism's doing.
- **A quarter of turns are shams.** The reply is logged and the light is not
  applied. The model is never told which. A sham costs exactly what a real turn
  costs.
- **Prompt variants** are held in one file and differ only in what the model is
  told it is coupled to: BLIND (the interface and nothing else), INFORMED (told
  it is a slime mould), ADVERSARIAL, MIMIC (given Physarum's constraints rather
  than told to imitate one), NULL (a noise floor with the task removed), and
  now METERED. Running the same session through several is how the model's
  priors are separated from the signal.
- **Everything is logged per turn**, including refused actions and the model's
  per-token uncertainty. The piece is rendered from the log afterwards, not
  live.

## The metered coupling, added 2026-09-08

The organism's measured period sets the model's context window and how many
past turns it is shown. Reference period 130 seconds, the middle of the
106-164 second band measured on this rig; the scale is clamped between a
quarter and four times the base.

The direction chosen is **shorter period, more tokens**. The inverse was built
first and rejected: it makes light a reward, which is positive feedback with no
stopping condition. As built, the only way for the model to think at full width
is to leave the organism alone.

The metering rule is stated in the prompt. The relationship between light and
period is not — the model has to infer it from its own history, and that
inference is what gets scored. Each turn the model states which way it expects
the period to move; the next measurement settles it.

Predictions are directional rather than in seconds because the period is
estimated from a spectrum and cannot resolve seconds. Three numbers come out of
a run: the hit rate, the base rate that always answering the commonest
direction would score, and a signed hit rate excluding turns the model
predicted no change. A hit rate at or below the base rate is no skill.

Two outcomes are expected, and the scores separate them. The model infers that
light costs it capacity and settles at zero; or it attributes ordinary drift to
its own actuation and keeps acting. The second is the more likely first result.

Brightness is fixed at `STIMULUS_INTENSITY` and is not offered to the model.
METERED lights the whole dish rather than a zone, so duration is the only thing
it varies at all; the other prompts still choose a zone. A rolling cap bounds cumulative
exposure at 30 seconds of whole-dish light per hour for METERED, set low
because the organism cannot move out of a whole-dish stimulus, and 300 seconds
of single-zone light for the rest. Neither is a measured tolerance. Blue light moving the period is established
in the literature, so a null result would be evidence about this rig's dose and
resolution, not about the organism. It trims the duration rather than refusing
the action, and logs both numbers.

Full detail in `metered_loop.md`.

## Sound and image

The output is isomorphic, not representational. The synthesis engine is the
same kind of object as the organism: a population of coupled oscillators with
no controller. The organism's measured phase relationships set the coupling
between voices, not their pitch, so the sound emerges from the same mechanism
rather than describing it.

Mapping voltage to pitch and thresholds to triggers was rejected: it imposes
event-thinking on a system that has no events. Physarum signals by protoplasmic
flow, not action potentials.

The image is driven by the model's per-token uncertainty, registering two line
fields against each other. `av_instrument.md` and `av_instrument_build.md`.

## What the system does not claim

- **No translation.** There is no dictionary between the organism's electrical
  activity and language.
- **No conversation.** The organism has receptors for blue and UV light,
  chemical gradients, humidity, temperature, contact and substrate stiffness.
  It has no receptor for a language model. It can be shaped by one without any
  way of registering that one exists.
- **No symmetry.** The model can set zone, intensity and duration and nothing
  else — parameters, the weakest place to intervene in a system. Structure,
  rules and goals belong to the author.
- **No understanding of the organism.** The work samples it into the band of
  human perception and presents that.

## Open at the time of writing

- Sporangia are forming. The cause is not established. Drying is ruled out at
  95.7% RH. Blue and near-UV light plus starvation is the documented trigger
  for this species; infrared is not sourced either way, and the chamber's
  infrared flood currently runs continuously and cannot be gated from the Pi.
- The metered loop has never been run end to end. It is committed but not
  deployed to the machine that runs the services.
- A new LED matrix and fresh organism are going in before the first run.
- Settled 2026-09-08: the barrier zone is gone from the code, the prompts and
  the docs. All nine zones are drivable and nothing is held lit. The plasmodium
  starts on the central reference island, so zone 4 sits over the reference and
  light there enters as common mode on all three channels.
