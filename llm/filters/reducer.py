"""
Reduces raw electrode readings to the state description handed to the model.

A Physarum contraction cycle runs roughly 60-120 s, so a 30 min window holds
15-30 cycles. That is enough for the period estimate to mean something.

Channels are three recording electrodes read against a common reference.
"""

import numpy as np

SAMPLE_HZ = 1
COARSE_POINTS = 60

# Resolution limits. Reporting finer than the estimate is good for produces
# jitter that gets read as change.
LAG_QUANTUM_S = 5
PERIOD_QUANTUM_S = 5

# Period search bounds, in seconds. Outside this is not the organism.
PERIOD_MIN = 30
PERIOD_MAX = 240


def dominant_period(x):
    """Strongest oscillation period in seconds, or None if there isn't one.

    Autocorrelation rather than FFT: the signal is short, non-stationary and
    not a clean sinusoid, and we only want the dominant lag.
    """
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    if x.std() < 1e-12:
        return None

    corr = np.correlate(x, x, mode="full")[len(x) - 1:]
    corr = corr / corr[0]

    lo, hi = int(PERIOD_MIN * SAMPLE_HZ), int(PERIOD_MAX * SAMPLE_HZ)
    hi = min(hi, len(corr) - 1)
    if hi <= lo:
        return None

    band = corr[lo:hi]
    peak = int(np.argmax(band))

    # A real oscillation gives a distinct peak. Noise gives a flat band.
    if band[peak] < 0.2:
        return None

    raw = float(peak + lo) / SAMPLE_HZ
    return round(raw / PERIOD_QUANTUM_S) * PERIOD_QUANTUM_S


