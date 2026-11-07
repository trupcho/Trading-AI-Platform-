"""One-time importer for the vetted 20-file Trading AI demo starter.

Invoked by GitHub Actions once. Validates the exact package hash and stops on
any mismatch; it does not download or execute untrusted external code.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import shutil
import zlib

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SHA256 = "227b60cd03a6a963ab281632bdb75ecda6cb5c3dcb23021a5d40a340f0395ef6"
PARTS = [ROOT / ".bootstrap" / f"piece{i:02d}.txt" for i in range(1, 7)]


def main():
    encoded = "".join(p.read_text(encoding="ascii") for p in PARTS)
    actual_hash = hashlib.sha256(encoded.encode("ascii")).hexdigest()
    if actual_hash != EXPECTED_SHA256:
        raise SystemExit(f"Source bundle integrity mismatch: {actual_hash}")
    blob = zlib.decompress(base64.b64decode(encoded, validate=True))
    files = json.loads(blob)
    if not isinstance(files, dict) or len(files) != 20:
        raise SystemExit("Unexpected manifest contents (expected 20 source files)")
    for name, body in files.items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or not isinstance(body, str):
            raise SystemExit(f"Unsafe path or content: {name!r}")
        if path.parts[0] == ".bootstrap":
            raise SystemExit("Cannot overwrite staging paths")
        dest = ROOT / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")
        print("Imported", name)
    shutil.rmtree(ROOT / ".bootstrap")
    (ROOT / ".github/workflows/import.yml").unlink(missing_ok=True)
    print(f"Successfully imported {len(files)} source files.")


if __name__ == "__main__":
    main()
