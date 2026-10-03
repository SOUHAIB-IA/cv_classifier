"""Talking to the desktop: a notification, and showing a file in a window.

The same three gestures, three ways. Linux speaks D-Bus and xdg, Windows speaks
PowerShell and explorer, macOS speaks osascript and open. None of them is
essential: a notification that does not appear and a folder that does not open
are an inconvenience, not a failure, so every function here returns False rather
than raising. The caller carries on.

Kept beside browsers.py and locking.py, the other two places where one job has
three platform answers.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

SYSTEM = platform.system()          # "Linux" | "Windows" | "Darwin"

# A desktop notification is advisory, and a desktop that ignores it is normal.
_ICONS = {"filed": "document-save", "duplicate": "edit-copy",
          "lowconf": "dialog-question", "skipped": "dialog-information",
          "error": "dialog-error"}
_URGENCY = {"error": "critical", "lowconf": "normal"}


def _run(cmd: list[str], env: dict | None = None, timeout: int = 15) -> bool:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env)
        return r.returncode == 0
    except Exception:
        return False


def _ps_quote(s: str) -> str:
    """A PowerShell single-quoted string: the only escape inside one is ''."""
    return "'" + str(s).replace("'", "''") + "'"


def _osa_quote(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


# --------------------------------------------------------------- notification
def notify(kind: str, title: str, body: str = "", env: dict | None = None
           ) -> bool:
    """Show a desktop notification. False when the desktop has no way to."""
    if SYSTEM == "Linux":
        if not shutil.which("notify-send"):
            return False
        return _run(["notify-send", "-a", "cv-router",
                     "-i", _ICONS.get(kind, "document-save"),
                     "-u", _URGENCY.get(kind, "low"), title, body], env=env)

    if SYSTEM == "Darwin":
        if not shutil.which("osascript"):
            return False
        script = (f"display notification {_osa_quote(body)} "
                  f"with title {_osa_quote(title)}")
        return _run(["osascript", "-e", script], env=env)

    if SYSTEM == "Windows":
        # No dependency and no toast XML: a balloon from the tray area, which
        # every Windows since 7 has had. A real toast needs an AppUserModelID
        # the app does not own until it is installed, so it would show nothing.
        ps = (
            "[reflection.assembly]::LoadWithPartialName('System.Windows.Forms')"
            " > $null; $n = New-Object System.Windows.Forms.NotifyIcon;"
            " $n.Icon = [System.Drawing.SystemIcons]::Information;"
            f" $n.BalloonTipTitle = {_ps_quote(title)};"
            f" $n.BalloonTipText = {_ps_quote(body or ' ')};"
            " $n.Visible = $true; $n.ShowBalloonTip(5000);"
            " Start-Sleep -Milliseconds 5200; $n.Dispose()"
        )
        return _run(["powershell", "-NoProfile", "-NonInteractive",
                     "-Command", ps], env=env, timeout=20)
    return False


# ------------------------------------------------------------- showing a file
def reveal(path: Path, env: dict | None = None) -> tuple[bool, bool]:
    """Open a window with `path` selected.

    Returns (opened, selected). Selecting the file is the point — an employer's
    upload dialog opens wherever it last was, and a CV filed by date is several
    clicks away however well it is named — but a folder shown without the
    selection still beats nothing, so that is the fallback everywhere.
    """
    path = Path(path)
    folder = path.parent

    if SYSTEM == "Windows":
        # explorer returns 1 even when it worked, so its exit code says nothing.
        try:
            subprocess.Popen(["explorer", f"/select,{path}"], env=env)
            return True, True
        except Exception:
            return open_folder(folder, env), False

    if SYSTEM == "Darwin":
        if _run(["open", "-R", str(path)], env=env):
            return True, True
        return open_folder(folder, env), False

    # Linux: the file manager's own interface selects the file; xdg-open on the
    # folder is what a desktop without it can still do.
    if shutil.which("dbus-send") and _run(
            ["dbus-send", "--session",
             "--dest=org.freedesktop.FileManager1", "--type=method_call",
             "/org/freedesktop/FileManager1",
             "org.freedesktop.FileManager1.ShowItems",
             f"array:string:{path.as_uri()}", "string:"], env=env, timeout=20):
        return True, True
    return open_folder(folder, env), False


def open_folder(folder: Path, env: dict | None = None) -> bool:
    """Open a folder in the file manager. False when nothing can."""
    folder = str(folder)
    try:
        if SYSTEM == "Windows":
            subprocess.Popen(["explorer", folder], env=env)
            return True
        opener = "open" if SYSTEM == "Darwin" else "xdg-open"
        if not shutil.which(opener):
            return False
        subprocess.Popen([opener, folder], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


# ------------------------------------------------------------ service control
def service_manager() -> str | None:
    """"systemd" when the watcher runs as a service here, otherwise None.

    start.py runs the watcher in a thread, which has no service to restart. A
    button that calls systemctl then has nothing to act on, and on Windows and
    macOS it never had: better to say so than to fail.
    """
    if SYSTEM != "Linux" or not shutil.which("systemctl"):
        return None
    r = subprocess.run(["systemctl", "--user", "list-unit-files",
                        "cv-router-watcher.service"],
                       capture_output=True, text=True, timeout=10)
    return "systemd" if "cv-router-watcher.service" in (r.stdout or "") else None


def restart_watcher() -> tuple[bool, str]:
    """Restart the watcher service. (ok, message)"""
    if service_manager() != "systemd":
        return False, (
            "the watcher is not running as a service here. Started with "
            "`python start.py` it is a thread inside this application, so "
            "stop it with Ctrl+C and start it again.")
    r = subprocess.run(["systemctl", "--user", "restart",
                        "cv-router-watcher.service"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip()[:200] or "restart failed"
    return True, "restarted"
