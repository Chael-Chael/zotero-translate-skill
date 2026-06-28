param(
  [string]$PythonExe,
  [string]$PackageSpec = "pdf2zh-next>=2.8.2",
  [switch]$Force
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

. (Join-Path $PSScriptRoot "resolve_python.ps1")
$python = Resolve-SkillPythonCommand -PreferredPython $PythonExe
$argsList = @((Join-Path $PSScriptRoot "ensure_runtime.py"))
if ($PythonExe) { $argsList += @("--python-exe", $PythonExe) }
if ($PackageSpec) { $argsList += @("--package-spec", $PackageSpec) }
if ($Force) { $argsList += "--force" }

& $python.Exe @($python.Args + $argsList)
exit $LASTEXITCODE
