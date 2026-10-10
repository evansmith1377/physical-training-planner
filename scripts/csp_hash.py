"""Keep the Content-Security-Policy script hash in index.html in sync with its inline script.

Usage:
  python scripts/csp_hash.py          # update the hash in place
  python scripts/csp_hash.py --check  # exit 1 if the hash is stale (used in CI)
"""
import base64
import hashlib
import re
import sys
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "index.html"
SCRIPT_RE = re.compile(r"<script>(.*?)</script>", re.S)
HASH_RE = re.compile(r"script-src 'sha256-[^']*'")


def expected_hash(html: str) -> str:
    scripts = SCRIPT_RE.findall(html)
    if len(scripts) != 1:
        sys.exit(f"Expected exactly one inline <script>, found {len(scripts)}.")
    digest = hashlib.sha256(scripts[0].encode("utf-8")).digest()
    return "sha256-" + base64.b64encode(digest).decode()


def main() -> int:
    html = PAGE.read_text(encoding="utf-8")
    want = f"script-src '{expected_hash(html)}'"
    current = HASH_RE.search(html)
    if not current:
        sys.exit("No script-src 'sha256-…' found in the CSP meta tag.")
    if current.group(0) == want:
        print("CSP script hash is up to date.")
        return 0
    if "--check" in sys.argv:
        print("CSP script hash is stale. Run: python scripts/csp_hash.py")
        return 1
    PAGE.write_text(HASH_RE.sub(want, html, count=1), encoding="utf-8")
    print(f"Updated CSP: {want}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
