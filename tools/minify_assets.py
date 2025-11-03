#!/usr/bin/env python3
"""
Minify first-party JS and CSS assets.
Usage:
    python tools/minify_assets.py

Requires (JS):
    pip install rjsmin

CSS minification uses a lightweight built-in routine (no extra deps).
"""
from pathlib import Path
import sys
import re

try:
    from rjsmin import jsmin
except Exception as e:
    sys.stderr.write("Missing dependency 'rjsmin'. Install with: pip install rjsmin\n")
    raise

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "interfaces" / "http" / "flask" / "web" / "static"

JS_FILES = [
    STATIC / "js" / "motif_dipoles.js",
    STATIC / "js" / "toxin_filter.js",
]

CSS_DIR = STATIC / "css"


def cssmin(css: str) -> str:
    """Very small CSS minifier (remove comments and unnecessary whitespace).
    Not as aggressive as rcssmin but safe for our stylesheets.
    """
    # Remove all comments /* ... */
    css = re.sub(r"/\*[^*]*\*+(?:[^/*][^*]*\*+)*/", "", css)
    # Collapse whitespace
    css = re.sub(r"\s+", " ", css)
    # Remove spaces around punctuation
    css = re.sub(r"\s*([{};:,])\s*", r"\1", css)
    # Remove trailing semicolons before }
    css = re.sub(r";\}", "}", css)
    # Trim
    return css.strip()


def write_js_min(src: Path) -> None:
    if not src.exists():
        print(f"⚠ Skipping, not found: {src}")
        return
    dst = src.with_suffix('.min.js')
    code = src.read_text(encoding='utf-8')
    minified = jsmin(code)
    dst.write_text(minified, encoding='utf-8')
    before = len(code)
    after = len(minified)
    saved = before - after
    print(f"✓ {src.name} → {dst.name}  {before} → {after} bytes  (−{saved} bytes)")


def write_css_min(src: Path) -> None:
    if not src.exists() or src.suffix != '.css' or src.name.endswith('.min.css'):
        return
    dst = src.with_suffix('.min.css')
    code = src.read_text(encoding='utf-8')
    minified = cssmin(code)
    dst.write_text(minified, encoding='utf-8')
    before = len(code)
    after = len(minified)
    saved = before - after
    print(f"✓ {src.name} → {dst.name}  {before} → {after} bytes  (−{saved} bytes)")


def main() -> int:
    any_written = False
    # JS
    for f in JS_FILES:
        write_js_min(f)
        any_written = True
    # CSS (all first-party styles in static/css)
    if CSS_DIR.exists():
        for css in CSS_DIR.glob('*.css'):
            if css.name.endswith('.min.css'):
                continue
            write_css_min(css)
            any_written = True
    return 0 if any_written else 1


if __name__ == '__main__':
    raise SystemExit(main())
