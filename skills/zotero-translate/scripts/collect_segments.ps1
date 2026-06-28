param(
  [Parameter(Mandatory = $true)]
  [string]$SegmentsPath,
  [string]$ManifestPath,
  [string]$SourceLanguage = "en",
  [Parameter(Mandatory = $true)]
  [string]$TargetLanguage,
  [string]$PythonExe
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

. (Join-Path $PSScriptRoot "resolve_python.ps1")
$python = Resolve-SkillPythonCommand -PreferredPython $PythonExe
$argsList = @(
  (Join-Path $PSScriptRoot "collect_segments.py"),
  "--segments-path", $SegmentsPath,
  "--source-language", $SourceLanguage,
  "--target-language", $TargetLanguage
)
if ($ManifestPath) { $argsList += @("--manifest-path", $ManifestPath) }

& $python.Exe @($python.Args + $argsList)
exit $LASTEXITCODE
