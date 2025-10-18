$ErrorActionPreference = 'Stop'
$env:HOST = '0.0.0.0'
$env:PORT = '5443'
$env:SSL_CERTFILE = (Join-Path $PSScriptRoot '..\certs\server.crt')
$env:SSL_KEYFILE = (Join-Path $PSScriptRoot '..\certs\server.key')
if (!(Test-Path $env:SSL_CERTFILE) -or !(Test-Path $env:SSL_KEYFILE)) {
  Write-Error "Missing cert files at $env:SSL_CERTFILE / $env:SSL_KEYFILE"
  exit 1
}
if (Get-Command waitress-serve -ErrorAction SilentlyContinue) {
  waitress-serve --host=$env:HOST --port=$env:PORT --url-scheme=https --ssl-certfile=$env:SSL_CERTFILE --ssl-keyfile=$env:SSL_KEYFILE app:app
} else {
  python ..\serve_https.py
}

