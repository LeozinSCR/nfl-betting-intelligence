"""Local code identity and capture of actual nflreadpy HTTP responses."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_identity():
    root = Path(__file__).resolve().parents[2]

    def git(*args):
        try:
            return (
                subprocess.check_output(
                    ["git", "-C", str(root), *args], stderr=subprocess.DEVNULL
                )
                .decode()
                .strip()
            )
        except (OSError, subprocess.CalledProcessError):
            return None

    paths = list(Path(__file__).parent.glob("*.py")) + list(
        Path(__file__).parent.glob("*.sql")
    )
    paths += [
        root / p for p in ("pyproject.toml", "requirements.lock") if (root / p).exists()
    ]
    return {
        "git_commit": git("rev-parse", "HEAD"),
        "worktree_dirty": bool(git("status", "--porcelain")),
        "files_sha256": {str(p.relative_to(root)): sha256(p) for p in sorted(paths)},
    }


def safe_url(url):
    # Redirect URLs can contain temporary asset signatures; do not retain them.
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


@contextmanager
def capture_downloads(folder):
    """Scope instrumentation to this CLI; use URLs resolved by the installed loader.

    Force cache off so every successful source has a real HTTP response/body hash.
    No global requests monkeypatch; restore downloader and cache configuration.
    """
    import nflreadpy as nfl
    from nflreadpy.config import get_config
    from nflreadpy.downloader import get_downloader

    downloader = get_downloader()
    config = get_config()
    old_cache, old_verbose = config.cache_mode, config.verbose
    config.cache_mode = "off"
    config.verbose = False
    original = downloader._download_file
    prior_hooks = list(downloader.session.hooks.get("response", []))
    trace = {"source": None, "requested_url": None, "responses": []}

    def hook(response, *args, **kwargs):
        item = {
            "source": trace["source"],
            "requested_url": safe_url(trace["requested_url"]),
            "response_url": safe_url(response.url),
            "status_code": response.status_code,
            "received_at_utc": datetime.now(timezone.utc).isoformat(),
            "headers": {
                k: response.headers.get(k)
                for k in ("ETag", "Last-Modified", "Date", "Content-Type")
            },
        }
        if response.status_code == 200:
            raw = response.content
            dest = (
                Path(folder)
                / "http"
                / (str(trace["source"]) + "-" + str(len(trace["responses"])) + ".body")
            )
            dest.parent.mkdir(exist_ok=True)
            dest.write_bytes(raw)
            item.update(
                path=str(dest.relative_to(folder)), bytes=len(raw), sha256=sha256(dest)
            )
        trace["responses"].append(item)
        return response

    def traced(url, **kwargs):
        trace["requested_url"] = url
        return original(url, **kwargs)

    downloader._download_file = traced
    downloader.session.hooks["response"] = prior_hooks + [hook]
    try:
        yield trace
    finally:
        downloader._download_file = original
        downloader.session.hooks["response"] = prior_hooks
        config.cache_mode, config.verbose = old_cache, old_verbose
