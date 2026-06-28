param(
  [ValidateSet("collect", "render")]
  [string]$Phase = "collect",
  [string]$InputPdf,
  [string]$RunDir,
  [string]$Pages,
  [string]$LangIn = "en",
  [string]$LangOut = "zh",
  [ValidateSet("mono", "dual", "both")]
  [string]$OutputMode = "both",
  [ValidateSet("no_watermark", "watermarked", "both")]
  [string]$WatermarkOutputMode = "no_watermark",
  [switch]$NoAutoGlossary,
  [int]$CliTranslatorTimeout = 120,
  [string]$PythonExe,
  [switch]$ForceRuntime,
  [switch]$KeepArtifacts,
  [ValidateSet("success", "always", "never")]
  [string]$CleanupPolicy = "success",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

. (Join-Path $PSScriptRoot "resolve_python.ps1")
$python = Resolve-SkillPythonCommand -PreferredPython $PythonExe
$argsList = @((Join-Path $PSScriptRoot "run_pdf2zh.py"))

if ($PSBoundParameters.ContainsKey("Phase")) { $argsList += @("--phase", $Phase) }
if ($PSBoundParameters.ContainsKey("InputPdf")) { $argsList += @("--input-pdf", $InputPdf) }
if ($PSBoundParameters.ContainsKey("RunDir")) { $argsList += @("--run-dir", $RunDir) }
if ($PSBoundParameters.ContainsKey("Pages")) { $argsList += @("--pages", $Pages) }
if ($PSBoundParameters.ContainsKey("LangIn")) { $argsList += @("--lang-in", $LangIn) }
if ($PSBoundParameters.ContainsKey("LangOut")) { $argsList += @("--lang-out", $LangOut) }
if ($PSBoundParameters.ContainsKey("OutputMode")) { $argsList += @("--output-mode", $OutputMode) }
if ($PSBoundParameters.ContainsKey("WatermarkOutputMode")) { $argsList += @("--watermark-output-mode", $WatermarkOutputMode) }
if ($NoAutoGlossary) { $argsList += "--no-auto-glossary" }
if ($PSBoundParameters.ContainsKey("CliTranslatorTimeout")) { $argsList += @("--cli-translator-timeout", [string]$CliTranslatorTimeout) }
if ($PythonExe) { $argsList += @("--python-exe", $PythonExe) }
if ($ForceRuntime) { $argsList += "--force-runtime" }
if ($KeepArtifacts) { $argsList += "--keep-artifacts" }
if ($PSBoundParameters.ContainsKey("CleanupPolicy")) { $argsList += @("--cleanup-policy", $CleanupPolicy) }
if ($DryRun) { $argsList += "--dry-run" }

& $python.Exe @($python.Args + $argsList)
exit $LASTEXITCODE
