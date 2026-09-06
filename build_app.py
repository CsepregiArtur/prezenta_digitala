#!/usr/bin/env python3
"""
Build script v3.0.0 for Attendance Control.

Production build similar to the SMT-Line-Monitor pipeline, adapted to this
PySide6 attendance application:

  - prereq checks (Python/PyInstaller), optional clean
  - single-file or onedir PyInstaller build of the attendance kiosk EXE
  - Windows file version info (CompanyName / FileVersion / ProductName ...)
  - self-signed code-signing certificate (created once, CurrentUser) + signing
    with timestamp + signature verification
  - distribution folder (+ optional .zip): EXE + LICENSE / README / GUIDE + a
    build manifest with file hash and signature status
  - coloured, timestamped log and final summary

Run:            python build_app.py              # onefile + sign + package
                python build_app.py --onedir     # folder mode
                python build_app.py --no-sign    # skip signing (macOS/Linux)
See --help for every option.
"""

import argparse
import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Version & identity
# ---------------------------------------------------------------------------
APP_NAME = "AttendanceControl"          # EXE / PyInstaller name
PRODUCT_NAME = "Attendance Control"     # human-facing product name
COMPANY_NAME = "Csepregi Artur"
CONTACT_URL = "https://csepregiartur.github.io"
BUILD_SCRIPT_VERSION = "3.0.0"

ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
DISTRIBUTION_DIR = ROOT_DIR / "distribution"
ENTRY_SCRIPT = ROOT_DIR / "app" / "main.py"


def read_version() -> str:
    """Read __version__ from app/__init__.py (e.g. '1.0.0')."""
    init_py = ROOT_DIR / "app" / "__init__.py"
    if init_py.exists():
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_py.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    return "1.0.0"


VERSION = read_version()
COPYRIGHT = f"Copyright (c) {datetime.now().year} {COMPANY_NAME}. All rights reserved."
CERT_NAME = f"{PRODUCT_NAME} - {COMPANY_NAME}"
TIMESTAMP_SERVER = "http://timestamp.digicert.com"


class BuildColors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"


def _emit(text: str) -> None:
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"), flush=True)


