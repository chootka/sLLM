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

# Below this a channel is treated as having nothing to show, and its coarse
# trace is dropped from the model-facing state by for_model(compact=True).
# Set just above the 0.37 mV measured on unconnected electrodes 2026-08-09.
QUIET_AMPLITUDE_MV = 0.5

# A trough only counts if the correlation actually went down, not if it merely
# paused on the way. Anything above this is still part of the decay.
TROUGH_MAX = 0.2

# How far the peak must rise above that trough to count as an oscillation.
# PROVISIONAL: set from 2026-08-09 unconnected-electrode data, which reached
# 0.13-0.22. Recalibrate against a clean empty-dish recording; until then
# expect false positives near 0.15.
MIN_DEPTH = 0.15


def acf(x):
    """Normalised autocorrelation, lag 0 upward. None if the input is flat."""
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    if x.std() < 1e-12:
        return None
    c = np.correlate(x, x, mode="full")[len(x) - 1:]
    return c / c[0]


def dominant_period(x):
    """Strongest oscillation period in seconds, or None if there isn't one.

    Autocorrelation rather than FFT: the signal is short, non-stationary and
    not a clean sinusoid.

    Do NOT take the argmax over the search band. Noise decays monotonically, so
    its largest value in the band is always at PERIOD_MIN, and the function then
    reports the shortest lag it was allowed to consider. On 2026-08-09
    unconnected data that fired on a third of pure-noise windows, all at 30-32 s.

    A real oscillation falls below zero at half a period and climbs back at a
    full one, so require a trough then a local maximum.
    """
    return _period_and_depth(x)[0]


def _period_and_depth(x):
    """(period_s, depth) -- depth is the rise above the preceding trough."""
    c = acf(x)
    if c is None:
        return None, 0.0

    hi = min(int(PERIOD_MAX * SAMPLE_HZ), len(c) - 2)
    if hi <= int(PERIOD_MIN * SAMPLE_HZ):
        return None, 0.0

    # The trough has to be genuine, not a wobble part way down the decay.
    trough = None
    for lag in range(1, hi):
        if c[lag] < c[lag - 1] and c[lag] <= c[lag + 1] and c[lag] < TROUGH_MAX:
            trough = lag
            break
    if trough is None:
        return None, 0.0

    # The FIRST peak after the trough, not the strongest: it is the fundamental,
    # later ones are harmonics. Taking the strongest lands on whichever slow bump
    # is largest -- near 120 s in the unconnected data, which made the detector
    # fire on 74% of pure-noise windows.
    best, best_depth = None, 0.0
    for lag in range(trough + 1, hi):
        if c[lag] > c[lag - 1] and c[lag] >= c[lag + 1]:
            if lag < PERIOD_MIN * SAMPLE_HZ:
                continue
            best, best_depth = lag, float(c[lag] - c[trough])
            break

    if best is None or best_depth < MIN_DEPTH:
        return None, best_depth

    raw = float(best) / SAMPLE_HZ
    return round(raw / PERIOD_QUANTUM_S) * PERIOD_QUANTUM_S, best_depth


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

    period_s, depth = _period_and_depth(detrended)

    return {
        "period_s": period_s,
        # Not for the model. Kept so MIN_DEPTH can be calibrated from logs.
        "period_depth": round(depth, 3),
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


def for_model(state, compact=False):
    """The view of the state that goes into the prompt.

    reduce_window's return is what gets logged; this is what the model sees.
    `period_depth` is dropped -- it is diagnostic, and handing the model the
    detector's confidence invites it to narrate the detector.

    Under `compact` a quiet channel loses its coarse trace, most of the payload,
    so a quiet turn genuinely costs less context. ADVERSARIAL tells the model
    exactly that, so it has to be true.
    """
    out = {}
    for key, value in state.items():
        if not isinstance(value, dict) or "amplitude_mv" not in value:
            out[key] = value
            continue

        channel = {k: v for k, v in value.items() if k != "period_depth"}
        if compact and _is_quiet(value):
            channel.pop("coarse_mv", None)
        out[key] = channel
    return out


def _is_quiet(channel):
    """Nothing detected and the swing is at the noise floor."""
    return (channel.get("period_s") is None
            and channel.get("drift_mv_per_min") is None
            and (channel.get("amplitude_mv") or 0) < QUIET_AMPLITUDE_MV)


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
