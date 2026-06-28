param(
  [Parameter(Mandatory = $true)]
  [string]$TranslationsPath,
  [Parameter(Mandatory = $true)]
  [string]$MissingPath,
  [string]$PythonExe
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

. (Join-Path $PSScriptRoot "resolve_python.ps1")
$python = Resolve-SkillPythonCommand -PreferredPython $PythonExe
$argsList = @(
  (Join-Path $PSScriptRoot "lookup_translator.py"),
  "--translations-path", $TranslationsPath,
  "--missing-path", $MissingPath
)

& $python.Exe @($python.Args + $argsList)
exit $LASTEXITCODE
