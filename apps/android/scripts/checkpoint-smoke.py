"""Verify checkpoint/close/reopen after emulator-smoke.py's synthetic fixture flow."""

import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ADB = ROOT / ".tools/android/sdk/platform-tools/adb"
PACKAGE = "com.photofold.mediacleaner"
ENV = {**os.environ, "ANDROID_USER_HOME": str(ROOT / ".tools/android/user")}


def adb(*args):
    return (
        subprocess.check_output(
            [str(ADB), "-s", "emulator-5554", *args], env=ENV, timeout=60
        )
        .decode()
        .strip()
    )


def tree():
    adb("shell", "uiautomator", "dump", "/sdcard/window.xml")
    return ET.fromstring(adb("exec-out", "cat", "/sdcard/window.xml"))


def find(text, timeout=40, button=False):
    deadline, previous, direction = time.monotonic() + timeout, None, 1
    while time.monotonic() < deadline:
        root = tree()
        for node in root.iter("node"):
            if button and not node.get("class", "").endswith("Button"):
                continue
            if (
                text.casefold() in node.get("text", "").casefold()
                and node.get("enabled") == "true"
            ):
                return node
        current = ET.tostring(root)
        if current == previous:
            direction *= -1
        previous = current
        start, end = ("1950", "950") if direction == 1 else ("950", "1950")
        adb("shell", "input", "swipe", "550", start, "550", end, "350")
    raise AssertionError("Missing fixture control: " + text)


def tap(node):
    left, top, right, bottom = map(int, re.findall(r"\d+", node.get("bounds")))
    adb("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))


def close_at_checkpoint():
    tap(find("Settings", button=True))
    tap(find("Save checkpoint and shut down", button=True))
    tap(find("Save and shut down", button=True))
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if not any(node.get("package") == PACKAGE for node in tree().iter("node")):
            break
    else:
        raise AssertionError("Activity did not close after checkpoint")
    assert "ServiceRecord{" not in adb(
        "shell", "dumpsys", "activity", "services", PACKAGE
    ), "Scan service still running"


assert adb("emu", "avd", "name").splitlines()[0] == "media-cleaner-test", (
    "Synthetic test AVD only"
)
close_at_checkpoint()
adb("shell", "am", "start", "-n", PACKAGE + "/.MainActivity")
tap(find("Scanner", button=True))
tap(find("Scan options", button=True))
tap(find("Continue Scan"))
tap(find("Continue Scan", button=True))
find("Scan complete.", timeout=90)
close_at_checkpoint()
print(
    "Android checkpoint close/reopen/resume passed; activity closed and scan service stopped."
)
