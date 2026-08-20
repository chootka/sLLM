"""Extracellular memory: where the model has been, held outside the model.

Physarum's memory is not internal. It lays extracellular slime as it moves and
reads it back off the substrate, avoiding ground it has already covered. The
MIMIC variant gives the model the same arrangement -- no conversation history,
and one decaying map of nine cells that persists between turns.

Marks are laid automatically by acting, not chosen. Slime is a consequence of
having been somewhere, not a decision.
"""

import json
import os
import tempfile

ZONES = 9
DECAY = 0.85            # per turn; a mark is half gone after ~4 turns


class Trail:
    def __init__(self, path, zones=ZONES, decay=DECAY):
        self.path = path
        self.zones = zones
        self.decay = decay
        self.cells = self._load()

    def _load(self):
        try:
            with open(self.path) as f:
                cells = json.load(f)['cells']
            if len(cells) == self.zones:
                return [float(c) for c in cells]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return [0.0] * self.zones

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path))
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump({'cells': self.cells}, f)
            os.replace(tmp, self.path)
        except BaseException:
            os.unlink(tmp)
            raise

    def step(self):
        """One turn of fading. Called whether or not anything was laid."""
        self.cells = [c * self.decay for c in self.cells]

    def mark(self, zone, amount=1.0):
        """Saturating: slime thickness has a ceiling, and so does this."""
        if 0 <= zone < self.zones:
            self.cells[zone] = min(1.0, self.cells[zone] + amount)

    def view(self):
        """What the model sees: 0-100 per zone, absolute.

        Absolute, not scaled to the strongest cell. Normalising to the peak
        makes a fading trail look identical to a fresh one, which is the one
        thing the map exists to distinguish.
        """
        return [round(100 * c) for c in self.cells]
