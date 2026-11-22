# Run in PowerShell from the project folder:  powershell -ExecutionPolicy Bypass -File .\check_deps.ps1
$tools = @(
  @{n="Python"; c="python"; a="--version"},
  @{n="py launcher"; c="py"; a="--version"},
  @{n="uv"; c="uv"; a="--version"},
  @{n="FFmpeg"; c="ffmpeg"; a="-version"},
  @{n="FFprobe"; c="ffprobe"; a="-version"},
  @{n="Node.js"; c="node"; a="--version"},
  @{n="npm"; c="npm"; a="--version"},
  @{n="Git"; c="git"; a="--version"}
)
foreach ($t in $tools) {
  $cmd = Get-Command $t.c -ErrorAction SilentlyContinue
  if ($cmd) {
    $v = (& $t.c $t.a 2>&1 | Select-Object -First 1)
    Write-Host ("[OK]      {0,-12} {1}" -f $t.n, $v) -ForegroundColor Green
  } else {
    Write-Host ("[MISSING] {0,-12}" -f $t.n) -ForegroundColor Red
  }
}
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
  $enc = ffmpeg -hide_banner -encoders 2>&1 | Select-String "libx264"
  $flt = ffmpeg -hide_banner -filters 2>&1 | Select-String " ass |sidechaincompress"
  Write-Host ("libx264 encoder: {0}" -f ($(if ($enc) {"yes"} else {"NO"})))
  Write-Host ("ass/sidechain filters: {0}" -f ($flt.Count))
}
Write-Host "`nIf missing, install with:"
Write-Host "  winget install Python.Python.3.12"
Write-Host "  winget install astral-sh.uv"
Write-Host "  winget install Gyan.FFmpeg"
Write-Host "  winget install OpenJS.NodeJS.LTS   (only needed for Remotion)"
