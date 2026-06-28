param(
  [Parameter(Mandatory = $true)]
  [string]$InputPdf,
  [string]$OutputPath,
  [string]$ZoteroJson,
  [string]$SourceLanguage = "en",
  [string]$TargetLanguage = "zh",
  [int]$MaxPages = 4,
  [int]$MaxCharsPerPage = 5000,
  [string]$UserPreferences = "Use concise, academically precise Simplified Chinese. Preserve established English acronyms and method names when commonly used.",
  [string]$PythonExe,
  [switch]$IncludeLocalPaths,
  [switch]$Force
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

. (Join-Path $PSScriptRoot "resolve_python.ps1")
$python = Resolve-SkillPythonCommand -PreferredPython $PythonExe
$argsList = @(
  (Join-Path $PSScriptRoot "build_context_pack.py"),
  "--input-pdf", $InputPdf,
  "--source-language", $SourceLanguage,
  "--target-language", $TargetLanguage,
  "--max-pages", [string]$MaxPages,
  "--max-chars-per-page", [string]$MaxCharsPerPage,
  "--user-preferences", $UserPreferences
)
if ($OutputPath) { $argsList += @("--output-path", $OutputPath) }
if ($ZoteroJson) { $argsList += @("--zotero-json", $ZoteroJson) }
if ($IncludeLocalPaths) { $argsList += "--include-local-paths" }
if ($Force) { $argsList += "--force" }

& $python.Exe @($python.Args + $argsList)
exit $LASTEXITCODE
