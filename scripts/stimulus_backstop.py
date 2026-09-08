#!/usr/bin/env python3
"""Blank the panel and enter recovery, whatever the stimulus run did.

Insurance for an unattended run: scripts/stimulus_run.py clears the panel on
exit, but a SIGKILL, a power cut or a reboot leaves whatever block was running
in place. Runs from a one-shot timer after the last block is due to end.

    ./scripts/py scripts/stimulus_backstop.py
"""

import os
import sys

sys.path.insert(0, '/var/www/sllm/gpio')

import recovery                                    # noqa: E402
from matrix_client import open_matrix              # noqa: E402

matrix, error = open_matrix()
if matrix is None:
    print('no matrix: %s' % error)
else:
    matrix.clear_stimulus()
    print('panel cleared, active zones:', matrix.active_zones())

state = recovery.set_state(True, dark_=True, note='step 9 backstop')
print('recovery active=%s dark=%s' % (state['active'], state['dark']))
