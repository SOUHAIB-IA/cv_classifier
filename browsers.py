"""Finding Chrome, on whichever machine this is.

There were three copies of this list and none of them knew the name `chrome`,
which is what Windows calls the binary and what a CI runner puts on PATH. So the
same checkout rendered CVs on a developer's Linux box and failed to find a
browser everywhere else — with an error that blames the renderer rather than the
search.

One list, one set of well-known locations, three callers.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

# Order matters: a real Chrome before Chromium, and the bare name last so an
# unrelated `chrome` shim on PATH never wins over a proper install.
NAMES = ("google-chrome", "google-chrome-stable", "chromium",
         "chromium-browser", "chrome", "chrome.exe", "msedge")

# Windows and macOS keep the browser outside PATH more often than not.
WINDOWS_RELATIVE = (r"Google\Chrome\Application\chrome.exe",
                    r"Google\Chrome Beta\Application\chrome.exe",
                    r"Microsoft\Edge\Application\msedge.exe")
MACOS_PATHS = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
               "/Applications/Chromium.app/Contents/MacOS/Chromium",
               "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")


def find_chrome(preferred: str = "") -> str | None:
    """The browser to render with, or None. `preferred` is tried first."""
    for c in ([preferred] if preferred else []) + list(NAMES):
        if not c:
            continue
        if Path(c).is_file():
            return c
        p = shutil.which(c)
        if p:
            return p

    for base in (os.environ.get("PROGRAMFILES"),
                 os.environ.get("PROGRAMFILES(X86)"),
                 os.environ.get("LOCALAPPDATA")):
        if not base:
            continue
        for rel in WINDOWS_RELATIVE:
            p = Path(base) / rel
            if p.is_file():
                return str(p)

    for p in MACOS_PATHS:
        if Path(p).is_file():
            return p
    return None
