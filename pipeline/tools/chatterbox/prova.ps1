param([string]$Reference, [string]$TextFile, [string]$Language='it')
$ErrorActionPreference = 'Stop'
$ttsRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$ttsArguments = @('-X','utf8',(Join-Path $PSScriptRoot 'probe.py'),'--languages',$Language)
if ($Reference) { $ttsArguments += @('--reference',(Resolve-Path -LiteralPath $Reference).Path,'--name','reference') }
if ($TextFile) { $ttsArguments += @('--text-file',(Resolve-Path -LiteralPath $TextFile).Path) }
Set-Location -LiteralPath $ttsRoot
$ttsPython = Join-Path $ttsRoot '.venv-chatterbox/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $ttsPython)) { throw 'Esegui prima tools/chatterbox/setup.ps1.' }
& $ttsPython @ttsArguments
if ($LASTEXITCODE -ne 0) { throw 'La prova vocale non e stata completata.' }
