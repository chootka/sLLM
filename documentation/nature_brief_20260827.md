# Briefing notes — Nature editor visit, 2026-08-27

Facts as of 2026-08-26 05:00 CEST. Numbers here come from run
`20260824T004220Z-live`. Current state is in `STATUS.md`.

## What the project is

Three measuring electrodes in agar islands in a petri dish, plus a reference
electrode in a fourth island. An ADS1115 16-bit ADC reads each measuring
electrode against the reference at 1 Hz, 8 SPS conversion rate. An SHT31 logs
chamber temperature and humidity at 1 Hz. A camera photographs the dish every
300 s.

Physarum polycephalum is inoculated on the reference island and grows outward.
When a protoplasmic tube reaches a measuring island, that electrode is
connected to the reference through the organism and the site becomes
measurable.

## What was measured

| | |
|---|---|
| run start | 2026-08-24 02:42 CEST |
| duration | 50 h continuous, one 15 s gap |
| bridge to ch1 | 2026-08-24 13:24:30 |
| bridge to ch2 | 2026-08-24 23:15:30 |
| ch0 | never reached by the organism |
| noise floor | 0.02-0.10 mV per sample |

## The finding

An oscillation at 2.2-2.4 min, amplitude 0.5-1.8 mV, on both bridged
electrodes.

- Absent from ch0, which the organism never reached.
- Absent from the 10 h pre-bridge record on all three channels.
- p < 0.005 against 200 coloured-noise surrogates drawn on each channel's own
  smoothed spectral background.

## Retraction event, 2026-08-26 04:05 CEST

The ch1 tube retracted. ch2 remained connected. This gives a natural on/off at
one site with a simultaneous control at the other.

- ch1 per-sample noise rose 0.032 -> 0.188 mV, the bridge signature in reverse.
- The 100-160 s line on ch1 fell to +0.48, +0.89, +0.77 dex in the three hours
  after, against +1.20 to +1.90 in the six hours before. All three post-values
  are below every pre-value; exact rank test p = 0.012.
- ch2 over the same hours: +1.58, +1.09, +1.50 against a prior range of +1.34
  to +2.18. Within range.

The signal rose at ch1 when a tube arrived and fell when it left, while the
control site did neither.

Caveat on interpretation: retraction also removes organism material from the
electrode surface, so interface electrochemistry weakens the same way. This
test does not separate the two.

## Controls run

| control | result |
|---|---|
| temperature and humidity | own line at 4.00 min, 0.0027 C and 0.0008 % RH. Nothing at 2.4 min |
| camera cadence | 132 captures epoch-averaged at +-150 s. Largest excursion z = 2.7 over 301 lags. No 300 s line in the spectrum |
| shared reference | survives channel differencing. ch1-ch2 peaks 2.22 min at 0.66 mV, p < 0.005 |
| period stability | drifts 1.82-2.58 min across successive 4 h windows |

## Prior work

- Adamatzky A, Jones J. arXiv:1012.1809. Same electrode geometry: one reference
  island with the plasmodium inoculated on it, recording islands under agar
  blobs. Reports high-frequency waves at 1-2 min, 2-3 mV.
- Kashimoto, cited in the above: surface potential 5 mV at 1.5-2 min.

Measured period here is slightly longer, amplitude somewhat lower.

## Limits — state these first

- **n = 1.** One dish, one organism, one run. No replication.
- **Organism-driven versus interface electrochemistry is not resolved.** Every
  result to date fits both. A stimulus-response test separates them; a removal
  blank does not.
- **One measurement site as of 2026-08-26 07:00.** ch0 was never colonised; ch1's tube retracted at 04:05. ch2 remains connected.
- **The 30-40 min band is absent.** The same paper reports 4-5 mV there. This
  run gives 0.23-0.47 mV, ten times under.
- One 15 s gap and three excluded windows on 2026-08-26, all listed in
  `STATUS.md`.

## If asked what is next

Either a light-stimulus test with the organism in place, or removal followed by
an 18-24 h blank. The artifact threshold is fixed in writing before either
runs: a peak in 60-200 s exceeding local background by >1.0 dex at p < 0.01,
with no organism present, means artifact.

## Phrasing

Accurate: the oscillation appeared with colonisation, is absent from the
uncolonised control, and survives the environmental and instrumental controls
run so far.

Not accurate: confirmed biological activity.
