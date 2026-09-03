param([ValidateRange(0,65535)][int]$Port = 0, [switch]$ListOnly)
$ErrorActionPreference = 'Stop'
$h3Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $PSScriptRoot 'server_processes.ps1')

try {
    $h3Servers = @(Get-H3ServerProcesses -Root $h3Root -Port $Port)
    if ($ListOnly) { ConvertTo-Json -InputObject @($h3Servers | Select-Object Pid,ParentPid,Port) -Compress; exit 0 }
    if ($h3Servers.Count -eq 0) { Write-Host 'H3-documentary e gia fermo in questa cartella.'; exit 0 }
    foreach ($h3ServerPort in @($h3Servers.Port | Sort-Object -Unique)) {
        $h3Url = "http://127.0.0.1:$h3ServerPort"
        try {
            $h3Health = Invoke-RestMethod -Uri "$h3Url/api/health" -TimeoutSec 2
            if ($h3Health.service -eq 'h3-documentary' -and $h3Health.instance -and [IO.Path]::GetFullPath($h3Health.instance) -ieq $h3Root) {
                $h3Jobs = @(Invoke-RestMethod -Uri "$h3Url/api/projects" -TimeoutSec 2)
                foreach ($h3Job in $h3Jobs) {
                    if ($h3Job.status -in @('running','queued','cancelling')) {
                        Invoke-RestMethod -Method Post -Uri "$h3Url/api/projects/$($h3Job.id)/cancel" -Headers @{'X-DocumentariAI'='studio'} -TimeoutSec 3 | Out-Null
                        Write-Host 'Produzione interrotta; materiali salvati conservati.'
                    }
                }
            }
        } catch { Write-Host 'Il server non risponde: chiudo i suoi processi locali verificati.' }
    }
    # Stop the parent interpreter as well as the venv child and its renderer/FFmpeg descendants.
    $h3Parents = @($h3Servers | Where-Object { $_.ParentPid -notin $h3Servers.Pid })
    foreach ($h3Server in $h3Parents) {
        $h3Current = Get-CimInstance Win32_Process -Filter "ProcessId = $($h3Server.Pid)"
        if ($null -eq $h3Current) { continue }
        $h3Verified = Get-H3ServerIdentity -Process $h3Current -Root $h3Root
        if ($null -eq $h3Verified -or $h3Current.CreationDate -ne $h3Server.Created) { throw 'Il processo e cambiato: arresto annullato per sicurezza.' }
        & "$env:SystemRoot/System32/taskkill.exe" /PID "$($h3Server.Pid)" /T /F | Out-Null
        if ($LASTEXITCODE -ne 0 -and (Get-CimInstance Win32_Process -Filter "ProcessId = $($h3Server.Pid)")) { throw 'Impossibile fermare il processo del server.' }
    }
    # A short bounded verification; another application's process is never killed to free a port.
    for ($h3Try=0; $h3Try -lt 20; $h3Try++) {
        $h3Remaining = @(Get-H3ServerProcesses -Root $h3Root -Port $Port)
        if ($h3Remaining.Count -eq 0) { break }
        Start-Sleep -Milliseconds 150
    }
    if ($h3Remaining.Count -ne 0) { throw 'Alcuni processi del server sono ancora attivi.' }
    $h3Record = Join-Path $h3Root 'data/server.json'
    if (Test-Path -LiteralPath $h3Record) {
        try {
            $h3Saved = Get-Content -LiteralPath $h3Record -Raw | ConvertFrom-Json
            if ($h3Saved.root -ieq $h3Root -and $h3Saved.pid -in $h3Servers.Pid) { Remove-Item -LiteralPath $h3Record }
        } catch { Write-Host 'Il registro di avvio verra aggiornato al prossimo START.' }
    }
    Write-Host "H3-documentary fermato. Porte della copia: $(@($h3Servers.Port | Sort-Object -Unique) -join ', '). Puoi eseguire i test o riavviare con START.bat."
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