def phase_lag(a, b, period):
    """Lag of b behind a in seconds, searched within one period.

    Quantized to 5 s. The estimate is only good to a second or two, so
    unrounded values jitter turn to turn on noise alone, and anything
    reading them narrates the jitter as change.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    if period is None or a.std() < 1e-12 or b.std() < 1e-12:
        return None

    a, b = a - a.mean(), b - b.mean()
    a, b = a / a.std(), b / b.std()

    span = int(period * SAMPLE_HZ / 2)
    lags = np.arange(-span, span + 1)
    scores = [np.dot(a, np.roll(b, lag)) for lag in lags]
    raw = float(lags[int(np.argmax(scores))]) / SAMPLE_HZ

    # Sign flipped so a positive value means b arrives after a, which is how
    # anyone reading it will expect it to work.
    return round(-raw / LAG_QUANTUM_S) * LAG_QUANTUM_S


def drift(x):
    """Baseline slope in mV/min, or None if it is not distinguishable from
    noise.

    A least squares fit to noise always returns a slope. Without a
    significance test that slope gets reported every turn, it flips sign at
    random, and anything reading it narrates each flip as a development.
    """
    x = np.asarray(x, dtype=float)
    t = np.arange(len(x))
    n = len(x)

    slope, intercept = np.polyfit(t, x, 1)
    residuals = x - (slope * t + intercept)

    # Standard error of the slope.
    se = np.sqrt((residuals ** 2).sum() / (n - 2) / ((t - t.mean()) ** 2).sum())

    # Oscillating residuals are strongly autocorrelated, so the samples are
    # not independent and the naive standard error is far too small. Inflate
    # it by the effective sample size implied by the lag-1 autocorrelation.
    r1 = np.corrcoef(residuals[:-1], residuals[1:])[0, 1]
    r1 = min(max(r1, 0.0), 0.99)
    se *= np.sqrt((1 + r1) / (1 - r1))

    if abs(slope) < 2 * se:
        return None
    return round(float(slope) * 60 * 1000, 3)


def amplitude(x):
    """Oscillation amplitude in mV, robust to noise spikes.

    Peak to peak catches the largest noise excursion in the window, so it
    reads high and jitters turn to turn. The interquartile range of a
    sinusoid is a stable estimator of the same quantity.
    """
    x = np.asarray(x, dtype=float)
    iqr = np.percentile(x, 75) - np.percentile(x, 25)
    return round(float(iqr) * 1.414 * 1000, 2)


def describe_channel(x):
    """Reduce one channel to the handful of numbers worth sending."""
    x = np.asarray(x, dtype=float)
    t = np.arange(len(x))
    detrended = x - np.polyval(np.polyfit(t, x, 1), t)

    return {
        "period_s": dominant_period(detrended),
        "amplitude_mv": amplitude(detrended),
        "drift_mv_per_min": drift(x),
        "coarse_mv": [round(float(s.mean()) * 1000, 2)
                      for s in np.array_split(x, COARSE_POINTS)],
    }


def reduce_window(channels, previous=None):
    """channels: dict of name -> array of volts. Returns the state dict.

    If previous is given, adds a 'changes' section naming what moved since
    then. A change spread over several turns is invisible in any single
    turn's numbers, so without this it has to be reconstructed from the
    conversation, and it mostly isn't.
    """
    state = {name: describe_channel(x) for name, x in channels.items()}

    names = list(channels)
    periods = [state[n]["period_s"] for n in names if state[n]["period_s"]]
    reference = float(np.median(periods)) if periods else None

    state["phase_lags_s"] = {
        f"{a}->{b}": phase_lag(channels[a], channels[b], reference)
        for a, b in zip(names, names[1:])
    }

    if previous is not None:
        state["changes_since_last_turn"] = compare(previous, state, names)

    return state


def compare(before, after, names):
    """Name what moved, in plain terms, or say nothing moved.

    Only reports changes larger than the resolution of the estimate, so a
    quantity that is merely jittering does not appear here at all.
    """
    changes = []

    for name in names:
        old, new = before.get(name, {}), after.get(name, {})

        o_p, n_p = old.get("period_s"), new.get("period_s")
        if o_p and n_p and abs(n_p - o_p) >= PERIOD_QUANTUM_S:
            pct = round((n_p - o_p) / o_p * 100)
            verb = "lengthened" if n_p > o_p else "shortened"
            changes.append(f"{name} period {verb} from {o_p}s to {n_p}s "
                           f"({pct:+d}%)")

        o_a, n_a = old.get("amplitude_mv"), new.get("amplitude_mv")
        if o_a and n_a and abs(n_a - o_a) / max(o_a, 1e-9) > 0.20:
            pct = round((n_a - o_a) / o_a * 100)
            changes.append(f"{name} amplitude {pct:+d}%")

        o_d, n_d = old.get("drift_mv_per_min"), new.get("drift_mv_per_min")
        if o_d is None and n_d is not None:
            changes.append(f"{name} baseline began drifting at {n_d} mV/min")
        elif o_d is not None and n_d is None:
            changes.append(f"{name} baseline stopped drifting")

    o_l = before.get("phase_lags_s", {})
    n_l = after.get("phase_lags_s", {})
    for pair, new_lag in n_l.items():
        old_lag = o_l.get(pair)
        if old_lag is not None and new_lag is not None and old_lag != new_lag:
            changes.append(f"lag {pair} moved from {old_lag}s to {new_lag}s")

    return changes if changes else ["nothing measurable changed"]


# ---------------------------------------------------------------------------
# Synthetic data, so all of the above can be tested with no hardware.


def synth(duration_s=1800, period_s=90, amplitude_mv=3.0, noise_mv=0.4,
          lag_s=0.0, drift_mv_per_min=0.0, seed=None):
    """One channel of plausible-looking Physarum signal, in volts."""
    rng = np.random.default_rng(seed)
    t = np.arange(0, duration_s, 1 / SAMPLE_HZ)

    wave = amplitude_mv / 2 * np.sin(2 * np.pi * (t - lag_s) / period_s)
    # Real traces are not clean sinusoids, so add a weaker harmonic.
    wave += amplitude_mv / 8 * np.sin(4 * np.pi * (t - lag_s) / period_s)
    wave += drift_mv_per_min * t / 60
    wave += rng.normal(0, noise_mv, len(t))

    return wave / 1000


if __name__ == "__main__":
    # Three channels, same oscillation, arriving 12 s apart.
    truth = {"period_s": 90, "lag_s": 12}
    channels = {
        "ch0": synth(lag_s=0, seed=1),
        "ch1": synth(lag_s=12, seed=2),
        "ch2": synth(lag_s=24, seed=3),
    }

    state = reduce_window(channels)

    print(f"planted period {truth['period_s']} s, "
          f"planted lag {truth['lag_s']} s\n")
    for name in ("ch0", "ch1", "ch2"):
        c = state[name]
        print(f"{name}: period {c['period_s']} s, "
              f"amplitude {c['amplitude_mv']} mV, "
              f"drift {c['drift_mv_per_min']} mV/min")
    print(f"\nlags: {state['phase_lags_s']}")

    print("\nflat channel:", describe_channel(synth(amplitude_mv=0,
                                                    seed=4))["period_s"])
