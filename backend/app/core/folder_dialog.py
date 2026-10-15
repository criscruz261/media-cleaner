"""User-initiated native folder dialog. Never accepts executable shell input."""

import json
import shutil
import subprocess
import sys


def choose_directory() -> str | None:
    if sys.platform == "darwin":
        command = ["osascript", "-e", 'POSIX path of (choose folder with prompt "Choose a media folder")']
    elif sys.platform == "win32":
        script = 'Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.FolderBrowserDialog; if($d.ShowDialog() -eq "OK") { $d.SelectedPath }'
        command = ["powershell", "-NoProfile", "-STA", "-Command", script]
    elif shutil.which("zenity"):
        command = ["zenity", "--file-selection", "--directory", "--title=Choose a media folder"]
    elif shutil.which("kdialog"):
        command = ["kdialog", "--getexistingdirectory", str(__import__("pathlib").Path.home())]
    else:
        raise ValueError("No native folder dialog available. Install zenity/kdialog or paste a folder path.")
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise ValueError("Folder selection timed out. Try again or paste a path.")
    if process.returncode != 0:
        return None
    return process.stdout.strip() or None


if __name__ == "__main__":
    print(json.dumps({"path": choose_directory()}))
