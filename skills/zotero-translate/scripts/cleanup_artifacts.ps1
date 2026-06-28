param(
  [Parameter(Mandatory = $true)]
  [string]$RunDir,
  [ValidateSet("success", "always", "never")]
  [string]$CleanupPolicy = "success",
  [switch]$KeepArtifacts,
  [switch]$ConfirmAttached,
  [string]$PythonExe
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

. (Join-Path $PSScriptRoot "resolve_python.ps1")
$python = Resolve-SkillPythonCommand -PreferredPython $PythonExe
$argsList = @(
  (Join-Path $PSScriptRoot "cleanup_artifacts.py"),
  "--run-dir", $RunDir,
  "--cleanup-policy", $CleanupPolicy
)
if ($KeepArtifacts) { $argsList += "--keep-artifacts" }
if ($ConfirmAttached) { $argsList += "--confirm-attached" }

& $python.Exe @($python.Args + $argsList)
exit $LASTEXITCODE