def log(msg: str, level: str = "INFO") -> None:
    """Timestamped, colour-coded logging (ASCII symbols for console safety)."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    if level == "SUCCESS":
        _emit(f"{BuildColors.GREEN}[{timestamp}] [OK] {msg}{BuildColors.END}")
    elif level == "ERROR":
        _emit(f"{BuildColors.RED}[{timestamp}] [ERR] {msg}{BuildColors.END}")
    elif level == "WARNING":
        _emit(f"{BuildColors.YELLOW}[{timestamp}] [WARN] {msg}{BuildColors.END}")
    elif level == "STEP":
        _emit(f"\n{BuildColors.BLUE}{BuildColors.BOLD}>>> {msg}{BuildColors.END}")
    elif level == "INFO":
        _emit(f"[{timestamp}] {msg}")


def print_header() -> None:
    print(f"\n{BuildColors.HEADER}{BuildColors.BOLD}")
    print("=" * 70)
    print(f"  {PRODUCT_NAME} - Build script v{BUILD_SCRIPT_VERSION}")
    print("=" * 70)
    print(f"  Application v{VERSION}  |  {COPYRIGHT}")
    print("=" * 70)
    print(f"{BuildColors.END}")


# ============================================================================
# STEP 0: PREREQUISITES
# ============================================================================
def check_prerequisites() -> Tuple[bool, Optional[str]]:
    log("CHECKING PREREQUISITES", "STEP")
    log(f"Python: {sys.version.split()[0]}")
    missing = []

    try:
        import PyInstaller
        log(f"PyInstaller {PyInstaller.__version__}", "SUCCESS")
    except ImportError:
        log("PyInstaller is not installed (pip install pyinstaller)", "ERROR")
        missing.append("pyinstaller")

    for path, description in [(ENTRY_SCRIPT, "main entry"), (ROOT_DIR / "config.json", "config")]:
        if path.exists():
            log(f"Found: {path.name} ({description})", "SUCCESS")
        else:
            log(f"Missing: {path} ({description})", "ERROR")
            missing.append(path.name)

    if missing:
        log(f"Missing prerequisites: {', '.join(missing)}", "ERROR")
        return False, None
    return True, None


# ============================================================================
# STEP 0.5: CLEAN
# ============================================================================
def clean_build() -> None:
    log("CLEANING PREVIOUS BUILDS", "STEP")
    for folder in (BUILD_DIR, DIST_DIR, DISTRIBUTION_DIR):
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
            log(f"Removed: {folder}/", "SUCCESS")
    for spec in glob.glob(str(ROOT_DIR / "*.spec")):
        try:
            os.remove(spec)
            log(f"Removed: {Path(spec).name}", "SUCCESS")
        except OSError:
            pass
    for cache in ROOT_DIR.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


# ============================================================================
# STEP 1: VERSION INFO (Windows)
# ============================================================================
def version_tuple() -> Tuple[int, int, int, int]:
    parts = re.findall(r"\d+", VERSION)
    parts = (list(map(int, parts)) + [0, 0, 0, 0])[:4]
    return tuple(parts)  # type: ignore[return-value]


def create_version_info() -> Optional[Path]:
    """Create version_info.txt consumed by PyInstaller --version-file."""
    if sys.platform != "win32":
        log("Version file skipped (Windows only)", "WARNING")
        return None
    log("CREATING VERSION INFORMATION", "STEP")
    filevers = ", ".join(str(p) for p in version_tuple())
    content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({filevers}),
    prodvers=({filevers}),
    mask=0x3f,
    flags=0x0,
    OS=0x4,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'{COMPANY_NAME}'),
        StringStruct(u'FileDescription', u'{PRODUCT_NAME} - Employee time tracking kiosk'),
        StringStruct(u'FileVersion', u'{VERSION}'),
        StringStruct(u'InternalName', u'{APP_NAME}'),
        StringStruct(u'LegalCopyright', u'{COPYRIGHT}'),
        StringStruct(u'OriginalFilename', u'{APP_NAME}.exe'),
        StringStruct(u'ProductName', u'{PRODUCT_NAME}'),
        StringStruct(u'ProductVersion', u'{VERSION}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    version_file = ROOT_DIR / "version_info.txt"
    version_file.write_text(content, encoding="utf-8")
    log(f"Version info written: {version_file.name}", "SUCCESS")
    return version_file


# ============================================================================
# STEP 2: BUILD EXECUTABLE
# ============================================================================
def build_executable(onefile: bool) -> Tuple[bool, Optional[Path]]:
    log("BUILDING EXECUTABLE", "STEP")
    if not ENTRY_SCRIPT.exists():
        log(f"Entry script not found: {ENTRY_SCRIPT}", "ERROR")
        return False, None

    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", APP_NAME,
        "--windowed",
        "--add-data", f"config.json{sep}.",
    ]
    for module in ("serial", "openpyxl", "barcode", "PIL"):
        cmd.append(f"--hidden-import={module}")

    version_file = create_version_info()
    if version_file:
        cmd.append(f"--version-file={version_file}")

    cmd.append("--onefile" if onefile else "--onedir")
    cmd.append(str(ENTRY_SCRIPT))

    log("Running PyInstaller... (this can take several minutes)", "INFO")
    log("Command: " + " ".join(cmd), "INFO")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if result.returncode != 0:
        log(f"PyInstaller failed with exit code {result.returncode}", "ERROR")
        return False, None

    if onefile:
        exe_path = DIST_DIR / f"{APP_NAME}.exe"
    else:
        exe_path = DIST_DIR / APP_NAME / f"{APP_NAME}.exe"
    if not exe_path.exists():
        found = list(DIST_DIR.rglob("*.exe"))
        exe_path = found[0] if found else None
    if not exe_path:
        log("Executable was not produced", "ERROR")
        return False, None
    log(f"Executable created: {exe_path} ({exe_path.stat().st_size / 1_048_576:.1f} MB)", "SUCCESS")
    return True, exe_path


# ============================================================================
# STEP 3: CODE SIGNING (Windows)
# ============================================================================
def _powershell(script: str, timeout: int = 180):
    """Run a PowerShell snippet non-interactively with a hard timeout."""
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        log("PowerShell step timed out", "WARNING")
        return None
    except Exception as error:  # noqa: BLE001
        log(f"PowerShell could not start: {error}", "WARNING")
        return None


def copy_release_docs(exe_path: Path) -> None:
    """Copy the licensing/documentation files next to the EXE (like build_exe.bat)."""
    log("COPYING RELEASE DOCUMENTS", "STEP")
    target_dir = exe_path.parent
    for source_name, dest_name in [("LICENSE", "LICENSE.txt"), ("README.md", "README.md"), ("GUIDE.md", "GUIDE.md")]:
        source = ROOT_DIR / source_name
        if source.exists():
            shutil.copy2(source, target_dir / dest_name)
            log(f"Copied: {dest_name} -> {target_dir}", "SUCCESS")
        else:
            log(f"Missing source document: {source}", "WARNING")


TRUST_PS1 = r'''param(
    [string]$CertPath = (Join-Path $PSScriptRoot 'AttendanceControl_codesigning.cer'),
    [switch]$CurrentUserOnly
)
# Installs the Attendance Control code-signing certificate as trusted so the
# signed EXE shows its real publisher (no "Unknown publisher") on this PC.
$ErrorActionPreference = 'Stop'
if (-not (Test-Path $CertPath)) { Write-Host "Certificate not found: $CertPath"; exit 1 }
$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($CertPath)
$storeLocation = if ($CurrentUserOnly) { 'CurrentUser' } else { 'LocalMachine' }
try {
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root', $storeLocation)
    $store.Open('ReadWrite')
    $present = $store.Certificates | Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
    if ($present) { Write-Host "[OK] Already trusted: $($cert.Subject)" }
    else {
        $store.Add($cert)
        Write-Host "[OK] Trusted on this machine: $($cert.Subject)"
    }
    $store.Close()
    $exe = Join-Path $PSScriptRoot '..\AttendanceControl.exe'
    if (Test-Path $exe) {
        $sig = Get-AuthenticodeSignature $exe
        Write-Host "Signature on AttendanceControl.exe: $($sig.Status)  ($($sig.SignerCertificate.Subject))"
    }
}
catch {
    Write-Host "[ERR] $($_.Exception.Message)"
    Write-Host "Tip: run as Administrator to trust for all users, or use -CurrentUserOnly for just this user."
    exit 1
}
'''

INSTALL_TXT = """Attendance Control - code signing trust (free, internal deployment)
====================================================================

