#!/usr/bin/env python3
"""Mint a one-time token for registering a passkey on the admin page.

The first passkey cannot be authorised by a passkey, so enrolment is gated on
being able to run this -- that is, on having a shell on the Pi. The token is
single use, expires in ten minutes, and is stored only as a SHA-256 hash, so a
copy of the credentials file does not let anyone enrol.

    sudo -u sllm ./scripts/py scripts/enrol_passkey.py

Run it on the Pi against the deployed tree (/var/www/sllm), as the `sllm` user,
because that is who owns the credentials file the API reads.

This is also the recovery path: if every registered device is lost, SSH in and
run this again. Register at least two devices so that stays theoretical.

    --list      show enrolled passkeys and unspent tokens
    --revoke N  remove the passkey at index N
"""

import argparse
import hashlib
import pathlib
import secrets
import sys
import time
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'api'))

TTL_S = 600


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='passkey',
                        help='a name for the device, e.g. "phone"')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--revoke', type=int, metavar='N')
    parser.add_argument('--relabel', nargs=2, metavar=('N', 'LABEL'),
                        help='rename an already-enrolled passkey')
    args = parser.parse_args()

    import config
    from admin import CredentialStore

    store = CredentialStore(config.ADMIN_CREDENTIALS_FILE)

    if args.list:
        creds = store.credentials()
        if not creds:
            print("no passkeys enrolled")
        for index, cred in enumerate(creds):
            when = datetime.fromtimestamp(cred['added']).strftime('%Y-%m-%d %H:%M')
            print(f"[{index}] {cred['label']:<20} added {when}  "
                  f"sign_count={cred['sign_count']}")
        pending = [e for e in store._read().get('enrolments', [])
                   if e['expires_at'] > time.time()]
        print(f"\n{len(pending)} unspent enrolment token(s)")
        return 0

    if args.relabel is not None:
        index, label = args.relabel
        data = store._read()
        creds = data.get('credentials', [])
        try:
            index = int(index)
        except ValueError:
            print(f"'{index}' is not an index; use --list")
            return 1
        if not 0 <= index < len(creds):
            print(f"no passkey at index {index}; use --list")
            return 1
        was = creds[index]['label']
        creds[index]['label'] = label
        store._write(data)
        print(f"[{index}] '{was}' -> '{label}'")
        return 0

    if args.revoke is not None:
        data = store._read()
        creds = data.get('credentials', [])
        if not 0 <= args.revoke < len(creds):
            print(f"no passkey at index {args.revoke}; use --list")
            return 1
        removed = creds.pop(args.revoke)
        store._write(data)
        print(f"revoked {removed['label']}")
        if not creds:
            print("WARNING: no passkeys remain. The admin page cannot be "
                  "logged into until you enrol another.")
        return 0

    token = secrets.token_urlsafe(24)
    store.add_enrolment(
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=time.time() + TTL_S,
        label=args.label,
    )

    origin = getattr(config, 'ADMIN_ORIGIN', 'https://sllm.visceral.systems')
    print(f"""
Enrolment token for '{args.label}' -- valid {TTL_S // 60} minutes, single use.

  1. On the device you want to register, open:
       {origin}/?enrol={token}

  2. Click "Register this device" and approve the prompt.

The token is spent the moment it is used. It is stored here only as a hash,
so this is the only time it is shown.
""")
    return 0


if __name__ == '__main__':
    sys.exit(main())
