param(
  [int]$Port = 9222,
  [string]$UserDataDir = "$env:LOCALAPPDATA\HumanBrowseProfile",
  [string]$ChromePath = ""
)

function Resolve-ChromePath {
  param([string]$OverridePath)

  if ($OverridePath -and $OverridePath.Trim().Length -gt 0) {
    if (Test-Path -LiteralPath $OverridePath) {
      return $OverridePath
    }
    throw "-ChromePath was provided but not found: $OverridePath"
  }

  $regKeys = @(
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
  )
  foreach ($key in $regKeys) {
    try {
      $val = (Get-ItemProperty -Path $key -ErrorAction Stop)."(default)"
      if ($val -and (Test-Path -LiteralPath $val)) {
        return $val
      }
    } catch {
      # ignore and continue
    }
  }

  $cmd = Get-Command chrome.exe -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Path -and (Test-Path -LiteralPath $cmd.Path)) {
    return $cmd.Path
  }

  $candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
  )
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
      return $candidate
    }
  }

  throw "Could not find chrome.exe. Pass -ChromePath to specify the Chrome executable."
}

$chromeExe = Resolve-ChromePath -OverridePath $ChromePath

if (-not (Test-Path -LiteralPath $UserDataDir)) {
  New-Item -ItemType Directory -Path $UserDataDir -Force | Out-Null
}

$args = @(
  "--remote-debugging-port=$Port",
  "--user-data-dir=$UserDataDir",
  "--new-window",
  "about:blank"
)

Start-Process -FilePath $chromeExe -ArgumentList $args
Write-Host "CDP check: http://127.0.0.1:$Port/json/version"
