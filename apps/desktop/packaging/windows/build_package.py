"""Build and verify a portable folder, publishing only after the smoke test."""
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from importlib import metadata
from pathlib import Path


def main():
    if sys.platform != "win32":
        raise SystemExit("Windows packaging must run on Windows.")
    version = datetime.now().strftime("%y%m%d%H%M")
    app_name = f"MediaCleaner-{version}-windows"
    root = Path(__file__).resolve().parents[4]
    backend = root / "apps/desktop/backend"
    frontend = root / "apps/desktop/frontend/dist"
    if not (frontend / "index.html").is_file():
        raise RuntimeError("Production frontend missing; run setup first.")
    from app.core.media_tools import executable
    from static_ffmpeg import run

    if not all(executable(name) for name in ("ffmpeg", "ffprobe")):
        run.get_or_fetch_platform_executables_else_raise()
    work_root = root / ".tools/windows-package"
    work_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="build-", dir=work_root) as temporary:
        work = Path(temporary)
        tools = work / "media-tools"
        tools.mkdir()
        for name in ("ffmpeg", "ffprobe"):
            source = executable(name)
            if not source:
                raise RuntimeError(f"Missing {name} after tool installation")
            shutil.copy2(source, tools / (name + ".exe"))
        command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console", "--name", app_name,
                   "--distpath", str(work / "dist"), "--workpath", str(work / "work"), "--specpath", str(work),
                   "--paths", str(backend), "--add-data", f"{frontend};frontend",
                   "--add-data", f"{backend / 'migrations'};migrations", "--add-data", f"{tools};media-tools"]
        for package in ("app", "uvicorn", "alembic", "sqlalchemy", "PIL", "pillow_heif", "rawpy", "imagehash", "scipy", "pywt", "mediapipe"):
            command += ["--collect-all", package]
        command += [str(Path(__file__).with_name("launcher.py"))]
        subprocess.run(command, check=True, cwd=root)
        bundle = work / "dist" / app_name
        # Preserve installed distribution metadata, including available license files.
        licenses = bundle / "third-party-licenses"
        licenses.mkdir()
        versions = {}
        for distribution in metadata.distributions():
            name = distribution.metadata.get("Name", "unknown")
            versions[name] = distribution.version
            for file in distribution.files or ():
                if ".dist-info/" in str(file).replace("\\", "/") and any(word in str(file).lower() for word in ("license", "copying", "notice", "metadata")):
                    source = Path(distribution.locate_file(file))
                    if source.is_file():
                        destination = licenses / str(file)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, destination)
        (bundle / "build-info.json").write_text(json.dumps({"version": version, "python": sys.version, "architecture": platform.machine(), "packages": versions}, indent=2), encoding="utf-8")
        shutil.copy2(Path(__file__).with_name("README.txt"), bundle / "README.txt")
        readme = bundle / "README.txt"
        readme.write_text(readme.read_text().replace("MediaCleaner.exe", f"{app_name}.exe"), encoding="utf-8")
        # Run outside the repository and without developer Python/Node on PATH.
        import os
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env["PATH"] = str(Path(env.get("SystemRoot", "C:/Windows")) / "System32")
        subprocess.run([str(bundle / f"{app_name}.exe"), "--smoke-test"], cwd=work, env=env, check=True, timeout=120)
        output = root / "deployment-package/windows" / app_name
        output.mkdir(parents=True, exist_ok=True)
        # Replace only build-owned paths. Keep .gitkeep and unrelated files.
        for item in bundle.iterdir():
            target = output / item.name
            if target.is_dir():
                if target.resolve().parent != output.resolve():
                    raise RuntimeError("Refusing to remove a path outside package output")
                shutil.rmtree(target)
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
        archive = shutil.make_archive(str(output), "zip", root_dir=output.parent, base_dir=output.name)
        print(f"Windows package ready: {archive}")


if __name__ == "__main__":
    main()
