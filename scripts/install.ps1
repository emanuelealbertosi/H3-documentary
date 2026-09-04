param([switch]$Chatterbox,[switch]$SenzaChatterbox)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$h3Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $h3Root
New-Item -ItemType Directory -Force -Path "$h3Root/data","$h3Root/.runtimes/uv" | Out-Null
Start-Transcript -LiteralPath "$h3Root/data/install.log" -Append | Out-Null
function Run-Checked([string]$File, [string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Operazione non riuscita (codice $LASTEXITCODE): $File" }
}
try {
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
        throw 'Questa versione richiede Windows x64 Intel/AMD.'
    }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $h3Uv = Join-Path $h3Root '.runtimes/uv/uv.exe'
    if (-not (Test-Path -LiteralPath $h3Uv)) {
        Write-Host 'Scarico il gestore gratuito dei componenti...'
        $h3Archive = Join-Path $h3Root '.runtimes/uv.zip'
        $h3Url = 'https://github.com/astral-sh/uv/releases/download/0.12.9/uv-x86_64-pc-windows-msvc.zip'
        $h3Expected = 'ddbfcee1ac615a0499f6aa97b5ec8ebdf3ee4a7714a48055ec2ba0030e3cf810'
        for ($h3Attempt=0; $h3Attempt -lt 3; $h3Attempt++) {
            try {
                Invoke-WebRequest -UseBasicParsing -Uri $h3Url -OutFile $h3Archive
                $h3Stream = [IO.File]::OpenRead($h3Archive)
                $h3Hasher = [Security.Cryptography.SHA256]::Create()
                try { $h3Hash = ([BitConverter]::ToString($h3Hasher.ComputeHash($h3Stream))).Replace('-','').ToLower() }
                finally { $h3Stream.Dispose(); $h3Hasher.Dispose() }
                if ($h3Hash -ne $h3Expected) { throw 'Checksum del runtime non valido.' }
                break
            } catch { if ($h3Attempt -eq 2) { throw }; Start-Sleep -Seconds 2 }
        }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $h3Zip = [IO.Compression.ZipFile]::OpenRead($h3Archive)
        try {
            foreach ($h3Entry in $h3Zip.Entries) {
                if ($h3Entry.Name -notin @('uv.exe','uvx.exe')) { continue }
                [IO.Compression.ZipFileExtensions]::ExtractToFile($h3Entry,(Join-Path "$h3Root/.runtimes/uv" $h3Entry.Name),$true)
            }
        } finally { $h3Zip.Dispose() }
    }
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $h3Root '.runtimes/python'
    $env:UV_CACHE_DIR = Join-Path $h3Root '.cache/uv'
    $env:UV_PYTHON_BIN_DIR = Join-Path $h3Root '.runtimes/bin'
    $env:UV_NO_MODIFY_PATH = '1'
    $env:PYTHONUTF8 = '1'
    $env:UV_HTTP_TIMEOUT = '180'
    $env:UV_HTTP_RETRIES = '3'
    foreach ($h3Area in @('', 'pipeline')) {
        $h3AreaRoot = if ($h3Area) { Join-Path $h3Root $h3Area } else { $h3Root }
        $h3Env = Join-Path $h3AreaRoot '.venv'
        $h3Python = Join-Path $h3Env 'Scripts/python.exe'
        Write-Host "Preparo Python e le dipendenze in $h3AreaRoot"
        Run-Checked $h3Uv @('venv',$h3Env,'--python','3.13.13','--managed-python','--allow-existing')
        Run-Checked $h3Uv @('pip','install','--python',$h3Python,'-r',(Join-Path $h3AreaRoot 'requirements-lock.txt'))
        Run-Checked $h3Uv @('pip','check','--python',$h3Python)
    }
    $h3AppPython = Join-Path $h3Root '.venv/Scripts/python.exe'
    Run-Checked $h3AppPython @('-X','utf8',(Join-Path $h3Root 'scripts/bootstrap_assets.py'))
    Run-Checked $h3AppPython @('-X','utf8',(Join-Path $h3Root 'scripts/check_install.py'),'--write-state')
    if ($Chatterbox -or -not $SenzaChatterbox) {
        Write-Host 'Preparo Chatterbox Multilingual V3 (download iniziale di circa 3 GB)...'
        & (Join-Path $h3Root 'pipeline/tools/chatterbox/setup.ps1')
        if ($LASTEXITCODE -ne 0) { throw 'Installazione opzionale Chatterbox non completata.' }
    }
    Write-Host 'H3-documentary pronto. Apri AVVIA.bat e configura il server LLM in Amministrazione.' -ForegroundColor Green
} catch {
    Write-Host "Installazione interrotta: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'I progetti sono conservati. Riapri INSTALLA.bat per riprendere. Dettagli: data/install.log'
    exit 1
} finally {
    Stop-Transcript | Out-Null
}
