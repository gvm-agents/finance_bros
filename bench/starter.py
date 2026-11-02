"""Unpack the public test documents that ship with the repo into data/items. Free; no key or network needed.

  python -m bench.starter
Everything in the pack is public SEC data, with answer keys from SEC structured data. Files already in data/items are kept.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "starter" / "public-sec-items.zip"
ITEMS = ROOT / "data" / "items"


def main() -> int:
    ITEMS.mkdir(parents=True, exist_ok=True)
    added = 0
    with zipfile.ZipFile(PACK) as z:
        for name in z.namelist():
            target = ITEMS / Path(name).name
            if target.exists():
                continue
            target.write_bytes(z.read(name))
            added += 1
    print(f"{added} test sets added to {ITEMS}; {len(list(ITEMS.glob('*.jsonl')))} there now")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
