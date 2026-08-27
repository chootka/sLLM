"""Slime-attributable signal extraction.

Shared by scripts/slime_signal.py (offline CLI) and api/app.py (dashboard), so
both run identical code. Method and rationale: documentation/signal_processing.md

The organism connecting an electrode drops that channel's noise by 1-2 orders
of magnitude. That drop, plus a 90-200 s line standing above the local spectral
background, is the gate. Validated 2026-08-27 at 0% false positives over 11.5 h
x 3 channels of blank.
"""

import numpy as np

P_THRESH = 0.0531   # mV, 5th pct of all blank per-minute noise windows
D_THRESH = 1.01     # dex, 95th pct of all blank sliding-dex windows
WIN, STEP = 3600, 60
HOLD = 1800         # s of continuous failure before the gate shuts again
MIN_RUN = 3600      # s; shorter gated runs are discarded as spurious
TAU = 600           # high-pass cutoff, seconds
BAND = (90, 200)    # seconds

# Lead-in a caller must supply before the window it actually wants.
#
# TAU for the high-pass, WIN for the periodogram -- and MIN_RUN on top, which is
# the part that is easy to miss: the first WIN samples are forced ungated, so
# without MIN_RUN of usable record after that, no run can ever reach the minimum
# length and the gate reads zero on every short window. At WIN+TAU a 300 s live
# view left 900 s of usable record against a 3600 s minimum, so it could not
# have gated whatever was in the dish.
WARMUP = WIN + TAU + MIN_RUN


