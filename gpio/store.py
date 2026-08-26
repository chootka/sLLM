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
    """Append-only daily CSV, with read-back across day boundaries.

    Rows carry the run they belong to. `run_provider` is a callable returning
    the current run dict; it is consulted on every append so a mode change from
    the admin page takes effect immediately, with nothing restarted.

    Readings for a non-experiment mode are written to a subdirectory. That is
    load-bearing rather than tidy: `recent()` is what assembles the model's
    window, and it reads a directory. Demo samples left at the top level would
    be handed to a real turn as though they came from the organism.
    """

    def __init__(self, directory, prefix, fieldnames, run_provider=None):
        self.directory = directory
        self.prefix = prefix
        self.run_provider = run_provider
        # run_id and mode are appended, not prepended, so existing files and
        # anything reading them by column name are unaffected.
        self.fieldnames = list(fieldnames) + ['run_id', 'mode']
        self._lock = threading.Lock()
        self._handle = None
        self._writer = None
        self._open_key = None
        os.makedirs(directory, exist_ok=True)

    def _run(self):
        if self.run_provider is None:
            return {'id': '', 'mode': 'test'}
        try:
            return self.run_provider()
        except Exception:  # noqa: BLE001 -- recording must not stop for this
            return {'id': '', 'mode': 'test'}

    def directory_for(self, mode):
        import run as run_state

        sub = run_state.subdirectory(mode)
        return os.path.join(self.directory, sub) if sub else self.directory

    def path_for(self, day, mode='test'):
        return os.path.join(self.directory_for(mode),
                            f"{self.prefix}_{day:%Y%m%d}.csv")

    def _migrate_header(self, path):
        """Bring an older file up to the current columns, once.

        Adding run_id and mode to an existing day's file would otherwise append
        eight fields under a six-name header, which is silently malformed --
        every reader would mis-parse it and nothing would complain.

        Historical rows are filled with mode `test`, not `live`. That is
        not a guess: nothing had been run for real at the point the labelling
        was added -- the rig was still being built, and those readings include
        demo runs written before routing existed. Calling them `experiment`
        would be exactly the contamination this mechanism exists to prevent.
        """
        try:
            with open(path, newline='', encoding='utf-8') as handle:
                rows = list(csv.reader(handle))
        except OSError:
            return
        if not rows:
            return

        header = rows[0]
        if header == self.fieldnames:
            return
        missing = [name for name in self.fieldnames if name not in header]
        if not missing:
            return

        tmp = path + '.migrating'
        with open(tmp, 'w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fieldnames,
                                    extrasaction='ignore')
            writer.writeheader()
            for raw in rows[1:]:
                # Rows already carrying the extra values (written after the
                # columns were added but before this migration) keep them.
                record = dict(zip(header, raw))
                extra = raw[len(header):]
                for name, value in zip(missing, extra):
                    record[name] = value
                record.setdefault('run_id', '')
                if not record.get('mode'):
                    # Everything predating the labelling was development, not a
                    # run. Marking it `dev` is not a guess -- nothing had been
                    # run for real yet -- and it is the label that keeps it out
                    # of any analysis filtering for `experiment`.
                    record['mode'] = 'test'
                writer.writerow(record)
        os.replace(tmp, path)
        print(f"store: migrated {os.path.basename(path)} to include "
              f"{', '.join(missing)}", flush=True)

    def _ensure_open(self, day, mode):
        key = (day, mode)
        if self._open_key == key and self._handle is not None:
            return
        if self._handle is not None:
            self._handle.close()

        path = self.path_for(day, mode)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            self._migrate_header(path)
        is_new = not os.path.exists(path) or os.path.getsize(path) == 0
        self._handle = open(path, 'a', newline='', encoding='utf-8')
        self._writer = csv.DictWriter(self._handle, fieldnames=self.fieldnames,
                                      extrasaction='ignore')
        if is_new:
            self._writer.writeheader()
        self._open_key = key

    def append(self, row):
        """Write one row. `row` must carry a 'timestamp' as a unix float."""
        moment = datetime.fromtimestamp(row["timestamp"], timezone.utc)
        active = self._run()
        row = dict(row, run_id=active.get('id', ''),
                   mode=active.get('mode', 'test'))
        with self._lock:
            self._ensure_open(moment.date(), row['mode'])
            self._writer.writerow(row)
            # Flushed every row rather than buffered: at 1 Hz the cost is
            # nothing, and it means pulling the power loses at most one
            # sample instead of an unknown tail.
            self._handle.flush()

    def recent(self, seconds, now=None, mode=None):
        """Rows from the last `seconds`, oldest first, across day boundaries.

        Reads exactly one mode: the current one unless told otherwise. The
        model's window comes through here, so this is what stops one mode's
        samples ever being handed to a turn belonging to another -- a demo can
        never be reduced as though it were the organism, and development noise
        can never end up in an experimental turn.
        """
        if mode is None:
            mode = self._run().get('mode', 'test')
        now = now or datetime.now(timezone.utc)
        cutoff = (now - timedelta(seconds=seconds)).timestamp()

        # A window can straddle midnight, so read yesterday too.
        days = sorted({(now - timedelta(seconds=seconds)).date(), now.date()})

        rows = []
        for day in days:
            path = self.path_for(day, mode)
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

    def between(self, start, end, mode=None):
        """Rows with start <= timestamp <= end, oldest first.

        Like `recent`, but over an arbitrary window rather than one anchored to
        now, and it walks every day file the window touches instead of assuming
        at most two. Scrolling back through a run that has been going for days
        is the whole point, so a week-wide window has to read a week of files.
        """
        if mode is None:
            mode = self._run().get('mode', 'test')
        if end < start:
            start, end = end, start

        day = datetime.fromtimestamp(start, timezone.utc).date()
        last = datetime.fromtimestamp(end, timezone.utc).date()

        rows = []
        while day <= last:
            path = self.path_for(day, mode)
            day += timedelta(days=1)
            if not os.path.exists(path):
                continue
            with open(path, newline='', encoding='utf-8') as handle:
                reader = csv.reader(handle)
                try:
                    header = next(reader)
                    stamp_at = header.index('timestamp')
                except (StopIteration, ValueError):
                    continue
                # csv.reader with one index lookup, not DictReader: a day is
                # ~86k rows at 1 Hz and building a dict per row is most of the
                # request. Only rows inside the window get one.
                for raw in reader:
                    if len(raw) <= stamp_at:
                        continue
                    try:
                        stamp = float(raw[stamp_at])
                    except ValueError:
                        continue
                    if start <= stamp <= end:
                        rows.append(dict(zip(header, raw)))

        rows.sort(key=lambda r: float(r["timestamp"]))
        return rows

    def aggregate(self, start, end, buckets, columns, mode=None):
        """Bucketed min/max/mean per column over a window, streaming.

        `between` builds a dict per row, which is fine for an hour and ruinous
        for a month -- the whole record is three quarters of a million samples
        and every one of them would become a dict before anything looked at it.
        This walks the same files but accumulates as it reads, so the memory
        cost is the bucket table and nothing else, whatever the span.

        Returns (table, seen) where table maps bucket index -> column name ->
        [min, max, total, count], and `seen` is how many rows landed in range.
        """
        if mode is None:
            mode = self._run().get('mode', 'test')
        if end < start:
            start, end = end, start
        width = (end - start) / buckets

        day = datetime.fromtimestamp(start, timezone.utc).date()
        last = datetime.fromtimestamp(end, timezone.utc).date()

        table = {}
        seen = 0
        while day <= last:
            path = self.path_for(day, mode)
            day += timedelta(days=1)
            if not os.path.exists(path):
                continue
            with open(path, newline='', encoding='utf-8') as handle:
                reader = csv.reader(handle)
                try:
                    header = next(reader)
                    stamp_at = header.index('timestamp')
                except (StopIteration, ValueError):
                    continue
                # Resolved once per file, not per row: the header can differ
                # between days, since columns were added as the rig grew.
                wanted = [(name, header.index(name))
                          for name in columns if name in header]
                if not wanted:
                    continue

                for raw in reader:
                    if len(raw) <= stamp_at:
                        continue
                    try:
                        stamp = float(raw[stamp_at])
                    except ValueError:
                        continue
                    if stamp < start or stamp > end:
                        continue
                    seen += 1
                    index = int((stamp - start) / width)
                    if index >= buckets:
                        index = buckets - 1
                    slot = table.get(index)
                    if slot is None:
                        slot = table[index] = {}
                    for name, at in wanted:
                        if at >= len(raw):
                            continue
                        text = raw[at]
                        if not text:
                            continue
                        try:
                            value = float(text)
                        except ValueError:
                            continue
                        stats = slot.get(name)
                        if stats is None:
                            slot[name] = [value, value, value, 1]
                            continue
                        if value < stats[0]:
                            stats[0] = value
                        elif value > stats[1]:
                            stats[1] = value
                        stats[2] += value
                        stats[3] += 1

        return table, seen

    def extent(self, mode=None):
        """(earliest, latest) timestamp on disk for `mode`, or (None, None).

        What the dashboard needs to know how far back it may scroll. Reads the
        first row of the oldest file and the tail of the newest rather than
        parsing everything between them -- at 1 Hz that would be the whole run.
        """
        if mode is None:
            mode = self._run().get('mode', 'test')
        directory = self.directory_for(mode)
        try:
            names = sorted(n for n in os.listdir(directory)
                           if n.startswith(f"{self.prefix}_")
                           and n.endswith('.csv'))
        except OSError:
            return (None, None)
        if not names:
            return (None, None)

        def _column(path):
            with open(path, newline='', encoding='utf-8') as handle:
                try:
                    return csv.reader(handle).__next__().index('timestamp')
                except (StopIteration, ValueError):
                    return None

        def _first(name):
            path = os.path.join(directory, name)
            at = _column(path)
            if at is None:
                return None
            with open(path, newline='', encoding='utf-8') as handle:
                reader = csv.reader(handle)
                next(reader, None)
                for raw in reader:
                    if len(raw) > at:
                        try:
                            return float(raw[at])
                        except ValueError:
                            continue
            return None

        def _last(name):
            path = os.path.join(directory, name)
            at = _column(path)
            if at is None:
                return None
            # Tail the file rather than read it: the last timestamp is the only
            # thing wanted and the file can be nine megabytes.
            size = os.path.getsize(path)
            with open(path, 'rb') as handle:
                handle.seek(max(0, size - 65536))
                tail = handle.read().decode('utf-8', 'ignore')
            lines = tail.splitlines()
            if size > 65536 and lines:
                lines = lines[1:]  # first line is probably a fragment
            for line in reversed(lines):
                raw = next(csv.reader([line]), [])
                if len(raw) > at:
                    try:
                        return float(raw[at])
                    except ValueError:
                        continue
            return None

        return (_first(names[0]), _last(names[-1]))

    def close(self):
        with self._lock:
            if self._handle is not None:
                self._handle.close()
                self._handle = None
                self._writer = None
                self._open_day = None


def _run_provider(config):
    import run as run_state

    return lambda: run_state.current(config)


def electrode_log(config):
    """Daily electrode CSV: one column per configured channel, in millivolts."""
    channels = tuple(getattr(config, 'ADC_CHANNELS', (0, 1, 2)))
    return ReadingLog(
        config.CSV_DIR, 'electrodes',
        ['timestamp', 'datetime'] + [f'ch{c}_mv' for c in channels],
        run_provider=_run_provider(config),
    )


def environment_log(config):
    """Daily environment CSV."""
    return ReadingLog(
        config.CSV_DIR, 'environment',
        ['timestamp', 'datetime', 'temperature_c', 'temperature_f',
         'humidity_pct', 'fan_on'],
        run_provider=_run_provider(config),
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
