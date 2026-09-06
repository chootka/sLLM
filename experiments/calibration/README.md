# Calibration

## Plain English

These tests do not use the signal. They establish whether there is one, and
whether it belongs to the organism rather than to the chamber, the wiring or
the amplifier. Run them when an experiment needs a clean biosignal. Skip them
when it only needs to know an electrode is bridged.

## Two levels of what a signal has to be

**Connection.** An electrode is bridged by the organism. Read straight off
per-sample noise: 0.02-0.06 mV connected, 0.10-0.20 mV not. Always available,
costs nothing.

**Biosignal.** The oscillation is the organism's, not the rig's. Costs a blank
run, an organism-in run and a stimulus run, and has to be redone when the dish,
the wiring or the chamber changes.

Most work needs only the first. Run the tests here when a claim depends on the
second.

## Order

1. `electrode-health` -- the amplifier and the tips, no organism.
2. `noise-floor` -- the chamber and fresh agar, no organism.
3. `blank-vs-organism` -- the same dish, blank then organism, back to back.
4. `blue-light-response` -- does the signal answer a stimulus the metal cannot.

1-3 establish that something appears only with the organism present.
4 is what separates the organism from chemistry at a colonised electrode, which
3 cannot: removing the organism takes both away at once.

## What calibration does not do

None of it makes the signal cleaner. It says how far the signal can be trusted,
and the answer can be "not far". A recorded null is a result.
