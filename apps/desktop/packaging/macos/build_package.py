"""Build and verify a macOS app bundle, publishing only after the smoke test."""

import json
import platform
import shutil
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path


def main():
    if sys.platform != "darwin":
        raise SystemExit("macOS packaging must run on macOS.")
    root = Path(__file__).resolve().parents[4]
    backend = root / "apps/desktop/backend"
    frontend = root / "apps/desktop/frontend/dist"
    if not (frontend / "index.html").is_file():
        raise RuntimeError("Production frontend missing; run setup first.")
    from app.core.media_tools import executable
    from static_ffmpeg import run

    if not all(executable(name) for name in ("ffmpeg", "ffprobe")):
        run.get_or_fetch_platform_executables_else_raise()
    work_root = root / ".tools/macos-package"
    work_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="build-", dir=work_root) as temporary:
        work = Path(temporary)
        tools = work / "media-tools"
        tools.mkdir()
        for name in ("ffmpeg", "ffprobe"):
            source = executable(name)
            if not source:
                raise RuntimeError(f"Missing {name} after tool installation")
            shutil.copy2(source, tools / name)
        command = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--windowed",
            "--name",
            "MediaCleaner",
            "--osx-bundle-identifier",
            "com.mediacleaner.desktop",
            "--distpath",
            str(work / "dist"),
            "--workpath",
            str(work / "work"),
            "--specpath",
            str(work),
            "--paths",
            str(backend),
            "--add-data",
            f"{frontend}:frontend",
            "--add-data",
            f"{backend / 'migrations'}:migrations",
            "--add-binary",
            f"{tools / 'ffmpeg'}:media-tools",
            "--add-binary",
            f"{tools / 'ffprobe'}:media-tools",
        ]
        for package in (
            "app",
            "uvicorn",
            "alembic",
            "sqlalchemy",
            "PIL",
            "pillow_heif",
            "rawpy",
            "imagehash",
            "scipy",
            "pywt",
            "mediapipe",
        ):
            command += ["--collect-all", package]
        command += [str(Path(__file__).with_name("launcher.py"))]
        subprocess.run(command, check=True, cwd=root)
        bundle = work / "dist/MediaCleaner.app"
        # Preserve installed distribution metadata, including available license files.
        licenses = bundle / "Contents/Resources/third-party-licenses"
        licenses.mkdir()
        versions = {}
        for distribution in metadata.distributions():
            name = distribution.metadata.get("Name", "unknown")
            versions[name] = distribution.version
            for file in distribution.files or ():
                if ".dist-info/" in str(file).replace("\\", "/") and any(
                    word in str(file).lower()
                    for word in ("license", "copying", "notice", "metadata")
                ):
                    source = Path(distribution.locate_file(file))
                    if source.is_file():
                        destination = licenses / str(file)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, destination)
        (bundle / "Contents/Resources/build-info.json").write_text(
            json.dumps(
                {
                    "python": sys.version,
                    "architecture": platform.machine(),
                    "packages": versions,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        shutil.copy2(
            Path(__file__).with_name("README.txt"),
            bundle / "Contents/Resources/README.txt",
        )
        # Added notices change the sealed resources; sign the completed bundle again.
        subprocess.run(
            ["codesign", "--force", "--deep", "--sign", "-", str(bundle)], check=True
        )
        subprocess.run(
            ["codesign", "--verify", "--deep", "--strict", str(bundle)], check=True
        )
        # Run outside the repository and without developer Python/Node on PATH.
        import os

        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
        env.pop("MEDIA_CLEANER_DATA", None)
        subprocess.run(
            [str(bundle / "Contents/MacOS/MediaCleaner"), "--smoke-test"],
            cwd=work,
            env=env,
            check=True,
            timeout=120,
        )
        output = root / "deployment-package/macOS"
        output.mkdir(parents=True, exist_ok=True)
        # Publish only the app owned by this build; preserve unrelated output files.
        target = output / bundle.name
        if target.is_symlink():
            raise RuntimeError(
                "Refusing to replace a symlink at the package destination"
            )
        staged = output / ".MediaCleaner.app.staging"
        if staged.exists() or staged.is_symlink():
            raise RuntimeError(
                f"Remove the previous staging path before rebuilding: {staged}"
            )
        shutil.copytree(bundle, staged, symlinks=True)
        if target.exists():
            shutil.rmtree(target)
        staged.rename(target)
        shutil.copy2(Path(__file__).with_name("README.txt"), output / "README.txt")
        print(f"macOS package ready: {target}")


if __name__ == "__main__":
    main()
