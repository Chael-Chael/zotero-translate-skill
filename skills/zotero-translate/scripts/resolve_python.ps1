function Resolve-SkillPythonCommand {
  param([string]$PreferredPython)

  $candidateCommands = @()
  if ($PreferredPython) {
    $candidateCommands += ,@($PreferredPython)
  }

  foreach ($name in @("python3", "python")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) {
      $candidateCommands += ,@($cmd.Source)
    }
  }

  if ($IsWindows -or $env:OS -eq "Windows_NT") {
    $py = Get-Command "py" -ErrorAction SilentlyContinue
    if ($py) {
      $candidateCommands += ,@($py.Source, "-3")
    }
  }

  $homeDir = [Environment]::GetFolderPath("UserProfile")
  if (-not $homeDir) { $homeDir = $HOME }
  if ($homeDir) {
    $codexRoot = Join-Path $homeDir ".cache/codex-runtimes/codex-primary-runtime/dependencies/python"
    foreach ($path in @(
      (Join-Path $codexRoot "python.exe"),
      (Join-Path $codexRoot "python"),
      (Join-Path $codexRoot "bin/python3"),
      (Join-Path $codexRoot "bin/python")
    )) {
      if (Test-Path -LiteralPath $path) {
        $candidateCommands += ,@($path)
      }
    }
  }

  $seen = @{}
  foreach ($command in $candidateCommands) {
    $key = ($command -join "`0")
    if ($seen.ContainsKey($key)) { continue }
    $seen[$key] = $true
    $exe = $command[0]
    $prefixArgs = @()
    if ($command.Count -gt 1) { $prefixArgs = @($command[1..($command.Count - 1)]) }
    try {
      & $exe @prefixArgs -c "import sys; print(sys.version)" *> $null
      if ($LASTEXITCODE -eq 0) {
        return [pscustomobject]@{ Exe = $exe; Args = $prefixArgs }
      }
    } catch {
      continue
    }
  }

  throw "No usable Python 3 executable was found. Install Python 3 or pass -PythonExe."
}
