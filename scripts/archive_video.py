#!/usr/bin/env python3
"""Encode captured frames to h264 and thin the originals.

Two products, both under data/video:

  recent.mp4    the newest RECENT_FRAMES frames, rebuilt every run. What the
                dashboard timelapse plays.
  seg_*.mp4     permanent archive, 500 frames each, encoded once. Once a
                segment verifies, 9 of every 10 of its originals are deleted.

Measured on the real archive: 500 JPEGs = 97 MB, the same frames at crf 20 =
16 MB. gzip on the JPEGs saves 4%.

    ./scripts/py scripts/archive_video.py --status
    ./scripts/py scripts/archive_video.py --dry-run
    ./scripts/py scripts/archive_video.py --no-thin
    ./scripts/py scripts/archive_video.py
"""

import argparse
import datetime as dt
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile

IMAGE_DIR = '/var/www/sllm/data/images'
VIDEO_DIR = '/var/www/sllm/data/video'
MANIFEST = os.path.join(VIDEO_DIR, 'manifest.json')
LOCK = os.path.join(VIDEO_DIR, '.archive.lock')

SEGMENT_FRAMES = 500   # frames per archived segment
RECENT_FRAMES = 720    # 24 h at a 120 s capture interval
KEEP_EVERY = 10        # originals kept per segment: 1 in 10
# h264 only wins where consecutive frames are alike. Over the sparse early
# record every frame is a scene change and the encode came out no smaller than
# the JPEGs, so a segment is thinned only where the video actually paid.
THIN_RATIO = 0.4       # video must be this fraction of its frames, or no thin
FPS = 10               # playback rate of the encoded video
SEGMENT_CRF = 20       # encoded once, kept forever
RECENT_CRF = 20

# Early captures carry a milliseconds suffix; the API accepts both forms
NAME_RE = re.compile(r'^slime_(\d{8})_(\d{6})(?:_(\d{1,3}))?\.jpg$')


def frames():
    """Every capture on disk, oldest first, as (filename, epoch seconds)."""
    out = []
    with os.scandir(IMAGE_DIR) as scan:
        for entry in scan:
            match = NAME_RE.match(entry.name)
            if not match or not entry.is_file():
                continue
            # A zero-byte capture stops ffmpeg dead; there is nothing in it
            if entry.stat().st_size == 0:
                continue
            stamp = dt.datetime.strptime(match.group(1) + match.group(2),
                                         '%Y%m%d%H%M%S')
            if match.group(3):
                stamp = stamp.replace(microsecond=int(match.group(3).ljust(3, '0')) * 1000)
            out.append((entry.name, stamp.timestamp()))
    # The filename leads with the timestamp, so name order is time order
    out.sort()
    return out


def load_manifest():
    try:
        with open(MANIFEST) as handle:
            return json.load(handle)
    except (FileNotFoundError, ValueError):
        return {'segment_frames': SEGMENT_FRAMES, 'keep_every': KEEP_EVERY,
                'segments': []}


def write_json(path, payload):
    """Write via a temp file in the same directory, then rename."""
    directory = os.path.dirname(path)
    handle, tmp = tempfile.mkstemp(dir=directory, suffix='.tmp')
    try:
        with os.fdopen(handle, 'w') as out:
            json.dump(payload, out)
        # mkstemp is 0600; the API reads these
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def encode(names, out_path, crf, preset):
    """Encode the named frames to out_path. Returns True on a verified file."""
    listing = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False)
    try:
        for name in names:
            path = os.path.join(IMAGE_DIR, name)
            listing.write("file '%s'\n" % path)
        listing.close()

        tmp_out = out_path + '.tmp.mp4'
        command = [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-r', str(FPS), '-f', 'concat', '-safe', '0', '-i', listing.name,
            '-c:v', 'libx264', '-preset', preset, '-crf', str(crf),
            '-pix_fmt', 'yuv420p', '-movflags', '+faststart', tmp_out,
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            sys.stderr.write('ffmpeg failed: %s\n' % result.stderr.strip())
            if os.path.exists(tmp_out):
                os.unlink(tmp_out)
            return False

        counted = count_frames(tmp_out)
        if counted != len(names):
            sys.stderr.write('encoded %s frames, expected %d -- keeping originals\n'
                             % (counted, len(names)))
            os.unlink(tmp_out)
            return False

        os.replace(tmp_out, out_path)
        return True
    finally:
        if os.path.exists(listing.name):
            os.unlink(listing.name)


def count_frames(path):
    """Video frames in the file, or None if it will not decode."""
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets',
         '-show_entries', 'stream=nb_read_packets', '-of', 'csv=p=0', path],
        capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def sidecar(names, times):
    """Frame index to capture time, for the overlay burned on playback."""
    return {'fps': FPS, 'frames': len(names), 'timestamps': times,
            'first': names[0], 'last': names[-1],
            'generated': dt.datetime.now().isoformat(timespec='seconds')}


