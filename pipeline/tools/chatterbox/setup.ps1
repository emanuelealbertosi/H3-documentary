$ErrorActionPreference = 'Stop'
$ttsRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location -LiteralPath $ttsRoot
$ttsBootstrap = Join-Path $ttsRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $ttsBootstrap)) { $ttsBootstrap = 'python' }
$ttsUv = Join-Path (Split-Path $ttsRoot -Parent) '.runtimes/uv/uv.exe'
if (-not (Test-Path -LiteralPath $ttsUv)) {
    & $ttsBootstrap -m pip install --target tools/.bootstrap/uv uv==0.12.9
    if ($LASTEXITCODE -ne 0) { throw 'Installazione del gestore ambienti non riuscita.' }
}
$env:UV_CACHE_DIR = Join-Path $ttsRoot '.cache/uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $ttsRoot '.runtimes/python'
$env:GIT_TERMINAL_PROMPT = '0'
if (-not (Test-Path -LiteralPath '.venv-chatterbox/Scripts/python.exe')) {
    & $ttsUv venv .venv-chatterbox --python 3.11.16 --managed-python
    if ($LASTEXITCODE -ne 0) { throw 'Creazione ambiente Chatterbox non riuscita.' }
}
& $ttsUv pip install --python .venv-chatterbox/Scripts/python.exe --no-deps -r tools/chatterbox/requirements-lock.txt --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match
if ($LASTEXITCODE -ne 0) { throw 'Installazione Chatterbox non riuscita.' }
& $ttsUv pip check --python .venv-chatterbox/Scripts/python.exe
if ($LASTEXITCODE -ne 0) { throw 'Dipendenze Chatterbox incoerenti.' }
& './.venv-chatterbox/Scripts/python.exe' -X utf8 tools/chatterbox/fetch_models.py
if ($LASTEXITCODE -ne 0) { throw 'Download o verifica dei pesi non riusciti.' }
Write-Output 'Chatterbox pronto. Esegui tools/chatterbox/prova.ps1 per ascoltare il campione italiano.'
