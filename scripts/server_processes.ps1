# Shared read-only identity check. Never trust a saved PID or a port alone.
if (-not ('H3WindowsCommandLine' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class H3WindowsCommandLine {
    [DllImport("shell32.dll", SetLastError=true)]
    static extern IntPtr CommandLineToArgvW([MarshalAs(UnmanagedType.LPWStr)] string value, out int count);
    [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr value);
    public static string[] Split(string value) {
        int count; IntPtr ptr=CommandLineToArgvW(value, out count);
        if(ptr==IntPtr.Zero) throw new InvalidOperationException("Command line parsing failed");
        try {
            string[] result=new string[count];
            for(int i=0;i<count;i++) result[i]=Marshal.PtrToStringUni(Marshal.ReadIntPtr(ptr,i*IntPtr.Size));
            return result;
        } finally {LocalFree(ptr);}
    }
}
'@
}

function Get-H3ServerIdentity {
    param($Process, [string]$Root)
    if (-not $Process.CommandLine -or $Process.Name -notmatch '^python(?:w)?\.exe$') { return $null }
    try {
        $h3Words = [H3WindowsCommandLine]::Split($Process.CommandLine)
        $h3ExpectedPython = [IO.Path]::GetFullPath((Join-Path $Root '.venv/Scripts/python.exe'))
        $h3ExpectedScript = [IO.Path]::GetFullPath((Join-Path $Root 'run.py'))
        if ($h3Words.Count -lt 2 -or [IO.Path]::GetFullPath($h3Words[0]) -ine $h3ExpectedPython) { return $null }
        # Accept only the launcher forms: python [-X utf8] <absolute run.py> [--port N].
        # A path mentioned inside `python -c ...` must never qualify as this server.
        $h3Index = 1
        if ($h3Words[$h3Index] -eq '-X' -and $h3Words.Count -gt 3 -and $h3Words[$h3Index+1] -eq 'utf8') { $h3Index += 2 }
        if (-not [IO.Path]::IsPathRooted($h3Words[$h3Index])) { return $null }
        if ([IO.Path]::GetFullPath($h3Words[$h3Index]) -ine $h3ExpectedScript) { return $null }
        $h3ServerPort = 8775
        if ($h3Words.Count -gt $h3Index+1) {
            if ($h3Words.Count -ne $h3Index+3 -or $h3Words[$h3Index+1] -ne '--port') { return $null }
            if (-not [int]::TryParse($h3Words[$h3Index+2], [ref]$h3ServerPort)) { return $null }
        }
        if ($h3ServerPort -lt 1024 -or $h3ServerPort -gt 65535) { return $null }
        return [pscustomobject]@{Pid=[int]$Process.ProcessId;ParentPid=[int]$Process.ParentProcessId;Created=$Process.CreationDate;Port=$h3ServerPort}
    } catch { return $null }
}

function Get-H3ServerProcesses {
    param([string]$Root, [int]$Port = 0)
    foreach ($h3Process in (Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'")) {
        $h3Identity = Get-H3ServerIdentity -Process $h3Process -Root $Root
        if ($null -ne $h3Identity -and ($Port -eq 0 -or $h3Identity.Port -eq $Port)) { $h3Identity }
    }
}
