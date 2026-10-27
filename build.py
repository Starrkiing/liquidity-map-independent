#!/usr/bin/env python3
"""Build the static GitHub Pages site without requiring any server runtime."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent
dist = root / "dist"
dist.mkdir(exist_ok=True)
shutil.copyfile(root / "site" / "index.html", dist / "index.html")
(dist / ".nojekyll").write_text("", encoding="utf-8")
print("Static site built:", dist / "index.html")
