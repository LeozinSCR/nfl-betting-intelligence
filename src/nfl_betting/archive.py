"""Exclusive local archive export and verification; cloud storage is unconfigured."""

import argparse
import json
import shutil
from pathlib import Path

from .provenance import sha256


def check_declared(root, entry):
    if not entry.get("path") or not entry.get("sha256"):
        raise ValueError("Declared artifact lacks path or hash")
    path = root / entry["path"]
    if (
        Path(entry["path"]).is_absolute()
        or ".." in Path(entry["path"]).parts
        or path.is_symlink()
        or not path.resolve().is_relative_to(root)
    ):
        raise ValueError("Unsafe declared path")
    if sha256(path) != entry["sha256"]:
        raise ValueError("Declared artifact hash mismatch")


def verify(folder, expected_catalog):
    folder = Path(folder).resolve()
    catalog = folder / "archive_catalog.json"
    if sha256(catalog) != expected_catalog:
        raise ValueError(
            "Catalog digest mismatch; obtain digest from independent run evidence"
        )
    files = json.loads(catalog.read_text())["files"]
    if any(p.is_symlink() for p in folder.rglob("*")):
        raise ValueError("Symlinks rejected")
    actual = {
        p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()
    }
    if actual != set(files) | {"archive_catalog.json"}:
        raise ValueError("Missing or unexpected archive file")
    for name, expected in files.items():
        path = folder / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or path.is_symlink()
            or not path.resolve().is_relative_to(folder)
        ):
            raise ValueError("Unsafe archive path")
        if sha256(path) != expected:
            raise ValueError(f"Archive hash mismatch: {name}")
    return {
        "status": "VERIFIED",
        "files": len(files),
        "catalog_sha256": expected_catalog,
    }


def export(raw, canonical, destination):
    sources = {"raw": Path(raw).resolve(), "canonical": Path(canonical).resolve()}
    destination = Path(destination).resolve()
    if any(destination.is_relative_to(source) for source in sources.values()):
        raise ValueError("Archive cannot be inside a source")
    # Validate catalog hash and source linkage before archiving.
    from .canonical import open_database

    with open_database(sources["canonical"]):
        pass
    build = json.loads((sources["canonical"] / "build_manifest.json").read_text())
    raw_manifest = sources["raw"] / "manifest.json"
    # Actual canonical manifest uses source_manifest_sha256 (not a guessed feed version).
    expected = build.get("source_manifest_sha256")
    if expected is None or sha256(raw_manifest) != expected:
        raise ValueError("Raw/canonical manifest linkage mismatch")
    raw_data = json.loads(raw_manifest.read_text())
    for entry in raw_data["sources"].values():
        if entry.get("status") == "OK":
            check_declared(sources["raw"], entry)
        for response in entry.get("http_responses", []):
            if response.get("path"):
                check_declared(sources["raw"], response)
    for entry in [*build["tables"].values(), build["database"], build["audit_csv"]]:
        check_declared(sources["canonical"], entry)
    planned = {}
    for label, source in sources.items():
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise ValueError("Symlinks rejected")
            if path.is_file():
                planned[f"{label}/{path.relative_to(source).as_posix()}"] = (
                    path,
                    sha256(path),
                )
    destination.mkdir(parents=True, exist_ok=False)
    for name, (source, _) in planned.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    catalog = {
        "version": 1,
        "storage": "LOCAL_EXPORT_NOT_CLOUD_DURABILITY",
        "files": {name: digest for name, (_, digest) in planned.items()},
    }
    path = destination / "archive_catalog.json"
    path.write_text(json.dumps(catalog, sort_keys=True, indent=2) + "\n")
    return verify(destination, sha256(path))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("export")
    create.add_argument("--raw", required=True)
    create.add_argument("--canonical", required=True)
    create.add_argument("--destination", required=True)
    check = sub.add_parser("verify")
    check.add_argument("--folder", required=True)
    check.add_argument("--expected-catalog", required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    print(json.dumps(export(**args) if command == "export" else verify(**args)))


if __name__ == "__main__":
    main()
