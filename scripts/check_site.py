#!/usr/bin/env python3
"""Basic integrity checks for the generated static site."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urlparse

ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "site"

HREF_RE = re.compile(r'''(?:href|src)=["']([^"']+)["']''')


def is_external(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.scheme in {"http", "https", "mailto", "tel", "javascript"})


def main() -> None:
    if not SITE_DIR.exists():
        raise SystemExit("site/ does not exist. Run: python scripts/build_site.py")

    html_files = sorted(SITE_DIR.rglob("*.html"))
    if not html_files:
        raise SystemExit("No HTML files were generated in site/.")

    errors: list[str] = []
    for html_file in html_files:
        text = html_file.read_text(encoding="utf-8")
        for match in HREF_RE.finditer(text):
            raw_url = match.group(1).strip()
            if not raw_url or raw_url.startswith("#") or is_external(raw_url):
                continue
            clean_url, _fragment = urldefrag(raw_url)
            if clean_url.startswith("/"):
                errors.append(f"{html_file.relative_to(SITE_DIR)} uses root-relative URL {raw_url!r}; use relative URLs for GitHub Pages project sites.")
                continue
            target = (html_file.parent / clean_url).resolve()
            try:
                target.relative_to(SITE_DIR.resolve())
            except ValueError:
                errors.append(f"{html_file.relative_to(SITE_DIR)} links outside site/: {raw_url!r}")
                continue
            if not target.exists():
                errors.append(f"{html_file.relative_to(SITE_DIR)} has broken link/source: {raw_url!r}")

    required = [
        SITE_DIR / "index.html",
        SITE_DIR / "ecosistema.html",
        SITE_DIR / "productos" / "decision-system.html",
        SITE_DIR / "assets" / "css" / "styles.css",
        SITE_DIR / "assets" / "js" / "main.js",
        SITE_DIR / ".nojekyll",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"Required generated file missing: {path.relative_to(SITE_DIR)}")

    if errors:
        print("Site check failed:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    print(f"Site check passed: {len(html_files)} HTML files verified.")


if __name__ == "__main__":
    main()
