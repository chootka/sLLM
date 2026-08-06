#!/usr/bin/env python3
"""Set the admin password for the web loop controls.

Reads the password from the terminal without echoing it and writes only a
scrypt hash into api/config.py. The password itself is never stored, never
logged, and never passed as an argument -- an argument would sit in your shell
history and in the process list for anyone running `ps`.

    ./scripts/py scripts/set_admin_password.py

Run it on the Pi against the deployed tree (/var/www/sllm), since that is the
config the service actually reads. api/config.py is untracked, so the hash does
not enter git.
"""

import getpass
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG = ROOT / 'api' / 'config.py'

KEY = 'ADMIN_PASSWORD_HASH'
MIN_LENGTH = 12

BLOCK_HEADER = "# --- admin controls ---"


def main():
    sys.path.insert(0, str(ROOT / 'api'))
    try:
        from werkzeug.security import generate_password_hash
    except ImportError:
        print("werkzeug is missing. Run this with the venv interpreter:")
        print("    ./scripts/py scripts/set_admin_password.py")
        return 1

    if not CONFIG.exists():
        print(f"no config at {CONFIG}")
        return 1

    if not sys.stdin.isatty():
        # Refuse to read a password from a pipe: it would come from a file or a
        # shell history somewhere, which is the thing this script exists to avoid.
        print("refusing to read a password from a pipe; run this in a terminal")
        return 1

    print(f"Setting {KEY} in {CONFIG}")
    password = getpass.getpass("New admin password: ")
    if len(password) < MIN_LENGTH:
        print(f"too short: {MIN_LENGTH} characters minimum")
        return 1
    if password != getpass.getpass("Repeat: "):
        print("passwords did not match")
        return 1

    digest = generate_password_hash(password)
    del password

    text = CONFIG.read_text()
    line = f"{KEY} = {digest!r}"

    if re.search(rf'^{KEY}\s*=', text, re.MULTILINE):
        text = re.sub(rf'^{KEY}\s*=.*$', line, text, count=1, flags=re.MULTILINE)
        action = "updated"
    else:
        text = text.rstrip('\n') + (
            f"\n\n{BLOCK_HEADER}\n"
            "# scrypt hash of the admin password, set by\n"
            "# scripts/set_admin_password.py. Never store the password itself.\n"
            "# Empty or absent means every /api/admin route returns 503.\n"
            f"{line}\n"
        )
        action = "added"

    CONFIG.write_text(text)
    print(f"{action} {KEY} ({digest.split('$')[0]})")
    print("\nRestart the API for it to take effect:")
    print("    sudo systemctl restart sllm-api")
    return 0


if __name__ == '__main__':
    sys.exit(main())
