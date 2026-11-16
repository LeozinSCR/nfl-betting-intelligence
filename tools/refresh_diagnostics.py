"""Dependency-free CI failure evidence, including missing ingestion manifests."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def summarize(raw_root, output, *, outcomes, run_url="", canonical_root=None):
    files = sorted(Path(raw_root).glob("2026/*/manifest.json"))
    manifests = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            manifests.append(
                {
                    "path": path.as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "manifest": data,
                }
            )
        except (ValueError, OSError) as exc:
            manifests.append(
                {"path": path.as_posix(), "error": type(exc).__name__ + ": " + str(exc)}
            )
    ok = (
        all(outcomes.get(k) == "success" for k in ("install", "tests", "ingest"))
        and len(manifests) == 1
        and manifests[0].get("manifest", {}).get("status") == "OK"
    )
    result = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if ok else "ERROR",
        "workflow_run_url": run_url,
        "step_outcomes": outcomes,
        "ingestions": manifests,
        "historical_data_updated": False,
        "financial_approved": False,
        "note": "Review artifacts/logs and source completeness; collection is not model validation",
    }
    if not manifests:
        result["diagnostic"] = (
            "NO_MANIFEST: setup, tests, collection or output creation failed; inspect step outcomes and logs"
        )
    if canonical_root is not None:
        builds = sorted(Path(canonical_root).glob("2026/*/build_manifest.json"))
        result["canonical_builds"] = []
        for path in builds:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                result["canonical_builds"].append(
                    {
                        "path": path.as_posix(),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "manifest": data,
                    }
                )
            except (ValueError, OSError) as exc:
                result["canonical_builds"].append(
                    {"path": path.as_posix(), "error": str(exc)}
                )
        if (
            len(builds) != 1
            or outcomes.get("canonical") != "success"
            or result["canonical_builds"][0].get("manifest", {}).get("status")
            not in ("OK", "PARTIAL")
        ):
            result["status"] = "ERROR"
            result["canonical_diagnostic"] = (
                "Missing, failed or ambiguous canonical build; inspect artifacts"
            )
        elif (
            result["status"] == "OK"
            and result["canonical_builds"][0]["manifest"]["status"] == "PARTIAL"
        ):
            result["status"] = "PARTIAL"
    logs = []
    for path in sorted(Path("reports/refresh_logs").glob("*.log")):
        logs.append(
            {
                "path": path.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    result["logs"] = logs
    dest = Path(output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", default="data/raw_auto")
    parser.add_argument("--output", default="reports/latest_nflverse_ingestion.json")
    parser.add_argument("--install", required=True)
    parser.add_argument("--tests", required=True)
    parser.add_argument("--ingest", required=True)
    parser.add_argument("--run-url", default="")
    parser.add_argument("--canonical", default=None)
    parser.add_argument("--canonical-root", default=None)
    args = parser.parse_args()
    summarize(
        args.raw_root,
        args.output,
        outcomes={
            k: getattr(args, k)
            for k in ("install", "tests", "ingest", "canonical")
            if getattr(args, k) is not None
        },
        run_url=args.run_url,
        canonical_root=args.canonical_root,
    )


if __name__ == "__main__":
    main()
