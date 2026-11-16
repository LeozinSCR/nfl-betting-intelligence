"""Build the only ingestion run in a fresh CI checkout; preserve a review summary."""

import argparse
import json
from pathlib import Path
from nfl_betting.canonical import build


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--raw-root", default="data/raw_auto")
    p.add_argument("--out", default="data/canonical")
    p.add_argument("--summary", default="reports/latest_canonical_build.json")
    a = p.parse_args()
    manifests = list(Path(a.raw_root).glob("2026/*/manifest.json"))
    if len(manifests) != 1:
        raise SystemExit("Exactly one ingestion manifest required for controlled build")
    folder, summary = build(manifests[0].parent, a.out)
    dest = Path(a.summary)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"canonical_folder": str(folder), "status": summary["status"]}, indent=2
        )
    )
    return 2 if summary["status"] == "ERROR" else 0


if __name__ == "__main__":
    raise SystemExit(main())
