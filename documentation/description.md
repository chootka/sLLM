# sLLM (under development)

## What it is

A *Physarum polycephalum* plasmodium grows across agar islands in a sealed
chamber. Electrodes under the islands record its extracellular potential at one
sample per second against a common reference. Every fifteen minutes a reduction
layer turns half an hour of that recording into four quantities: oscillation
period, amplitude, the phase lag between electrodes, and baseline drift. Those
go to a language model running locally. The model has one action. It can
illuminate one of eight regions of the chamber. It is never told whether the
action had any effect.

The organism reconfigures over the following minutes to hours, which change the 
readings that influence what the model does next.

Everything is written to a log. The piece is rendered from the log afterwards
rather than live. The sound is the organism's phase relationships driving a bank
of coupled CMOS oscillators. The image is the model's per-token uncertainty
driving the registration of two line fields against each other.

## What it refuses

It does not translate. There is no dictionary between the organism's electrical
activity and natural language. I built the layer that refuses to report anything
it cannot distinguish from noise before I built anything else, and tested it
against synthetic data with planted events, because nothing else here means
anything without it.

It does not stage a conversation. An organism's world consists of exactly what
its receptors register and its effectors act on, which is Uexküll's point. Physarum 
registers blue and UV light, chemical gradients, humidity, temperature,
contact, and the stiffness of what it sits on. It moves protoplasm. It has no
receptor for a language model. It can be shaped by one but it has no way of 
registering that one exists. The model receives the organism as four numbers.

It does not claim symmetry between the physarum and the language model. The 
model can adjust zone, intensity and duration, and nothing else. In Donella Meadows' 
ranking of leverage points those are parameters, the weakest place to intervene 
in any system. Structure, rules and goals are mine. The organism has no concept
of any of them.

I am making no claims of understanding the slime mould, because it is not possible. I am not
interpreting it or speaking for it, but rather sampling it up into the band of human
perception and presenting that, which is what places this within the realm of art rather than
science. I do, however, borrow scientific practice where it is needed for designing the controls, measuring the noise floor, and the refusal to report what cannot be distinguished from noise.

## Why these two systems

Neither has a controller anywhere inside it. Physarum has no nervous system and
no site where a decision happens. Every patch of the body contracts on its own
rhythm and behavior falls out of the phase relations between patches. A
transformer has no site where meaning happens. Both are standard examples of
coherence without a center, which is why I put these two together and not some
other pair.

Where they differ is what the relations hold between. The organism's exist in the
physical world and are between places: a network of tubes, food, the lag across twenty-five millimeters. The model's are held within the digital space of memory, a collection
of vectors. So the electrodes flatten a spatial arrangement into a sequence of numbers, and
the light array turns a sequence back into an arrangement in space.

Both systems have intelligence ascribed to them more than can be definitely
demonstrated. We want to believe that Physarum can solve mazes, learn patterns, 
and be built up into a living computer, same as we want to believe AI can possess
consciousness, understanding, and creativity. We can observe these systems taking
actions that approximate these characteristics, but just almost. The words attached
to these observations are doing most of the heavy lifting.

~~Both systems give something away at the point where they stop holding together: the~~ 
~~organism at a phase slip, the model where it confabulates, which shows up as fluent~~ 
~~text over a wide spread of token probabilities.~~

This is why I paired these two systems together, as two so-called intelligences put in 
comparison with one another.

 One of my problems, which i am having now, is this asymmetry between the lucy model and the physarum. but two systems can entrain each other without knowing anything about each other. like how the earth entrains the moon, and the moon the tides on earth.

## Sound and image

Sound carries the organism and image carries the model. Neither is a readout.
Nothing maps to magnitude, because any magnitude mapping is a code a viewer
learns in thirty seconds. What both map to is whether things stay in register:
whether the oscillators hold their lock, whether the two line fields sit still
against each other.

Three electrodes give three pairwise lags, and those set the coupling strengths
between oscillators rather than their pitches. When the organism is coherent the
bank locks and holds nearly still. When lags drift or reverse it comes apart
into beating before re-locking somewhere new. I have been building oscillators
from CMOS chips for years and this work started there, so the bank is CMOS
because that is what I build with. It holds up for a second reason: a
Schmitt-trigger relaxation oscillator is the same kind of object as a Physarum
tube, with slow charge, a threshold and fast discharge. The hardware is another
instance of the same class rather than an illustration of it. A CD4046 phase-locked loop is included as a listener in its own right, a circuit whose whole function is to stay in step with
something, and which audibly strains, loses its grip and catches again.