def highpass(x, tau=TAU):
    """Drop drift slower than tau s: agar settling, thermal, bridge transient.

    Retains 2-600 s, about 8 octaves. Deliberately wide -- a narrow band would
    manufacture the appearance of rhythm.
    """
    k = int(tau); f = np.ones(k) / k
    pad = np.pad(x, (k // 2, k // 2), mode='edge')
    return x - np.convolve(pad, f, mode='same')[k // 2:k // 2 + len(x)]


def bandpass(x, lo=BAND[0], hi=BAND[1]):
    """Band-limited analytic signal. angle = phase, abs = envelope, real = trace."""
    n = len(x)
    F = np.fft.fft(x)
    f = np.fft.fftfreq(n, 1.0)
    keep = np.zeros(n, dtype=bool)
    pos = f > 0
    keep[pos] = (1 / f[pos] >= lo) & (1 / f[pos] <= hi)
    F[~keep] = 0
    F[keep] *= 2
    return np.fft.ifft(F)


def presence(x, win=60):
    """Per-sample noise, mV, per win-second block. LOW = electrode connected."""
    d = np.diff(x); n = len(d) // win
    return np.array([np.std(d[i * win:(i + 1) * win]) / np.sqrt(2) for i in range(n)])


def _bg_index(win):
    """Background-window bounds for a periodogram of `win` samples.

    Period falls monotonically with frequency, so the +-0.6 octave background
    set is a contiguous slice, not a scattered mask. Returning bounds lets the
    hot loop slice instead of boolean-index -- the median call is most of the
    chain's cost and slicing is several times cheaper.

    Fixed per window length, so callers cache it rather than rebuilding it.
    """
    f = np.fft.rfftfreq(win, 1.0)
    ok = np.zeros_like(f, dtype=bool)
    ok[1:] = (1 / f[1:] >= 45) & (1 / f[1:] <= 1800)
    per = 1 / f[ok]
    lper = np.log2(per)
    lo = np.searchsorted(-lper, -lper - 0.6, side='left')
    hi = np.searchsorted(-lper, -lper + 0.6, side='right')
    return ok, per, (lo, hi)


def dex_one(x, ok, per, idx, band, w, sw2):
    """Largest 90-200 s peak above local background, in dex, for one window."""
    d, q = _dex_many(x[None, :], ok, per, idx, band, w, sw2)
    return float(d[0]), float(q[0])


def _dex_many(segs, ok, per, idx, band, w, sw2):
    """Vectorised over windows.

    The background is 79 medians per window. Done per window that is ~100k
    np.median calls for a day of data and numpy's per-call overhead, not the
    arithmetic, dominates -- it measured at 91% of the whole chain. Stacking
    the periodograms first turns it into 79 median calls on 2-D arrays.
    """
    seg = segs - segs.mean(axis=1, keepdims=True)
    P = 2 * np.abs(np.fft.rfft(seg * w, axis=1)) ** 2 / sw2
    lp = np.log10(P[:, ok])                       # (windows, bins)
    a, b = idx
    bg = np.empty_like(lp)
    for i in range(lp.shape[1]):
        bg[:, i] = np.median(lp[:, a[i]:b[i]], axis=1)
    ex = np.where(band, lp - bg, -9.0)
    j = np.argmax(ex, axis=1)
    rows = np.arange(lp.shape[0])
    return ex[rows, j], per[j]


def slide_dex(x, win=WIN, step=STEP, chunk=512):
    """dex_one over a sliding window. Returns (dex, peak_period_s) arrays.

    Windows are batched: one strided view per chunk rather than a Python loop,
    capped so a multi-day record does not materialise as one huge array.
    """
    ok, per, idx = _bg_index(win)
    band = (per >= BAND[0]) & (per <= BAND[1])
    w = np.hanning(win); sw2 = (w ** 2).sum()
    starts = np.arange(0, len(x) - win + 1, step)
    if not len(starts):
        return np.array([]), np.array([])
    d, p = [], []
    for c in range(0, len(starts), chunk):
        block = starts[c:c + chunk]
        segs = np.stack([x[s:s + win] for s in block])
        e, q = _dex_many(segs, ok, per, idx, band, w, sw2)
        d.append(e); p.append(q)
    return np.concatenate(d), np.concatenate(p)


def step_for(window_s, buckets):
    """Sliding-dex step matched to display resolution.

    slide_dex is ~90% of the chain's cost and scales linearly with step. The
    gate moves on the timescale of hours -- a tube bridging or retracting -- so
    resolving it finer than one display bucket is wasted work. Floor of 60 s
    keeps the live/short-window case at full resolution.
    """
    return int(min(600, max(60, window_s / max(1, buckets))))


def _hysteresis(open_now, hold):
    """Shut the gate only after `hold` seconds of continuous failure.

    A genuinely connected electrode still drops below threshold in short
    stretches -- ch1 was connected for 38.7 h in run 6 and the bare condition
    fragments that into ten runs. Without this the display chatters. Opening is
    left instantaneous: a late open is honest, a late close is not.
    """
    out = np.zeros(len(open_now), dtype=bool)
    fail = hold
    for i, ok in enumerate(open_now):
        fail = 0 if ok else fail + 1
        out[i] = fail < hold
    return out


def _min_run(gate, min_run):
    """Discard gated runs shorter than min_run.

    Colonisation lasts hours. Sub-hour opens are threshold noise -- in run 6
    they appear before the tube arrived. Costs min_run of latency live, which
    is why the live path reports `provisional` separately.
    """
    out = gate.copy()
    d = np.diff(np.concatenate(([0], gate.astype(int), [0])))
    for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)):
        if b - a < min_run:
            out[a:b] = False
    return out


def chain(x, step=STEP):
    """Full chain on one channel. Returns dict of 1 Hz arrays, len == len(x).

    signal is the deliverable: the band-limited trace, zeroed wherever the gate
    is shut. Flat at zero means no organism, not a dead feed -- pair it with
    ghost, which is never flat while data is arriving.
    """
    n = len(x)
    hp = highpass(x)
    an = bandpass(hp)
    p = presence(hp)
    d, pk = slide_dex(hp, step=step)

    t = np.arange(n)
    pm = (np.interp(t, np.arange(len(p)) * 60 + 30, p) if len(p)
          else np.full(n, np.inf))
    if len(d):
        grid = WIN + np.arange(len(d)) * step
        dm = np.interp(t, grid, d, left=d[0], right=d[-1])
        pkm = np.interp(t, grid, pk, left=pk[0], right=pk[-1])
    else:
        dm = np.zeros(n); pkm = np.zeros(n)

    raw_gate = (pm < P_THRESH) & (dm > D_THRESH)
    held = _hysteresis(raw_gate, HOLD)
    held[:WIN] = False    # window not yet full; extrapolating it would be invention
    gate = _min_run(held, MIN_RUN).astype(int)

    return {
        'ghost':    hp,                                  # high-passed raw, liveness
        'signal':   np.where(gate, np.real(an), 0.0),    # gated band trace
        'envelope': np.where(gate, np.abs(an), 0.0),
        'phase':    np.angle(an),
        'presence': np.clip((P_THRESH * 2 - pm) / (P_THRESH * 2), 0, 1),
        'activity': dm,
        'period':   pkm,
        'gate':     gate,
        'provisional': held.astype(int),   # gated but not yet MIN_RUN long
    }
