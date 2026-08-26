# Method basis — why the rig is built this way

Sources are in `~/research/`.

- **Adamatzky A, Jones J.** *On electrical correlates of Physarum polycephalum
  spatial activity: can we see Physarum machine in the dark?*
  arXiv:1012.1809v1 [nlin.PS], 8 Dec 2010. Biophysical Reviews and Letters
  6(01n02):29-57, 2011. → `1012.1809v1.pdf`
- **Whiting JGH, de Lacy Costello BPJ, Adamatzky A.** *Towards slime mould
  chemical sensor: mapping chemical inputs onto electrical potential dynamics
  of Physarum polycephalum.* arXiv:1312.4189v1, 2013. Sensors and Actuators B:
  Chemical, 2014. → `1312.4189v1.pdf`

## Why islands, not a continuous bed

Adamatzky and Jones place electrodes on the **bottom of the Petri dish** and
cover each one with a **separate blob of non-nutrient 2% agar**. Discrete
blobs, not a bed. Direct quote: "positioned an array of electrodes on bottom of
a Petri dish, covered electrodes with agar blobs".

A continuous bed conducts. Protoplasmic tube resistance is ~3 MΩ; spreading
resistance between mm-scale tips a few cm apart in a bed is 10-100 kΩ. That is
a divider of 30:1 to 300:1, so a 5 mV tube potential arrives at the buffer as
17-170 µV. This is the leading explanation for the no-signal history.

Bare dish floor between islands removes the path. Gaps kept at 10 mm because
the chamber runs 95-97% RH and condensation bridges narrow bare plastic.

## Why the plasmodium goes on the reference island

Adamatzky and Jones: "At the beginning of each experiment a piece of plasmodium
was placed on agar blob covering reference electrode." It grows outward to the
recording islands, so each recording channel captures an arrival.

The earlier barrier zone did the opposite — it kept the plasmodium off the
reference. Dropped.

## Why an oat flake on each recording island, none on the reference

Adamatzky and Jones: "An oat flake was placed on top of each agar blob to
attract plasmodium and provide supply of nutrients." The flakes are what pull
the organism off the reference and onto the recording sites.

## Why one reference and three recorders

Adamatzky and Jones: one ground/reference electrode and up to 8 recording
electrodes, 9 cm dish. Ours is three recorders in a 150 mm dish.

Every channel is E - REF and all three share one reference. A wobble on REF
appears identically on all three. Three traces that overlay perfectly are a
reference artifact, not biology.

## What the signal should look like

From Adamatzky and Jones, their own agar-blob setup:

| feature | value |
|---|---|
| transient before regular oscillation | **~8 h** |
| main oscillation | 30-40 min period, 4-5 mV |
| slower band | 50-70 min period, 3 mV |
| also reported | 22-28 min, 3-4 mV |
| high-frequency band, superimposed | 1-2 min, 2-3 mV |
| sclerotium forming (drying, failure) | rise to ~50 mV |

Literature background they cite: membrane potential -83.5 mV (Fingerle), and
the commonly quoted figure of 5-10 mV amplitude at 50-200 s period. The 50-200 s
figure comes from short single tubes fixed between electrodes. Adamatzky and
Jones note their own period is "15-20 times longer" than Kashimoto's and
attribute the difference to the setup. Free-range plasmodium on blobs is the
slower regime.

Note the spelling: the paper writes **Kashimoto** (also Kishimito in one place);
`hardware_setup.md` writes Kishimoto.

**Consequence for our arena.** 27.5 mm centre-to-recorder is the 2-3 cm regime,
so 30-40 min is the band to expect. The 1-2 min band may appear superimposed.
An oscillation in the first ~8 h is inside the transient and is not the signal.

## Why the noise floor run matters

Expected amplitude is 2-5 mV. Measured high-frequency noise is 0.026-0.060 mV
per sample at 8 SPS. Signal-to-noise is 50-200x, so a real oscillation cannot be
mistaken for noise — but a *drift* or a mains artifact in the 30-40 min band
could be. That is what the blank run establishes, and it is why the artifact
criterion has to be stated in the 30-40 min band rather than the 60-200 s band
inherited from the short-tube literature.

## Why 8 SPS

Nyquist for a 30-40 min oscillation needs almost nothing, so the rate is not
set by the signal. It is set by rejection: 8 SPS on the ADS1115 integrates over
a window that notches both 50 and 60 Hz mains. Dropping from the earlier rate
took noise from ~2 mV to ~50 µV.
