"""Verify preserved history, original ZIP manifest, and initial audit byte-for-byte."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def verify(root=ROOT):
    errors = []
    preservation = json.loads((root / "docs/HISTORICAL_PRESERVATION.json").read_text())
    for entry in preservation:
        path = root / entry["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            errors.append(entry["path"])
    with ZipFile(root / "NFL_Codex_GitHub_Migration_Starter.zip") as archive:
        original = json.loads(archive.read("docs/FILE_MANIFEST.json"))
        for item in original:
            data = archive.read(item["path"])
            if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                errors.append("ZIP:" + item["path"])
        if archive.read("docs/FILE_MANIFEST.json") != (root / "docs/FILE_MANIFEST.json").read_bytes():
            errors.append("docs/FILE_MANIFEST.json")
    return errors


if __name__ == "__main__":
    problems = verify()
    if problems:
        raise SystemExit("Historical integrity failure: " + ", ".join(problems))
    print("Historical data, ZIP, initial audit and original manifest: SHA-256 OK")