I tuned the bank in just intonation. It suits what the circuit already does.
Coupled nonlinear oscillators mode-lock at small-integer ratios, and the locking
region narrows as the integers grow, so simple ratios hold and complicated ones
barely do. Digital dividers produce rational ratios and nothing else, so just
intervals come out of the hardware directly and equal temperament would have to
be worked around it.

The image is two overlaid gratings whose relative spacing is driven by the
model's token-level entropy. One parameter, not ten. Beating is interference
between temporal frequencies and moiré is interference between spatial ones, the
same phenomenon in two senses. The discipline is inspired by Josef Albers' classroom
exercise asking his students to recreate the texture of newsprint using only vertical 
lines. I am also drawing from another one of Albers' exercises called Daffodility, the 
practice of rendering the essence of a thing without a literal representation of it.

I also use the test that Albers' specified for testing success in the newsprint exercise.
He had students paste their drawing of the newsprint back into the newspaper to see whether it vanished. The equivalent here is to render the empty-chamber control runs through the identical pipeline and ask whether anyone can sort them from the occupied ones. Then the harder beech-against-oak version: two sessions of the same organism, one rhythmic and
one drying. If those can be told apart, the material carries the organism's condition and not only my hand.

## Form

James Tenney's four categories, as Catherine Lamb unpacks them in *The Form of the
Spiral*, are element, clang, sequence, piece. The organism and the model are not
elements. They are not perceptible at all. What is present is sound and image,
and the clang is the perception of the two together.

The two systems never coincide in the chamber, where the coupling runs hours
behind itself and nothing about it is visible. They do not coincide in the data
either. A listener is the only place the two are ever present at the same time,
so if nobody is there the encounter does not happen anywhere. Lamb's clang
already covers memory mixing with the present moment, which is how a coupling
this slow can register as form at all. It is held across a gap rather than
displayed.

So I treat playback rate as a compositional decision rather than a setting. At
real time the causal link between image and sound is imperceptible. Compressed
too far, the two collapse into simultaneity and the asymmetry is lost. Somewhere
between, the lag is felt as lag.

Most of it is silence. Via Mani Kaul, quoted in the same lecture: the absent
notes impinge on those present, and absence is felt as a real experience of
space whose purpose is to unfold an ultimate quality in attention. Without hours
of nothing, a phase slip is just a sound. Max Neuhaus' *Times Square* is the
precedent for the frame. Unmarked, permanent, on a traffic island, running
because it runs, and most people who cross it never learn it is there.

## References

- **Adamatzky & Jones**, *On electrical correlates of Physarum polycephalum
  spatial activity* (2010). In the negative. The failure mode this project is
  built to avoid.
- **Nakagaki, Yamada & Ueda** (1999) on rhythm modulation by oscillatory
  irradiation, and **Saigusa et al.** (2008) on anticipation of periodic events.
  What the organism can actually be shown to do.
- **Alim et al.**, PNAS (2013), peristalsis in a random network. The
  methodological contrast: a physical claim with a mechanism behind it.
- **Jakob von Uexküll**. Umwelt, taken literally rather than as a figure.
- **James Tenney** via **Catherine Lamb**, *The Form of the Spiral* (2020).
  Element, clang, sequence, piece; harmonic distance; the listener constructs
  the form. Carrying with it **Mani Kaul** on included and excluded space,
  **Maryanne Amacher** on the listener's music, and **Peter Ablinger**.
- **Max Neuhaus**, *Times Square*. The unannounced frame.
- **Josef Albers**. Daffodility, beech against oak, and *Interaction of Color*:
  no colour has a fixed identity, only what its neighbour makes it.
- **Rosalind Krauss**, *Video: The Aesthetics of Narcissism* (1976), and **Peter
  Campus**, *dor*.
- **Donella Meadows**. Leverage points, and delay in a feedback loop as a cause
  of oscillation in its own right.
- **Varèse** on the sound object, **Eva Hesse** on materiality, **Meret
  Oppenheim** surreality
- Still to read: **Shaheed & Wang**, *I Am Sitting in a (Latent) Room* (2024).
