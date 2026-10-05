param([switch]$Rebuild)
$ErrorActionPreference = 'Stop'
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw '请按 README.md 中的初始化步骤建立本地运行环境。'
}
$taskArgs = @((Join-Path $PSScriptRoot 'analyze.py'), '--config', (Join-Path $PSScriptRoot 'tasks\2026-10-02-mac-readonly\config.json'))
if ($Rebuild) { $taskArgs += '--rebuild' }
& $taskPython @taskArgs
if ($LASTEXITCODE -ne 0) { throw "只读分析失败，退出码 $LASTEXITCODE。" }