def build_recent(pool, dry_run):
    """Rebuild recent.mp4 from the newest frames, unless nothing has landed."""
    window = pool[-RECENT_FRAMES:]
    if not window:
        return False

    names = [name for name, _ in window]
    times = [at for _, at in window]
    meta_path = os.path.join(VIDEO_DIR, 'recent.json')
    try:
        with open(meta_path) as handle:
            existing = json.load(handle)
        if (existing.get('last') == names[-1]
                and existing.get('first') == names[0]
                and os.path.exists(os.path.join(VIDEO_DIR, 'recent.mp4'))):
            print('recent.mp4 current (%d frames, newest %s)' % (len(names), names[-1]))
            return False
    except (FileNotFoundError, ValueError):
        pass

    print('recent.mp4: %d frames %s -> %s' % (len(names), names[0], names[-1]))
    if dry_run:
        return True

    out_path = os.path.join(VIDEO_DIR, 'recent.mp4')
    if not encode(names, out_path, RECENT_CRF, 'veryfast'):
        return False
    write_json(meta_path, sidecar(names, times))
    print('  wrote %s (%.1f MB)'
          % (out_path, os.path.getsize(out_path) / 1e6))
    return True


def archive(pool, manifest, dry_run, thin):
    """Encode whole segments out of the frames the recent window does not hold."""
    last_archived = max((segment['last'] for segment in manifest['segments']),
                        default='')

    # Never touch the recent window: recent.mp4 is rebuilt from those originals
    eligible = [(name, at) for name, at in pool[:-RECENT_FRAMES]
                if name > last_archived]
    if len(eligible) < SEGMENT_FRAMES:
        print('archive: %d frames pending, need %d' % (len(eligible), SEGMENT_FRAMES))
        return 0

    done = 0
    while len(eligible) >= SEGMENT_FRAMES:
        batch = eligible[:SEGMENT_FRAMES]
        eligible = eligible[SEGMENT_FRAMES:]
        names = [name for name, _ in batch]
        times = [at for _, at in batch]
        source_bytes = 0
        for name in names:
            try:
                source_bytes += os.path.getsize(os.path.join(IMAGE_DIR, name))
            except FileNotFoundError:
                pass
        stem = 'seg_' + NAME_RE.match(names[0]).group(1) \
            + '_' + NAME_RE.match(names[0]).group(2)
        out_path = os.path.join(VIDEO_DIR, stem + '.mp4')

        print('%s: %s -> %s' % (stem, names[0], names[-1]))
        if dry_run:
            done += 1
            continue

        if not encode(names, out_path, SEGMENT_CRF, 'medium'):
            print('  encode failed, stopping')
            break
        write_json(os.path.join(VIDEO_DIR, stem + '.json'), sidecar(names, times))

        kept = names[::KEEP_EVERY]
        entry = {
            'file': stem + '.mp4', 'frames': len(names), 'fps': FPS,
            'first': names[0], 'last': names[-1],
            'first_at': times[0], 'last_at': times[-1],
            'bytes': os.path.getsize(out_path),
            'source_bytes': source_bytes,
            'kept': len(kept), 'thinned': False,
            'created': dt.datetime.now().isoformat(timespec='seconds'),
        }

        pays = entry['bytes'] <= THIN_RATIO * source_bytes if source_bytes else False
        if thin and not pays:
            print('  %.1f MB video against %.1f MB of frames -- originals kept'
                  % (entry['bytes'] / 1e6, source_bytes / 1e6))
        elif thin:
            keep = set(kept)
            freed = 0
            for name in names:
                if name in keep:
                    continue
                path = os.path.join(IMAGE_DIR, name)
                try:
                    freed += os.path.getsize(path)
                    os.unlink(path)
                except FileNotFoundError:
                    pass
            entry['thinned'] = True
            print('  %.1f MB video, kept %d originals, freed %.1f MB'
                  % (entry['bytes'] / 1e6, len(kept), freed / 1e6))
        else:
            print('  %.1f MB video, originals kept' % (entry['bytes'] / 1e6))

        manifest['segments'].append(entry)
        write_json(MANIFEST, manifest)
        done += 1
    return done


def status(pool, manifest):
    segments = manifest['segments']
    total_bytes = sum(segment.get('bytes', 0) for segment in segments)
    print('frames on disk : %d' % len(pool))
    if pool:
        print('oldest / newest: %s / %s' % (pool[0][0], pool[-1][0]))
    print('segments       : %d (%.1f MB)' % (len(segments), total_bytes / 1e6))
    if segments:
        print('archived up to : %s' % segments[-1]['last'])
    last_archived = max((segment['last'] for segment in segments), default='')
    pending = [name for name, _ in pool[:-RECENT_FRAMES] if name > last_archived]
    print('pending        : %d of %d needed for the next segment'
          % (len(pending), SEGMENT_FRAMES))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--recent-only', action='store_true',
                        help='rebuild recent.mp4 and stop')
    parser.add_argument('--archive-only', action='store_true',
                        help='encode segments, skip recent.mp4')
    parser.add_argument('--no-thin', action='store_true',
                        help='encode segments but keep every original')
    parser.add_argument('--dry-run', action='store_true',
                        help='report what would be encoded, write nothing')
    parser.add_argument('--status', action='store_true',
                        help='report archive state and exit')
    args = parser.parse_args()

    os.makedirs(VIDEO_DIR, exist_ok=True)
    pool = frames()
    manifest = load_manifest()

    if args.status:
        status(pool, manifest)
        return 0

    # A slow segment encode must not overlap the next timer run
    lock = open(LOCK, 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('another run holds the lock, exiting')
        return 0

    if not args.archive_only:
        build_recent(pool, args.dry_run)
    if not args.recent_only:
        archive(pool, manifest, args.dry_run, thin=not args.no_thin)
    return 0


if __name__ == '__main__':
    sys.exit(main())
