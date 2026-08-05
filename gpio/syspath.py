"""Put the apt-installed system packages on the path. Import this first.

The venv cannot pip-install everything this project needs. `board` and the
RPi.GPIO shim come from apt, in /usr/lib/python3/dist-packages, and the
matrix's C extension `_rpi_ws281x` comes from a root pip install, in
/usr/local/lib/pythonX.Y/dist-packages. Neither is visible to a venv by
default.

Appended rather than prepended, so the venv keeps priority and only genuinely
missing modules fall through to the system. That ordering matters: the venv
used to carry a pip RPi.GPIO 0.7.1, which does not work on a Pi 5 at all, and
prepending was the only thing keeping the working apt shim in front of it. The
broken copy has been removed, but the ordering is still the safer default for
everything else -- numpy in particular.

Run everything with the venv interpreter, the same one the service uses:

    /var/www/sllm/api/venv/bin/python gpio/adc.py watch

Testing under a different interpreter than production is how you find out
about a missing dependency from the installation rather than from the bench.
"""

import sys

SYSTEM_PATHS = (
    '/usr/lib/python3/dist-packages',
    f'/usr/local/lib/python{sys.version_info.major}.{sys.version_info.minor}'
    '/dist-packages',
)

for _path in SYSTEM_PATHS:
    if _path not in sys.path:
        sys.path.append(_path)
