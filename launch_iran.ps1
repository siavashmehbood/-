$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
try {
    $venv = Join-Path $root '.venv\Scripts\python.exe'
    if (Test-Path $venv) {
        $python = $venv
        $prefix = @()
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $python = 'py'
        $prefix = @('-3.12')
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $python = 'python'
        $prefix = @()
    } else {
        throw 'Python 3.12 was not found. Install it or create .venv; see docs/FINAL_ACCEPTANCE.md.'
    }
    & $python @prefix (Join-Path $root 'launch_gui.pyw')
    if ($LASTEXITCODE -ne 0) { throw "IRAN startup failed. See gui_startup.log (exit $LASTEXITCODE)." }
} catch {
    Write-Host "IRAN could not start: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
