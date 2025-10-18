$ErrorActionPreference = 'Stop'
$env:HOST = '127.0.0.1'
$env:PORT = '5052'
python ..\serve_waitress.py

