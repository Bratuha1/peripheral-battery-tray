"""Build a one-file Windows EXE, portable ZIP and optional per-user installer."""

import argparse
import hashlib
from importlib import metadata
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from settings import APP_NAME, VERSION


def copy_licenses(directory):
    directory.mkdir(parents=True, exist_ok=True)
    names = [line.split("==", 1)[0] for line in (ROOT / "requirements.txt").read_text().splitlines()
             if "==" in line]
    names.append("pyinstaller")
    for name in names:
        distribution = metadata.distribution(name)
        for item in distribution.files or ():
            if item.parts[0].endswith(".dist-info") and (
                "licenses" in item.parts or item.name.lower().startswith(("license", "copying", "notice"))
            ):
                target = directory / name / Path(*item.parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(distribution.locate_file(item), target)
    python = Path(sys.base_prefix)
    shutil.copyfile(python / "LICENSE.txt", directory / "Python-LICENSE.txt")
    for path in (python / "tcl").glob("*/license.terms"):
        shutil.copyfile(path, directory / f"{path.parent.name}-LICENSE.txt")


def write_version(path):
    numbers = tuple(map(int, VERSION.split("."))) + (0,)
    path.write_text(f"""VSVersionInfo(
    ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f,
                      flags=0x0, OS=0x40004, fileType=0x1, subtype=0, date=(0, 0)),
    kids=[
        StringFileInfo([StringTable('040904B0', [
            StringStruct('CompanyName', 'Peripheral Battery Tray contributors'),
            StringStruct('FileDescription', '{APP_NAME}'),
            StringStruct('FileVersion', '{VERSION}'),
            StringStruct('OriginalFilename', 'PeripheralBatteryTray.exe'),
            StringStruct('ProductName', '{APP_NAME}'),
            StringStruct('ProductVersion', '{VERSION}')
        ])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])])
    ]
)
""", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iscc", type=Path, help="path to Inno Setup ISCC.exe")
    args = parser.parse_args()
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        parser.error("Use 64-bit Python on Windows.")
    if args.iscc is not None and not args.iscc.is_file():
        parser.error("ISCC.exe was not found.")

    build = ROOT / "build"
    licenses = build / "licenses"
    copy_licenses(licenses)
    write_version(build / "version.txt")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "packaging/PeripheralBatteryTray.spec"], cwd=ROOT, check=True,
    )
    exe = ROOT / "dist" / "PeripheralBatteryTray.exe"
    release = ROOT / "dist" / f"release-{VERSION}"
    release.mkdir(exist_ok=True)
    portable = release / f"PeripheralBatteryTray-{VERSION}-windows-x64-portable.zip"
    with ZipFile(portable, "w", ZIP_DEFLATED) as archive:
        archive.write(exe, exe.name)
        for name in ("LICENSE", "README.md", "docs/ru.md", "devices.example.toml"):
            archive.write(ROOT / name, name)
        for license_file in sorted(licenses.rglob("*")):
            if license_file.is_file():
                archive.write(license_file, license_file.relative_to(build))

    artifacts = [portable]
    if args.iscc is not None:
        subprocess.run(
            [str(args.iscc.resolve()), f"/DAppVersion={VERSION}", f"/DReleaseDir={release}",
             str(ROOT / "packaging" / "setup.iss")], check=True, cwd=ROOT,
        )
        artifacts.append(release / f"PeripheralBatteryTray-{VERSION}-windows-x64-setup.exe")
    with (release / "SHA256SUMS.txt").open("w", encoding="utf-8", newline="\n") as handle:
        for artifact in [exe, *artifacts]:
            with artifact.open("rb") as payload:
                digest = hashlib.file_digest(payload, "sha256").hexdigest()
            handle.write(f"{digest}  {artifact.name}\n")
    print(f"{exe.name}: {exe.stat().st_size:,} bytes")
    for artifact in artifacts:
        print(f"{artifact.name}: {artifact.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
