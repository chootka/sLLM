"""Is the stimulus arriving at a preferred phase of the organism's rhythm?

Two systems entrain each other without either one knowing anything about the
other -- the earth and the moon are locked and neither represents the other.
What entrainment does require is that the phase relationship between them stops
being arbitrary and settles. That is the only claim this module makes, and it
is measurable from the readings alone.

For every moment the light switched on, take the organism's contraction phase
at that instant. Uniform means the stimulus is landing anywhere in the cycle,
which is what a driver on a fixed clock produces. Clustered means it is
arriving at a preferred point.

The statistic is vector strength R, the resultant length of those phases on the
unit circle: 0 is perfectly spread, 1 is every event at the same phase. R is
always compared against a null built from the same number of events drawn at
random times from the same recording, because a handful of events clusters by
chance and R on its own will happily report a lock that is not there.

Shared by scripts/phase_lock.py and the /api/phase-lock endpoint so the number
on the dashboard and the number at the terminal cannot drift apart.
"""

import math

import numpy as np

# Contraction band to search for a period when none is given. Wide enough for
# the 30-40 min regime these islands produce and the shorter one the short-tube
# literature reports, and no wider -- drift below it would otherwise win.
PERIOD_MIN_S = 30.0
PERIOD_MAX_S = 3600.0
MIN_EVENTS = 8


def estimate_period(stamps, values):
    """Dominant period in the contraction band, or None."""
    x = np.asarray(values, dtype=float)
    x = x - x.mean()
    if len(x) < 16:
        return None
    dt = float(np.median(np.diff(stamps)))
    if not dt > 0:
        return None
    spectrum = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(len(x), dt)
    band = (freqs > 1.0 / PERIOD_MAX_S) & (freqs < 1.0 / PERIOD_MIN_S)
    if not band.any():
        return None
    return float(1.0 / freqs[band][np.argmax(spectrum[band])])


def onsets_from_lit(stamps, lit):
    """Timestamps where a per-sample lit flag went from off to on."""
    lit = np.asarray(lit, dtype=bool)
    if not lit.any():
        return np.array([])
    rising = np.flatnonzero(lit[1:] & ~lit[:-1]) + 1
    return np.asarray(stamps, dtype=float)[rising]


def phase_at(stamps, values, moments, period_s):
    """Contraction phase at each moment, from the analytic signal.

    Bandpassed around the period first: the phase of a signal still carrying
    baseline drift and mains is not the phase of the contraction. Hilbert is
    done by FFT so scipy is not a dependency.
    """
    stamps = np.asarray(stamps, dtype=float)
    x = np.asarray(values, dtype=float)
    x = x - x.mean()
    moments = np.asarray(moments, dtype=float)
    if len(moments) == 0 or len(x) < 16:
        return np.array([])

    dt = float(np.median(np.diff(stamps)))
    freqs = np.fft.rfftfreq(len(x), dt)
    f0 = 1.0 / period_s
    spectrum = np.fft.rfft(x)
    spectrum[(freqs < f0 / 2) | (freqs > f0 * 2)] = 0
    band = np.fft.irfft(spectrum, n=len(x))

    n = len(band)
    step = np.zeros(n)
    step[0] = 1
    step[1:(n + 1) // 2] = 2
    if n % 2 == 0:
        step[n // 2] = 1
    phases = np.angle(np.fft.ifft(np.fft.fft(band) * step))

    idx = np.searchsorted(stamps, moments)
    idx = idx[(idx > 0) & (idx < len(stamps))]
    return phases[idx]


def vector_strength(phases):
    if len(phases) == 0:
        return 0.0
    return float(abs(np.exp(1j * np.asarray(phases)).mean()))


def analyse(stamps, values, onsets, period_s=None, bins=12, shuffles=500,
            seed=0):
    """Everything the script and the dashboard both need, as one dict.

    `onsets` is a list of unix timestamps at which the light came on. Take them
    from the switches log rather than from anything the model said it wanted:
    only applied actions put light in the dish, and a sham turn asks for a zone
    that never lit.

    `verdict` is deliberately conservative: 'clustered' only when the shuffled
    null clears it at p < 0.05, 'arbitrary' otherwise, and 'insufficient' when
    there are too few onsets to say anything at all. Too few events is not a
    negative result and must not be rendered as one.
    """
    stamps = np.asarray(stamps, dtype=float)
    values = np.asarray(values, dtype=float)

    result = {"period_s": None, "n_onsets": 0, "R": None, "null_mean": None,
              "null_sd": None, "p": None, "bins": [], "bin_edges_deg": [],
              "verdict": "insufficient", "detail": ""}

    if len(stamps) < 100:
        result["detail"] = "not enough samples"
        return result

    period_s = period_s or estimate_period(stamps, values)
    if not period_s:
        result["detail"] = "no period in the contraction band"
        return result
    result["period_s"] = round(period_s, 1)

    phases = phase_at(stamps, values, np.asarray(onsets, dtype=float),
                      period_s)
    result["n_onsets"] = int(len(phases))
    if len(phases) < MIN_EVENTS:
        result["detail"] = (f"{len(phases)} light onsets; "
                            f"{MIN_EVENTS} needed before this says anything")
        return result

    R = vector_strength(phases)
    rng = np.random.default_rng(seed)
    pool = stamps[1:-1]
    null = np.array([
        vector_strength(phase_at(stamps, values,
                                 rng.choice(pool, size=len(phases),
                                            replace=False),
                                 period_s))
        for _ in range(shuffles)
    ])
    p = float((null >= R).mean())

    counts, edges = np.histogram(phases, bins=bins,
                                 range=(-math.pi, math.pi))
    result.update({
        "R": round(float(R), 4),
        "null_mean": round(float(null.mean()), 4),
        "null_sd": round(float(null.std()), 4),
        "p": round(p, 4),
        "bins": [int(c) for c in counts],
        "bin_edges_deg": [round(float(np.degrees(e)), 1) for e in edges],
        "verdict": "clustered" if p < 0.05 else "arbitrary",
        "detail": "",
    })
    return result
