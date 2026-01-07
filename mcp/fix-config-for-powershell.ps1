# fix-config-for-powershell.ps1
# Fixes config.toml to use Windows-style paths instead of Git Bash paths
# This resolves the "connection closed" MCP handshake issue

$ErrorActionPreference = "Stop"

Write-Host "=== Fixing Codex Config for PowerShell ===" -ForegroundColor Cyan
Write-Host ""

$configPath = Join-Path $env:USERPROFILE ".codex\config.toml"

if (-not (Test-Path $configPath)) {
    Write-Host "❌ Config file not found: $configPath" -ForegroundColor Red
    exit 1
}

Write-Host "Reading config: $configPath" -ForegroundColor White

# Backup original
$backupPath = "$configPath.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item $configPath $backupPath
Write-Host "✓ Backup created: $backupPath" -ForegroundColor Green

# Read config
$config = Get-Content $configPath -Raw

Write-Host ""
Write-Host "Analyzing config..." -ForegroundColor White

# Check if it has Git Bash style paths
if ($config -match '"-v","/c/') {
    Write-Host "Found Git Bash style path (causes issues)" -ForegroundColor Yellow
    Write-Host "  Example: /c/Users/..." -ForegroundColor DarkGray
    Write-Host ""

    # Fix: Convert /c/Users/... to C:\\Users\\...
    # Also fix the double slash in ://workspace to :/workspace
    $originalLine = $config | Select-String -Pattern '"-v","/c/[^"]+://workspace:ro"' | Select-Object -First 1

    if ($originalLine) {
        Write-Host "Original:" -ForegroundColor Red
        Write-Host "  $($originalLine.Line.Trim())" -ForegroundColor DarkGray

        # Replace pattern
        $config = $config -replace '"-v","/c/([^"]+)://workspace:ro"', '"-v","C:\$1:/workspace:ro"'

        # Need to escape backslashes for TOML
        $config = $config -replace '"-v","C:\\([^"]+):/workspace:ro"', {
            $path = $_.Groups[1].Value
            # Escape backslashes
            $escapedPath = $path -replace '/', '\\'
            "-v`",`"C:\\$escapedPath:/workspace:ro`""
        }

        $newLine = $config | Select-String -Pattern '"-v","C:\\\\[^"]+:/workspace:ro"' | Select-Object -First 1
        Write-Host ""
        Write-Host "Fixed:" -ForegroundColor Green
        Write-Host "  $($newLine.Line.Trim())" -ForegroundColor DarkGray
    }
}
else {
    Write-Host "✓ Config already uses Windows-style paths" -ForegroundColor Green
}

# Write fixed config
Set-Content $configPath -Value $config -Encoding UTF8

Write-Host ""
Write-Host "=== Fix Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Close any open Git Bash/PowerShell sessions running Codex" -ForegroundColor White
Write-Host "  2. Open a NEW PowerShell window (not Git Bash!)" -ForegroundColor White
Write-Host "  3. Navigate to your project:" -ForegroundColor White
Write-Host "     cd `"C:\Users\prenganathan\OneDrive - Adaptive Biotechnologies\Documents\git-rag-chat\git-rag-chat`"" -ForegroundColor Cyan
Write-Host "  4. Start Codex:" -ForegroundColor White
Write-Host "     codex" -ForegroundColor Cyan
Write-Host "  5. Test:" -ForegroundColor White
Write-Host "     List all available tools" -ForegroundColor Cyan
Write-Host ""
Write-Host "If you need to restore original config:" -ForegroundColor DarkGray
Write-Host "  Copy-Item `"$backupPath`" `"$configPath`"" -ForegroundColor DarkGray
Write-Host ""
