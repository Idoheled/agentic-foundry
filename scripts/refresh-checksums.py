#!/usr/bin/env python3
"""Refresh/check source and locked-payload checksums without downloading payloads."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import source_integrity


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="Check committed source controls and payload identities without needing actual payload files")
    action.add_argument("--write", action="store_true", help="After reviewed changes, regenerate SOURCE_MANIFEST.json and SHA256SUMS in a Git checkout")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--payload", action="store_true", help="Also verify hydrated payload bytes and modes during --check")
    args = parser.parse_args(argv)
    if args.write and args.payload:
        parser.error("--payload is a --check option; --write never changes payload.lock.json")
    root = Path(args.root).absolute()
    result = source_integrity.refresh(root) if args.write else source_integrity.check(root, args.payload)[0]
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
