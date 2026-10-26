"""GitHub Releases에서 최신 버전을 확인합니다."""
from __future__ import annotations

import json
import re
import urllib.request

from ellview import __version__


def parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def fetch_latest(repo: str, timeout: float = 6.0) -> dict | None:
    """{'version': 'x.y.z', 'url': 릴리스 페이지, 'notes': 본문} 또는 None."""
    if not repo or "/" not in repo:
        return None
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Ellview"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    tag = d.get("tag_name") or ""
    return {"version": tag.lstrip("vV"), "url": d.get("html_url", ""), "notes": d.get("body", "")}
