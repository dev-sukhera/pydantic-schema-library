"""Write the wire JSON Schemas to schemas/, or verify them with --check."""

import argparse
import sys
from pathlib import Path

from drones_comms_model.json_schema import wire_schemas

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "schemas"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_DIR, help="target directory")
    parser.add_argument("--check", action="store_true", help="fail if any file is out of date")
    args = parser.parse_args()

    stale = []
    for filename, text in wire_schemas().items():
        path = args.out / filename
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path}")

    if stale:
        print("out of date, run scripts/export_schemas.py:", *map(str, stale), sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
