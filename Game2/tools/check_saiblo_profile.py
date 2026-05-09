#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from saiblo_tools import get_profile, require_token


def main() -> int:
    parser = argparse.ArgumentParser(description='Check current Saiblo token username.')
    parser.add_argument('--expected-username', default='thebeginning')
    args = parser.parse_args()

    token = require_token('', 'game2 late probe retry')
    profile = get_profile(token)
    user = profile.get('user', {}) if isinstance(profile.get('user'), dict) else {}
    username = str(user.get('username', '')).strip()
    if username != args.expected_username:
        raise SystemExit(f'wrong username: {username!r}')
    print(username)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