The AttendanceControl.exe is signed with a certificate issued by you
(Csepregi Artur). Because the certificate is self-signed, other Windows PCs do
not trust it yet and may show "Unknown publisher".

Fix it once per PC (free, no public CA needed):
  1. Copy this 'certificates' folder (or the whole distribution) to the PC.
  2. Run as Administrator (trusts the certificate for all users on that PC):

       powershell -ExecutionPolicy Bypass -File trust_certificate.ps1

     or for just the current user (no admin needed):

       powershell -ExecutionPolicy Bypass -File trust_certificate.ps1 -CurrentUserOnly

After that, right-click AttendanceControl.exe > Properties > Digital Signatures
shows: "The digital signature is OK" and the publisher = Attendance Control -
Csepregi Artur. No more "Unknown publisher".

For fleets/domains: instead of running the script by hand, push the .cer into
"Trusted Root Certification Authorities" via Group Policy (Computer
Configuration > Windows Settings > Security Settings > Public Key Policies),
or with a one-line software-deployment command. That does the same thing.

Note: this trusts YOUR certificate only on PCs you control. It is not the same
as a commercial CA signature recognised by every Windows PC on the internet
(those certificates are paid).
"""


def publish_certificate_tools() -> bool:
    """Export the public .cer + the trust script so other PCs can trust it."""
    if sys.platform != "win32":
        return False
    log("PUBLISHING CERTIFICATE / TRUST TOOL", "STEP")
    cert_dir = DIST_DIR / "certificates"
    cert_dir.mkdir(parents=True, exist_ok=True)
    cer_path = cert_dir / "AttendanceControl_codesigning.cer"
    export = r'''
$certName = '@@CERT_NAME@@'
$out = '@@CER@@'
$c = Get-ChildItem -Path 'Cert:\CurrentUser\My' -CodeSigningCert | Where-Object { $_.Subject -like "*$certName*" } | Select-Object -First 1
if (-not $c) { Write-Output 'CERT_NOT_FOUND'; exit 1 }
[IO.File]::WriteAllBytes($out, $c.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert))
Write-Output ("CERT_EXPORTED=" + $out)
exit 0
'''.replace("@@CERT_NAME@@", CERT_NAME).replace("@@CER@@", str(cer_path))
    result = _powershell(export, timeout=60)
    if result is None or result.returncode != 0 or not cer_path.exists():
        log("Could not export the certificate", "WARNING")
        return False
    log(f"Exported: {cer_path.name}", "SUCCESS")
    (cert_dir / "trust_certificate.ps1").write_text(TRUST_PS1, encoding="utf-8")
    (cert_dir / "INSTALL.txt").write_text(INSTALL_TXT, encoding="utf-8")
    log("Written: trust_certificate.ps1 + INSTALL.txt", "SUCCESS")
    return True


def create_self_signed_certificate() -> bool:
    """Find (or create) the code-signing certificate and make it trusted.

    The certificate lives in Cert:\\CurrentUser\\My. For Get-AuthenticodeSignature
    to report ``Valid`` it must also be trusted, so it is mirrored into the
    CurrentUser Root store (no admin rights needed).
    """
    if sys.platform != "win32":
        log("Code signing skipped (Windows only)", "WARNING")
        return False
    log("CHECKING CODE SIGNING CERTIFICATE", "STEP")
    script = r'''
$ErrorActionPreference = 'Stop'
$certName = '@@CERT_NAME@@'
$company = '@@COMPANY@@'
try {
  $cert = Get-ChildItem -Path 'Cert:\CurrentUser\My' -CodeSigningCert | Where-Object { $_.Subject -like "*$certName*" } | Select-Object -First 1
  if (-not $cert) {
    Write-Output 'CERT_CREATING_NEW'
    $cert = New-SelfSignedCertificate -Subject ("CN=" + $certName + ", O=" + $company) `
      -Type CodeSigningCert -CertStoreLocation 'Cert:\CurrentUser\My' `
      -KeyExportPolicy Exportable -KeySpec Signature -KeyLength 2048 `
      -HashAlgorithm SHA256 -NotAfter (Get-Date).AddYears(5)
    Write-Output ("CERT_CREATED=" + $cert.Subject)
  } else {
    Write-Output ("CERT_FOUND=" + $cert.Subject)
  }
  # Make the certificate trusted for this user so signatures verify as Valid.
  $inRoot = Get-ChildItem -Path 'Cert:\CurrentUser\Root' | Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
  if (-not $inRoot) {
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root','CurrentUser')
    $store.Open('ReadWrite')
    $store.Add($cert)
    $store.Close()
    Write-Output 'CERT_TRUSTED'
  } else {
    Write-Output 'CERT_ALREADY_TRUSTED'
  }
  Write-Output ("CERT_THUMB=" + $cert.Thumbprint)
  Write-Output ("CERT_EXPIRY=" + $cert.NotAfter.ToString('yyyy-MM-dd'))
  exit 0
} catch {
  Write-Output ("CERT_ERROR=" + $_.Exception.Message)
  exit 1
}
'''.replace("@@CERT_NAME@@", CERT_NAME).replace("@@COMPANY@@", COMPANY_NAME)
    result = _powershell(script, timeout=240)
    if result is None:
        return False
    for line in result.stdout.splitlines():
        if line.startswith("CERT_"):
            log(line, "INFO")
    if result.stderr and "CERT_ERROR" not in result.stdout:
        log(result.stderr.strip(), "WARNING")
    if result.returncode == 0:
        return True
    log("Certificate step failed", "WARNING")
    return False


def _sign_once(exe_path: Path, use_timestamp: bool) -> bool:
    """One signing attempt. Returns True when Authenticode reports Valid."""
    ts_arg = f"-TimestampServer '{TIMESTAMP_SERVER}'" if use_timestamp else ""
    script = r'''
$ErrorActionPreference = 'Stop'
$exe = '@@EXE@@'
$certName = '@@CERT_NAME@@'
try {
  if (-not (Test-Path $exe)) { Write-Output 'SIGN_NO_EXE'; exit 1 }
  $cert = Get-ChildItem -Path 'Cert:\CurrentUser\My' -CodeSigningCert | Where-Object { $_.Subject -like "*$certName*" } | Select-Object -First 1
  if (-not $cert) { $cert = Get-ChildItem -Path 'Cert:\CurrentUser\My' -CodeSigningCert | Select-Object -First 1 }
  if (-not $cert) { Write-Output 'SIGN_NO_CERT'; exit 2 }
  $sig = Set-AuthenticodeSignature -FilePath $exe -Certificate $cert @@TS_ARG@@ -HashAlgorithm SHA256
  Write-Output ("SIGN_STATUS=" + $sig.Status)
  if ($sig.SignerCertificate) { Write-Output ("SIGN_SIGNER=" + $sig.SignerCertificate.Subject) }
  if ($sig.Status -eq 'Valid') { exit 0 } else { Write-Output ("SIGN_DETAIL=" + $sig.StatusMessage); exit 3 }
} catch {
  Write-Output ("SIGN_ERROR=" + $_.Exception.Message)
  exit 4
}
'''.replace("@@EXE@@", str(exe_path)).replace("@@CERT_NAME@@", CERT_NAME).replace("@@TS_ARG@@", ts_arg)
    result = _powershell(script, timeout=240)
    if result is None:
        return False
    for line in result.stdout.splitlines():
        if line.startswith("SIGN_"):
            log(line, "INFO")
    return result.returncode == 0


def sign_executable(exe_path: Path) -> bool:
    if sys.platform != "win32":
        return False
    log("SIGNING EXECUTABLE", "STEP")
    if _sign_once(exe_path, use_timestamp=True):
        log("Executable signed successfully (with timestamp)", "SUCCESS")
        return True
    # Offline or a blocked timestamp server: sign again without a timestamp.
    log("Timestamped signing failed - retrying without a timestamp", "WARNING")
    if _sign_once(exe_path, use_timestamp=False):
        log("Executable signed successfully (no timestamp)", "SUCCESS")
        return True
    log("Signing did not reach a Valid status", "WARNING")
    return False


def verify_signature(exe_path: Path) -> bool:
    if sys.platform != "win32":
        return False
    log("VERIFYING SIGNATURE", "STEP")
    script = r'''
$exe = '@@EXE@@'
$sig = Get-AuthenticodeSignature -FilePath $exe
Write-Output ("VERIFY_STATUS=" + $sig.Status)
Write-Output ("VERIFY_MESSAGE=" + $sig.StatusMessage)
if ($sig.SignerCertificate) {
  Write-Output ("VERIFY_SIGNER=" + $sig.SignerCertificate.Subject)
  Write-Output ("VERIFY_VALID_FROM=" + $sig.SignerCertificate.NotBefore.ToString('yyyy-MM-dd'))
  Write-Output ("VERIFY_VALID_TO=" + $sig.SignerCertificate.NotAfter.ToString('yyyy-MM-dd'))
}
if ($sig.Status -eq 'Valid') { exit 0 } else { exit 1 }
'''.replace("@@EXE@@", str(exe_path))
    result = _powershell(script, timeout=120)
    if result is None:
        return False
    for line in result.stdout.splitlines():
        if line.startswith("VERIFY_"):
            log(line, "INFO")
    if result.returncode == 0:
        log("Signature is VALID", "SUCCESS")
        return True
    log("Signature is not valid (self-signed certs must be trusted on the target machine)", "WARNING")
    return False


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ============================================================================
# STEP 4: DISTRIBUTION PACKAGE
# ============================================================================
def create_distribution_package(exe_path: Path, onefile: bool, signed: bool, make_zip: bool) -> bool:
    log("CREATING DISTRIBUTION PACKAGE", "STEP")
    pkg_dir = DISTRIBUTION_DIR / f"{APP_NAME}_v{VERSION}"
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir, ignore_errors=True)
    pkg_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(exe_path, pkg_dir / exe_path.name)
    log(f"Copied: {exe_path.name}", "SUCCESS")

    if not onefile:
        internal = exe_path.parent / "_internal"
        if internal.exists():
            shutil.copytree(internal, pkg_dir / "_internal", dirs_exist_ok=True)
            log(f"Copied: _internal/ ({sum(1 for _ in internal.rglob('*'))} files)", "SUCCESS")

    docs = [("LICENSE", "LICENSE.txt"), ("README.md", "README.md"), ("GUIDE.md", "GUIDE.md")]
    for source_name, dest_name in docs:
        source = ROOT_DIR / source_name
        if source.exists():
            shutil.copy2(source, pkg_dir / dest_name)
            log(f"Copied: {dest_name}", "SUCCESS")

    certificates = exe_path.parent / "certificates"
    if certificates.exists():
        shutil.copytree(certificates, pkg_dir / "certificates", dirs_exist_ok=True)
        log("Copied: certificates/ (signing trust tool)", "SUCCESS")

    manifest = pkg_dir / "build_info.txt"
    signature_status = "Signed (self-signed, see below)" if signed else "NOT signed"
    manifest.write_text(
        "\n".join([
            f"Product: {PRODUCT_NAME}",
            f"Version: {VERSION}",
            f"Built:   {datetime.now():%Y-%m-%d %H:%M:%S}",
            f"Python:  {sys.version.split()[0]}",
            f"Copyright: {COPYRIGHT}",
            f"Contact: {CONTACT_URL}",
            "",
            f"Executable: {exe_path.name}",
            f"SHA256: {sha256_of(exe_path)}",
            f"Digital signature: {signature_status}",
            "Verify: right-click the EXE -> Properties -> Digital Signatures.",
            "",
            "Self-signed certificates are not issued by a public CA, so Windows may",
            "still warn 'unknown publisher'. The signature confirms the file has not",
            "been modified since it was built on this machine.",
            "",
            "Distribution contents:",
            "  AttendanceControl.exe  the application (needs the other files' folder)",
            "  LICENSE.txt / README.md / GUIDE.md   licensing & documentation",
        ]) + "\n",
        encoding="utf-8",
    )
    log("Written: build_info.txt", "SUCCESS")

    if make_zip:
        zip_path = DISTRIBUTION_DIR / f"{APP_NAME}_v{VERSION}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in pkg_dir.rglob("*"):
                if file.is_file():
                    archive.write(file, file.relative_to(pkg_dir))
        log(f"Created: {zip_path.name}", "SUCCESS")

    total = sum(f.stat().st_size for f in pkg_dir.rglob("*") if f.is_file())
    log(f"Distribution package ready: {pkg_dir} ({total / 1_048_576:.1f} MB)", "SUCCESS")
    return True


# ============================================================================
# STEP 5: POST-BUILD CLEANUP
# ============================================================================
def post_build_cleanup(keep_spec: bool = False) -> None:
    log("POST-BUILD CLEANUP", "STEP")
    for path in [ROOT_DIR / "version_info.txt"]:
        if path.exists():
            path.unlink()
            log(f"Removed: {path.name}", "SUCCESS")
    if not keep_spec:
        for spec in glob.glob(str(ROOT_DIR / "*.spec")):
            try:
                os.remove(spec)
                log(f"Removed: {Path(spec).name}", "SUCCESS")
            except OSError:
                pass


# ============================================================================
# MAIN
# ============================================================================
def main() -> None:
    print_header()
    parser = argparse.ArgumentParser(description=f"Build {PRODUCT_NAME} (Attendance Control)")
    parser.add_argument("--onedir", action="store_true", help="Folder build instead of a single-file EXE")
    parser.add_argument("--skip-clean", action="store_true", help="Do not delete previous build/dist folders")
    parser.add_argument("--no-sign", action="store_true", help="Skip code signing and verification")
    parser.add_argument("--no-verify", action="store_true", help="Skip signature verification after signing")
    parser.add_argument("--no-package", action="store_true", help="Skip the distribution package")
    parser.add_argument("--no-zip", action="store_true", help="Skip creating the .zip of the distribution")
    parser.add_argument("--keep-spec", action="store_true", help="Keep the generated PyInstaller .spec file")
    parser.add_argument("--skip-prereq", action="store_true", help="Skip the prerequisite checks")
    parser.add_argument("--sign-existing", action="store_true",
                        help="Sign, document and package the already-built dist EXE (skip PyInstaller)")
    args = parser.parse_args()

    started = datetime.now()
    signed = False
    onefile = not args.onedir

    if args.sign_existing:
        log("SIGN-EXISTING MODE - using the current dist executable", "STEP")
        exe_path = DIST_DIR / f"{APP_NAME}.exe"
        if not exe_path.exists() and DIST_DIR.exists():
            candidates = list(DIST_DIR.rglob("*.exe"))
            exe_path = candidates[0] if candidates else None
        if exe_path is None or not exe_path.exists():
            log("No existing executable found - run the full build first (no --sign-existing)", "ERROR")
            sys.exit(1)
        log(f"Using existing executable: {exe_path}", "SUCCESS")
    else:
        if not args.skip_prereq:
            ok, _ = check_prerequisites()
            if not ok:
                log("Prerequisite check failed", "ERROR")
                sys.exit(1)

        if not args.skip_clean:
            clean_build()
        else:
            log("Skipping clean (--skip-clean)", "WARNING")

        ok, exe_path = build_executable(onefile=onefile)
        if not ok or exe_path is None:
            log("Build failed - cannot continue", "ERROR")
            sys.exit(1)

    # Always drop the release documents next to the EXE (as build_exe.bat did).
    copy_release_docs(exe_path)

    if not args.no_sign:
        if create_self_signed_certificate() and sign_executable(exe_path):
            signed = True
            if not args.no_verify:
                verify_signature(exe_path)
            publish_certificate_tools()
        else:
            log("Signing skipped or not valid", "WARNING")
    else:
        log("Skipping code signing (--no-sign)", "WARNING")

    if not args.no_package:
        create_distribution_package(exe_path, onefile=onefile, signed=signed, make_zip=not args.no_zip)
    else:
        log("Skipping distribution package (--no-package)", "WARNING")

    post_build_cleanup(keep_spec=args.keep_spec)

    duration = datetime.now() - started
    print(f"\n{BuildColors.GREEN}{BuildColors.BOLD}")
    print("=" * 70)
    print(f"  BUILD COMPLETE - {PRODUCT_NAME} v{VERSION}")
    print("=" * 70)
    print(f"{BuildColors.END}")
    print(f"  Executable : {exe_path} ({exe_path.stat().st_size / 1_048_576:.1f} MB)")
    print(f"  Signature  : {'signed' if signed else 'unsigned'}")
    print(f"  Build time : {duration.total_seconds():.1f} s")
    print(f"  Documents  : copied next to the EXE in {exe_path.parent}")
    if not args.no_package:
        print(f"  Package    : {DISTRIBUTION_DIR}")
    print()


if __name__ == "__main__":
    main()
