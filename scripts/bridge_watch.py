#!/usr/bin/env python3
"""Start sllm-loop when the plasmodium reaches an oat-flake island.

Per-island mean absolute difference against a baseline frame, brightness
normalised. Two guards against a false start:

  1. sustained -- the island stays above threshold for SUSTAIN checks
  2. local     -- its change exceeds the other oat islands by LOCAL_X, so
                  condensation or a lighting shift, which move all of them
                  together, cannot trigger a start

The reference island is measured and reported but never triggers: the organism
is already on it.
"""
import glob
import os
import subprocess
import time

import numpy as np
from PIL import Image

IMAGES = '/var/www/sllm/data/images'
OATS = {
    'island1_top':    (930, 40, 1300, 310),
    'island3_middle': (1120, 680, 1480, 970),
    'island4_bottom': (1070, 1000, 1500, 1290),
}
REF_NAME, REF_BOX = 'island2_ref', (1040, 340, 1420, 650)
TRIGGER_X, LOCAL_X, SUSTAIN, CHECK_S = 4.0, 2.0, 3, 300
DEADLINE = time.time() + 14 * 3600


def frames():
    return sorted(glob.glob(os.path.join(IMAGES, 'slime_2026*.jpg')))


def roi(path, box):
    a = np.asarray(Image.open(path).convert('L').crop(box), np.float32)
    return a / max(a.mean(), 1e-6)


fs = frames()
base_path = fs[-1]
boxes = dict(OATS); boxes[REF_NAME] = REF_BOX
baseline = {n: roi(base_path, b) for n, b in boxes.items()}
noise = {n: max(float(np.mean([np.abs(roi(fs[i], b) - roi(fs[i+1], b)).mean()
                               for i in range(len(fs)-6, len(fs)-1)])), 1e-6)
         for n, b in boxes.items()}

print('baseline:', os.path.basename(base_path), flush=True)
for n in boxes:
    print(f'  {n:16} noise {noise[n]:.5f}  trigger {noise[n]*TRIGGER_X:.5f}', flush=True)
print(flush=True)

streak = {n: 0 for n in OATS}
hit = None
while time.time() < DEADLINE and hit is None:
    time.sleep(CHECK_S)
    fs = frames()
    if not fs:
        continue
    latest = fs[-1]
    ratios = {n: np.abs(roi(latest, b) - baseline[n]).mean() / noise[n]
              for n, b in boxes.items()}
    for n in OATS:
        others = [ratios[o] for o in OATS if o != n]
        local = ratios[n] >= LOCAL_X * max(float(np.median(others)), 0.5)
        streak[n] = streak[n] + 1 if (ratios[n] >= TRIGGER_X and local) else 0
        if streak[n] >= SUSTAIN:
            hit = (n, ratios[n], latest)
    print(time.strftime('%H:%M'),
          '  '.join(f'{n.split("_")[0]} {ratios[n]:5.1f}x' for n in boxes),
          flush=True)

print(flush=True)
if not hit:
    print('no arrival within the deadline; loop NOT started')
    raise SystemExit(0)

name, ratio, latest = hit
print(f'ARRIVAL {name}: {ratio:.1f}x noise, sustained {SUSTAIN} checks')
print(f'frame {os.path.basename(latest)}')
r = subprocess.run(['sudo', '-n', 'systemctl', 'start', 'sllm-loop'],
                   capture_output=True, text=True)
print('start sllm-loop ->', r.returncode, r.stderr.strip())
time.sleep(5)
print('sllm-loop is now:', subprocess.run(['systemctl', 'is-active', 'sllm-loop'],
                                          capture_output=True, text=True).stdout.strip())
