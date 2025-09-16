Param(
  [string]$Domain = "anp.local.test",
  [string]$OutDir = "config/certs",
  [int]$Port = 443
)

$ErrorActionPreference = 'Stop'

Write-Host "[dev-up] Domain: $Domain OutDir: $OutDir Port: $Port"

# Ensure venv python is used if available
function Resolve-Python {
  if (Test-Path "venv/Scripts/python.exe") { return "venv/Scripts/python.exe" }
  return "python"
}

$py = Resolve-Python

# Generate certs if missing
if (-not (Test-Path "$OutDir/server.crt") -or -not (Test-Path "$OutDir/server.key")) {
  Write-Host "[dev-up] Generating certificates..."
  & $py scripts/gen_dev_certs.py --domain $Domain --out $OutDir
}

$certPath = Resolve-Path "$OutDir/server.crt"
$keyPath  = Resolve-Path "$OutDir/server.key"

Write-Host "[dev-up] Using cert: $certPath"
Write-Host "[dev-up] Using key : $keyPath"

# Checklist for hosts mapping
$hosts = "$env:SystemRoot\System32\drivers\etc\hosts"
Write-Host "[dev-up] Ensure hosts file contains: 127.0.0.1`t$Domain"
Write-Host "           Hosts file: $hosts"

Write-Host "[dev-up] Ensure the certificate is trusted (Trusted Root Certification Authorities)."
Write-Host "           Open 'certmgr.msc' and import $certPath into 'Trusted Root Certification Authorities' > 'Certificates'"

# Set env for the ANP server process
$env:ANP_SSL_CERT = "$certPath"
$env:ANP_SSL_KEY  = "$keyPath"
$env:ANP_HOST     = "0.0.0.0"
$env:ANP_PORT     = "$Port"
$env:ANP_SERVER_DOMAIN = "did:wba:$Domain:anp-server"
$env:ANP_CLIENT_DOMAIN = "$Domain"
$env:ANP_DEV_LOCAL_RESOLVER = "false"

Write-Host "[dev-up] Starting ANP SDK server on https://$Domain:$Port (requires admin for port 443)"

try {
  & $py -m servers.anp_sdk_server
} catch {
  Write-Warning "Failed to start ANP server on port $Port. Try running PowerShell as Administrator or use -Port 8443."
  throw
}

