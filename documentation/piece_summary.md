# drift — what the piece is

Context for writing about the work. Facts only; the voice is Sarah's.

## In one line

A sealed screen-and-speaker object playing a 53-hour recording of the voltage
at four electrodes a slime mould grew over, sonified through a software model
of a CMOS oscillator circuit and drawn as an interference field.

## What is being heard and seen

A slime mould was grown in a covered dish over four Ag/AgCl electrodes set into
the gel. When it spreads far enough to make contact with one, a very faint
electrical signal appears there, rising and falling roughly every two minutes as
the organism pulses.

That signal is not played directly. It drives a **simulation of an electronic
circuit** — three 40106 relaxation oscillators wired in a ring, each coupled
into the next through a vactrol, plus a 4046 phase-locked loop, a 4051 mux and
4040 counters. The organism's voltage controls how hard the oscillators pull on
each other. A strong signal drags them onto the same note; a weak one lets them
drift apart and beat against each other. The circuit exists on a breadboard;
the object runs a per-sample model of it, not a recording of it.

- **Left channel:** the three oscillators.
- **Right channel:** the PLL, a voice that chases the oscillators and never
  quite settles.
- With no electrode connected the piece rests as a low pad. Contact opens it
  up and brings it forward over 1.5 seconds.
- The organism's rise and fall drives pitch. (An amplitude mapping exists on a
  separate branch and is not in the shipped object.)

The picture is a character grid — an ASCII interference field. Each oscillator
is a source of concentric rings; where ripples line up the field is bright,
where they cancel it is dark. As the ring locks, the three sources converge into
one set of rings, which is the same event the ear hears. When the organism
reaches an electrode, a yellow bloom travels outward from that source over
1.5 seconds — the same duration as the sound coming forward, so the two are one
gesture rather than two events.

## The recording

53.2 hours of electrode data, recorded from 2026-08-24. It plays at 12× speed,
so one full pass takes 4.4 hours, then loops. The opening is trimmed so the
first contact arrives about 29 seconds in.

Three separate connections occur across a pass, at roughly 0, 20% and 61%
through.

## The object

Raspberry Pi 4, touch panel, PCM5122 DAC, stereo out, in a sealed enclosure.
Runs headless Linux with a kiosk compositor; no operating system is visible and
there is no way into it. The display is mounted upside down so the power cable
hangs.

It arrives silent. Two touch targets: **SOUND ON** starts it, **ABOUT** opens a
panel describing what is playing and the live state of each electrode. Both are
hidden until the screen is tapped. With the sound off the field drops to a slow
standby drift, so the object rests until a visitor starts it.

Plug it in and it plays. Unplug it and it forgets nothing — there is no state to
lose.

## What is true, and what to be careful about

- The data is real, unmodified electrode measurement. It is **not live** — the
  object plays a fixed recording, and says so in its own ABOUT panel.
- The recording is spliced from two separate runs. **Sarah's position is that
  this need not be stated** — it is a compositional decision, not a claim about
  the science. Do not volunteer it, and do not write anything that implies the
  53 hours are continuous either.
- The sound is a model of a circuit, not the circuit itself, and not a
  recording of the organism's own electrical activity being amplified. Both of
  those are common and wrong readings of this kind of work.
- No species is asserted here; confirm with Sarah before naming one.
- The piece has no title beyond "drift" as a working name.

## Where it is being sold

A **media art group show hosted on eBay**. Not a physical gallery: there is no
wall label, no certificate of authenticity, no install crew. The listing has to
do the work that a gallery context normally does — but the buyer receives an
object that needs nothing except power and a place to sit.
