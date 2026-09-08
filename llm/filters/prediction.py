"""Scoring the model's stated prediction against what the organism then did.

The model is asked, every turn, which way the period will move by the next
telemetry. That prediction is the evidence artifact: it is the only thing in
the run that can be wrong. Prose about coupling cannot be scored, a sign can.

Predictions are directional, not in seconds, because the period estimate is a
peak FFT bin and cannot resolve seconds. For a window of T seconds the bin
spacing near period P is about P^2 / T -- 9.4 s at P=130 over a 30 min window,
19 s over 15 min. A move smaller than that is not a measurement, so it scores
as no change rather than as a miss.

'0' is the base-rate answer: most turns the period does not cross a bin, so a
model that always says '0' scores well while predicting nothing. Report the
base rate next to the hit rate, and the signed hit rate separately. A run where
signed accuracy sits at the base rate is a run where the model learned nothing.
"""


def resolution_s(period_s, window_s):
    """Half the FFT bin width near this period, in seconds, or None.

    The smallest period change the estimate can distinguish. Anything under it
    is quantisation.
    """
    if not period_s or not window_s:
        return None
    return (period_s ** 2 / window_s) / 2.0


def observed_trend(before_s, after_s, window_s):
    """Which way the period actually moved: '+', '-', '0', or None.

    Deadbanded by the measurement resolution, so a bin-width wobble is not
    reported as a direction.
    """
    if not before_s or not after_s:
        return None
    band = resolution_s(before_s, window_s)
    if band is None:
        return None
    delta = after_s - before_s
    if delta > band:
        return '+'
    if delta < -band:
        return '-'
    return '0'


def parse_trend(value):
    """The model's stated direction, or None if it gave none.

    Accepts the sign, and the words a model reaches for when it ignores the
    format. Anything else is no prediction, not a wrong one.
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ('+', '1', '+1', 'longer', 'slower', 'increase', 'up'):
        return '+'
    if text in ('-', '-1', 'shorter', 'faster', 'decrease', 'down'):
        return '-'
    if text in ('0', 'none', 'no change', 'flat', 'unchanged', 'maintain'):
        return '0'
    return None


def score(predicted, before_s, after_s, window_s):
    """One prediction against one outcome, or None if either is missing."""
    actual = observed_trend(before_s, after_s, window_s)
    if predicted is None or actual is None:
        return None
    return {
        'predicted': predicted,
        'actual': actual,
        'hit': predicted == actual,
        'period_before_s': round(before_s, 1),
        'period_after_s': round(after_s, 1),
        'resolution_s': round(resolution_s(before_s, window_s), 1),
    }


def tally(scores):
    """Hit rate over scored predictions, with the base rate to beat.

    'base_rate' is what always answering the commonest actual direction would
    score. 'signed' excludes turns the model predicted '0', which is where it
    committed to something. A hit rate at or below the base rate is no skill.
    """
    scores = [s for s in scores if s]
    if not scores:
        return None
    actuals = [s['actual'] for s in scores]
    commonest = max(set(actuals), key=actuals.count)
    signed = [s for s in scores if s['predicted'] != '0']
    return {
        'n': len(scores),
        'hits': sum(1 for s in scores if s['hit']),
        'hit_rate': round(sum(1 for s in scores if s['hit']) / len(scores), 3),
        'base_rate': round(actuals.count(commonest) / len(scores), 3),
        'base_direction': commonest,
        'n_signed': len(signed),
        'signed_hit_rate': (round(sum(1 for s in signed if s['hit'])
                                  / len(signed), 3) if signed else None),
    }
