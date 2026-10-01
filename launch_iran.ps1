$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$gui = Join-Path $root 'gui.py'
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -like "*$gui*"
} | ForEach-Object {
    try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
}
Start-Sleep -Milliseconds 300
Start-Process 'C:\Program Files\Python314\pythonw.exe' -ArgumentList ('"' + $gui + '"') -WorkingDirectory $root
