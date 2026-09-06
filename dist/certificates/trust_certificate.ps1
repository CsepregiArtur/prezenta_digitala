param(
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
