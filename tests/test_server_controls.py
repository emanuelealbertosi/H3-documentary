"""Real Windows argument parsing; stopping must never rely on a saved PID alone."""
import json,os,subprocess
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
pytestmark=pytest.mark.skipif(os.name!='nt',reason='Windows launcher controls')

def test_process_identity_rejects_other_copies_and_mentioned_script(tmp_path):
    root=r'C:\H3 demo & test'
    python=root+r'\.venv\Scripts\python.exe';script=root+r'\run.py'
    commands=[
        [python,'-X','utf8',script,'--port','8778'],
        [python,script],
        [python,'-c',f'print({script!r})'],
        [python,root+r'\other\run.py','--port','8778'],
        [r'C:\Other H3\.venv\Scripts\python.exe',script],
        [python,'run.py'],
        [python,script,'--port','bad'],
        [python,script,'--port','80'],
        [python,script+'-different'],
        [python,'-m','uvicorn','app.server:app'],
        [python,script,'--port','8778','unexpected'],
    ]
    rows=[{'ProcessId':100+i,'ParentProcessId':10,'CreationDate':'2026-01-01','Name':'python.exe','CommandLine':subprocess.list2cmdline(c)} for i,c in enumerate(commands)]
    payload=tmp_path/'processes.json';payload.write_text(json.dumps({'root':root,'rows':rows}))
    ps=tmp_path/'identity.ps1'
    helper=str(ROOT/'scripts/server_processes.ps1').replace("'","''")
    ps.write_text("param([string]$Fixture)\n$ErrorActionPreference='Stop'\n. '"+helper+"'\n"+
        "$sample=Get-Content -LiteralPath $Fixture -Raw | ConvertFrom-Json\n"+
        "$results=@(foreach($row in $sample.rows){$found=Get-H3ServerIdentity -Process $row -Root $sample.root; if($null -eq $found){0}else{$found.Port}})\n"+
        "ConvertTo-Json -InputObject $results -Compress\n")
    binary=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    run=subprocess.run([str(binary),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(ps),str(payload)],capture_output=True,text=True,timeout=30)
    assert run.returncode==0,run.stderr
    assert json.loads(run.stdout)==[8778,8775,0,0,0,0,0,0,0,0,0]

def test_stop_does_not_install_dependencies_or_kill_by_image_name():
    stop=(ROOT/'scripts/stop.ps1').read_text()
    assert 'install.ps1' not in stop
    assert 'Get-H3ServerIdentity' in stop and 'CreationDate -ne $h3Server.Created' in stop
    assert '/T /F' in stop and '/IM' not in stop
    assert "'data/server.json'" in stop and 'Remove-Item -LiteralPath $h3Record' in stop
    assert 'server_processes.ps1' in stop
