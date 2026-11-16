"""Publish a permission-independent receipt and Actions summary, even on failure."""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit


def receipt(env):
    stages = {
        key: env.get(key, "missing")
        for key in (
            "INSTALL_OUTCOME",
            "TESTS_OUTCOME",
            "INGEST_OUTCOME",
            "CANONICAL_OUTCOME",
            "ARTIFACT_OUTCOME",
        )
    }
    url = env.get("ARTIFACT_URL", "")
    parts = urlsplit(url)
    safe_link = (
        parts.scheme == "https"
        and parts.hostname == "github.com"
        and not parts.query
        and not parts.fragment
        and not parts.username
        and all(c.isalnum() or c in "/-_." for c in parts.path)
    )
    if url and not safe_link:
        stages["ARTIFACT_OUTCOME"] = "invalid_artifact_url"
        url = ""
    if stages["ARTIFACT_OUTCOME"] == "success" and not url:
        stages["ARTIFACT_OUTCOME"] = "missing_artifact_url"
    return {
        "publication_mode": "ARTIFACT_AND_STEP_SUMMARY",
        "PR_OUTCOME": "NOT_REQUESTED",
        "permission_requirement": "contents: read",
        "ARTIFACT_URL": url,
        "outcomes": stages,
        "status": "OK" if all(v == "success" for v in stages.values()) else "ERROR",
        "decision": "NO_BET",
        "retention_days": 90,
        "durable_archive": "NOT_CONFIGURED",
    }


def render(value):
    # Only fixed labels/enumerated statuses; do not echo source exceptions or secrets.
    lines = [
        "## NFL research refresh",
        "",
        f"Technical delivery: **{value['status']}**.",
        "",
        "PR creation intentionally disabled; no additional GitHub permissions required.",
        "",
        "Stage | Outcome",
        "--- | ---",
    ]
    for key, status in value["outcomes"].items():
        status = (
            status
            if status in {"success", "failure", "skipped", "cancelled", "missing"}
            else "invalid"
        )
        lines.append(f"{key} | {status}")
    if value["ARTIFACT_URL"]:
        lines += ["", f"[Snapshot, manifests and diagnostics]({value['ARTIFACT_URL']})"]
    lines += [
        "",
        "Retention: 90 days; durable archive not configured. Inspect canonical PARTIAL/ERROR separately.",
        "NO_BET. No historical Master update or statistical/financial approval.",
    ]
    return "\n".join(lines) + "\n"


def main():
    value = receipt(os.environ)
    output = Path("reports/refresh_logs/workflow_receipt.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2) + "\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as stream:
            stream.write(render(value))
    print(json.dumps(value))
    return 0  # downstream final step preserves stage failures after receipt upload


if __name__ == "__main__":
    raise SystemExit(main())
