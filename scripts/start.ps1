param([int]$Port = 8775, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$h3Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $h3Root
try {
    $h3Python = Join-Path $h3Root '.venv/Scripts/python.exe'
    $h3State = Join-Path $h3Root 'data/installation.json'
    $h3Ready = $false
    if ((Test-Path -LiteralPath $h3Python) -and (Test-Path -LiteralPath $h3State)) {
        $h3Saved = Get-Content -LiteralPath $h3State -Raw | ConvertFrom-Json
        $h3Ready = ($h3Saved.root -eq $h3Root) -and ($h3Saved.version -eq (Get-Content -LiteralPath "$h3Root/VERSION" -Raw).Trim())
        if ($h3Ready) {
            & $h3Python -X utf8 "$h3Root/scripts/check_install.py" --quick
            $h3Ready = $LASTEXITCODE -eq 0
        }
    }
    if (-not $h3Ready) { & "$h3Root/scripts/install.ps1"; if ($LASTEXITCODE -ne 0) { throw 'Installazione non completata.' } }
    $h3Args = @('-X','utf8',"$h3Root/scripts/launch.py",'--port',"$Port")
    if ($NoBrowser) { $h3Args += '--no-browser' }
    & $h3Python @h3Args
    if ($LASTEXITCODE -ne 0) { throw 'Avvio non completato. Consulta data/server.stderr.log.' }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
