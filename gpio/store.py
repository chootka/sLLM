"""On-disk logging for readings, in daily CSV files.

Everything measured gets written down, timestamped, including the turns where
nothing happened. From the build notes: the record of quiet turns is evidence,
not noise.

This exists because the rolling buffer in adc.py is memory only. A 40 minute
buffer is enough to hand the reducer a window; it is not a record of a run
that goes on for days, and a service restart empties it. The empty-chamber
run alone is two to three days.

One file per UTC day per stream:

    data/readings/electrodes_20260805.csv
    data/readings/environment_20260805.csv

UTC because a run that crosses a daylight-saving boundary would otherwise
either skip an hour of filenames or write two hours into one, and the whole
point is that the record is unambiguous afterwards.
"""

import csv
import os
import threading
from datetime import datetime, timedelta, timezone


class ReadingLog:
    """Append-only daily CSV, with read-back across day boundaries."""

    def __init__(self, directory, prefix, fieldnames):
        self.directory = directory
        self.prefix = prefix
        self.fieldnames = list(fieldnames)
        self._lock = threading.Lock()
        self._handle = None
        self._writer = None
        self._open_day = None
        os.makedirs(directory, exist_ok=True)

    def path_for(self, day):
        return os.path.join(self.directory, f"{self.prefix}_{day:%Y%m%d}.csv")

    def _ensure_open(self, day):
        if self._open_day == day and self._handle is not None:
            return
        if self._handle is not None:
            self._handle.close()

        path = self.path_for(day)
        is_new = not os.path.exists(path) or os.path.getsize(path) == 0
        self._handle = open(path, 'a', newline='', encoding='utf-8')
        self._writer = csv.DictWriter(self._handle, fieldnames=self.fieldnames,
                                      extrasaction='ignore')
        if is_new:
            self._writer.writeheader()
        self._open_day = day

    def append(self, row):
        """Write one row. `row` must carry a 'timestamp' as a unix float."""
        moment = datetime.fromtimestamp(row["timestamp"], timezone.utc)
        with self._lock:
            self._ensure_open(moment.date())
            self._writer.writerow(row)
            # Flushed every row rather than buffered: at 1 Hz the cost is
            # nothing, and it means pulling the power loses at most one
            # sample instead of an unknown tail.
            self._handle.flush()

    def recent(self, seconds, now=None):
        """Rows from the last `seconds`, oldest first, across day boundaries."""
        now = now or datetime.now(timezone.utc)
        cutoff = (now - timedelta(seconds=seconds)).timestamp()

        # A window can straddle midnight, so read yesterday too.
        days = sorted({(now - timedelta(seconds=seconds)).date(), now.date()})

        rows = []
        for day in days:
            path = self.path_for(day)
            if not os.path.exists(path):
                continue
            with open(path, newline='', encoding='utf-8') as handle:
                for row in csv.DictReader(handle):
                    try:
                        stamp = float(row["timestamp"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if stamp >= cutoff:
                        rows.append(row)

        rows.sort(key=lambda r: float(r["timestamp"]))
        return rows

    def close(self):
        with self._lock:
            if self._handle is not None:
                self._handle.close()
                self._handle = None
                self._writer = None
                self._open_day = None


def electrode_log(config):
    """Daily electrode CSV: one column per configured channel, in millivolts."""
    channels = tuple(getattr(config, 'ADC_CHANNELS', (0, 1, 2)))
    return ReadingLog(
        config.CSV_DIR, 'electrodes',
        ['timestamp', 'datetime'] + [f'ch{c}_mv' for c in channels],
    )


def environment_log(config):
    """Daily environment CSV."""
    return ReadingLog(
        config.CSV_DIR, 'environment',
        ['timestamp', 'datetime', 'temperature_c', 'temperature_f',
         'humidity_pct', 'fan_on'],
    )


def channels_from_rows(rows, channels):
    """CSV rows -> {name: list of volts}, the shape reduce_window wants.

    The CSV is in millivolts because that is what is readable in a spreadsheet
    at these magnitudes; the reducer works in volts. Converting here keeps the
    unit boundary in one place.
    """
    out = {}
    for channel in channels:
        column = f'ch{channel}_mv'
        values = []
        for row in rows:
            raw = row.get(column)
            if raw in (None, ''):
                continue
            try:
                values.append(float(raw) / 1000.0)
            except ValueError:
                continue
        out[f'ch{channel}'] = values
    return out
