# Copy Cursor workflow rules (.mdc) into another project.
# Usage: .\scripts\sync-cursor-rules.ps1 -TargetProject "D:\MyApp"

param(
    [Parameter(Mandatory = $true)]
    [string]$TargetProject
)

$SourceRules = Join-Path $PSScriptRoot ".." ".cursor" "rules"
$DestRules = Join-Path $TargetProject ".cursor" "rules"

if (-not (Test-Path $TargetProject)) {
    Write-Error "Target project not found: $TargetProject"
    exit 1
}

New-Item -ItemType Directory -Path $DestRules -Force | Out-Null

$files = @("tdd.mdc", "e2e.mdc", "security-review.mdc")
foreach ($file in $files) {
    $src = Join-Path $SourceRules $file
    if (Test-Path $src) {
        Copy-Item $src -Destination $DestRules -Force
        Write-Host "Copied: $file"
    } else {
        Write-Warning "Missing: $src"
    }
}

Write-Host "Done. Rules are in: $DestRules"
