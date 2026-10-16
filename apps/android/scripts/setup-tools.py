"""Install local Android tools, prompting for licenses unless explicitly accepted."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tarfile
import zipfile
from pathlib import Path

parser = argparse.ArgumentParser(
    description="Install local Android tools on macOS Apple Silicon."
)
parser.add_argument(
    "--accept-licenses",
    action="store_true",
    help="Accept Google's Android SDK licenses (https://developer.android.com/studio#terms-and-conditions).",
)
parser.add_argument(
    "--emulator",
    action="store_true",
    help="Also install the Android 35 ARM64 emulator and system image.",
)
args = parser.parse_args()

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / ".tools" / "android"
TOOLS.mkdir(parents=True, exist_ok=True)


def download(url, destination, checksum):
    if (
        not destination.exists()
        or hashlib.sha256(destination.read_bytes()).hexdigest() != checksum
    ):
        temporary = destination.with_suffix(".part")
        subprocess.run(
            [
                "curl",
                "--fail",
                "--location",
                "--retry",
                "3",
                "--silent",
                "--show-error",
                "--output",
                str(temporary),
                url,
            ],
            check=True,
        )
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != checksum:
            raise RuntimeError("Download checksum mismatch")
        temporary.replace(destination)


def unzip(archive, destination):
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            target = destination / item.filename
            if not target.resolve().is_relative_to(destination.resolve()):
                raise RuntimeError("Unsafe archive path")
            source.extract(item, destination)
            mode = item.external_attr >> 16
            if mode and target.is_file():
                target.chmod(mode & 0o777)


if platform.system() != "Darwin" or platform.machine() != "arm64":
    raise SystemExit(
        "This optional bootstrap targets macOS ARM64. On other platforms install JDK 21 and Android SDK, then set JAVA_HOME and ANDROID_HOME."
    )
java = TOOLS / "jdk" / "Contents" / "Home"
if not (java / "bin/java").exists():
    metadata = json.loads(
        subprocess.check_output(
            [
                "curl",
                "--fail",
                "--location",
                "--silent",
                "--show-error",
                "https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture=aarch64&image_type=jdk&os=mac&vendor=eclipse",
            ]
        )
    )[0]["binary"]["package"]
    archive = TOOLS / "jdk.tar.gz"
    download(metadata["link"], archive, metadata["checksum"])
    extract = TOOLS / "jdk-extract"
    extract.mkdir(exist_ok=True)
    with tarfile.open(archive) as source:
        source.extractall(extract, filter="data")
    next(extract.glob("jdk*")).rename(TOOLS / "jdk")
    extract.rmdir()
sdk = TOOLS / "sdk"
if not (sdk / "cmdline-tools/latest/bin/sdkmanager").exists():
    archive = TOOLS / "commandline.zip"
    download(
        "https://dl.google.com/android/repository/commandlinetools-mac_arm64-15859902_latest.zip",
        archive,
        "835b62a26162b229b441d1f6d4680383815a270809eb33522c0d480fa5002c4e",
    )
    extract = TOOLS / "cmdline-extract"
    unzip(archive, extract)
    (sdk / "cmdline-tools").mkdir(parents=True, exist_ok=True)
    (extract / "cmdline-tools").rename(sdk / "cmdline-tools/latest")
    extract.rmdir()
env = {
    **os.environ,
    "JAVA_HOME": str(java),
    "ANDROID_HOME": str(sdk),
    "ANDROID_USER_HOME": str(TOOLS / "user"),
    "PATH": str(java / "bin") + os.pathsep + os.environ["PATH"],
}
manager = str(sdk / "cmdline-tools/latest/bin/sdkmanager")
packages = {
    "platform-tools": sdk / "platform-tools/adb",
    "platforms;android-35": sdk / "platforms/android-35/android.jar",
    "build-tools;35.0.0": sdk / "build-tools/35.0.0/aapt",
}
if args.emulator:
    packages.update(
        {
            "emulator": sdk / "emulator/emulator",
            "system-images;android-35;google_apis;arm64-v8a": sdk
            / "system-images/android-35/google_apis/arm64-v8a/package.xml",
        }
    )
missing = [name for name, marker in packages.items() if not marker.exists()]
if missing:
    print(
        "SDK license: https://developer.android.com/studio#terms-and-conditions",
        flush=True,
    )
    options = {"input": "y\n" * 100} if args.accept_licenses else {}
    subprocess.run(
        [manager, "--sdk_root=" + str(sdk), *missing],
        text=True,
        env=env,
        check=True,
        **options,
    )
    if any(not marker.exists() for marker in packages.values()):
        raise SystemExit(
            "SDK setup is incomplete. Accept the requested SDK licenses and rerun setup."
        )
print("Android build tools ready under .tools/android. Run ./build-android.sh")
