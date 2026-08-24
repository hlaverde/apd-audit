param(
    [string]$WatchFolder = "cloud_inbox",
    [int]$PollSeconds = 30,
    [switch]$Once,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    $scriptPath = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $scriptPath "..")).Path
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $enc)
}

function Read-Registry {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return @()
    }
    $raw = Get-Content -LiteralPath $Path -Raw
    if (-not $raw.Trim()) {
        return @()
    }
    $parsed = $raw | ConvertFrom-Json
    if ($null -eq $parsed) {
        return @()
    }
    $items = @()
    foreach ($item in @($parsed)) {
        if ($item.PSObject.Properties.Name -contains "sha256") {
            $items += $item
        }
    }
    return $items
}

function Write-Registry {
    param([object[]]$Items, [string]$Path)
    $json = @($Items) | ConvertTo-Json -Depth 20
    if ($null -eq $json) {
        $json = "[]"
    }
    Write-Utf8NoBom -Path $Path -Text ($json + "`n")
}

function Test-ZipStable {
    param([System.IO.FileInfo]$Zip)
    $size1 = $Zip.Length
    Start-Sleep -Seconds 2
    $fresh = Get-Item -LiteralPath $Zip.FullName
    return ($fresh.Length -eq $size1)
}

function Invoke-LoggedCommand {
    param(
        [string[]]$Command,
        [string]$Cwd,
        [string]$LogPath
    )
    $line = "+ " + ($Command -join " ")
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    Write-Host $line

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Command[0]
    foreach ($arg in $Command[1..($Command.Count - 1)]) {
        $psi.ArgumentList.Add($arg)
    }
    $psi.WorkingDirectory = $Cwd
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    [void]$proc.Start()
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()

    if ($stdout) {
        Add-Content -LiteralPath $LogPath -Value $stdout -Encoding UTF8
        Write-Host $stdout
    }
    if ($stderr) {
        Add-Content -LiteralPath $LogPath -Value $stderr -Encoding UTF8
        Write-Host $stderr
    }
    Add-Content -LiteralPath $LogPath -Value "exit_code: $($proc.ExitCode)" -Encoding UTF8
    return [int]$proc.ExitCode
}

function Test-AlreadyImported {
    param(
        [object[]]$Registry,
        [string]$Sha256,
        [string]$ZipName
    )
    foreach ($item in $Registry) {
        if ($item.sha256 -eq $Sha256) {
            return $true
        }
        if ($item.zip_name -eq $ZipName -and $item.status -eq "imported") {
            return $true
        }
    }
    return $false
}

function Process-Zip {
    param(
        [System.IO.FileInfo]$Zip,
        [string]$RepoRoot,
        [string]$RegistryPath,
        [switch]$DryRun
    )

    $logsDir = Join-Path $RepoRoot "results\logs"
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

    if (-not (Test-ZipStable -Zip $Zip)) {
        Write-Host "Skipping unstable ZIP still being written: $($Zip.FullName)"
        return $false
    }

    $sha = (Get-FileHash -LiteralPath $Zip.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $registry = Read-Registry -Path $RegistryPath
    if (Test-AlreadyImported -Registry $registry -Sha256 $sha -ZipName $Zip.Name) {
        Write-Host "Already imported, skipping: $($Zip.Name)"
        return $false
    }

    $logPath = Join-Path $logsDir ("import_{0}.log" -f $Zip.BaseName)
    if ($DryRun) {
        Write-Host "DRY RUN: would import $($Zip.FullName)"
        Write-Host "DRY RUN: would log to $logPath"
        Write-Host "DRY RUN: would update $RegistryPath after success"
        return $true
    }

    $started = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $header = @(
        "APD cloud ZIP import",
        "started_utc: $started",
        "zip: $($Zip.FullName)",
        "zip_name: $($Zip.Name)",
        "sha256: $sha",
        "size_bytes: $($Zip.Length)",
        "dry_run: $DryRun",
        ""
    ) -join "`n"
    Write-Utf8NoBom -Path $logPath -Text ($header + "`n")

    $importRc = Invoke-LoggedCommand -Command @(
        "python", "-m", "uv", "run", "python", "scripts/import_cloud_zip.py",
        $Zip.FullName,
        "--skip-dashboard",
        "--skip-preflight"
    ) -Cwd $RepoRoot -LogPath $logPath

    $dashboardRc = -1
    $preflightRc = -1
    if ($importRc -eq 0) {
        $dashboardRc = Invoke-LoggedCommand -Command @(
            "python", "-m", "uv", "run", "python", "scripts/09_progress_dashboard.py"
        ) -Cwd $RepoRoot -LogPath $logPath
        $preflightRc = Invoke-LoggedCommand -Command @(
            "python", "-m", "uv", "run", "python", "scripts/00_preflight.py"
        ) -Cwd $RepoRoot -LogPath $logPath
    }

    $status = "failed"
    if ($importRc -eq 0 -and $dashboardRc -eq 0 -and $preflightRc -eq 0) {
        $status = "imported"
    }

    $finished = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $entry = [ordered]@{
        zip_name = $Zip.Name
        zip_path = $Zip.FullName
        zip_stem = $Zip.BaseName
        sha256 = $sha
        size_bytes = [int64]$Zip.Length
        imported_at_utc = $finished
        status = $status
        log_path = $logPath
        import_returncode = $importRc
        dashboard_returncode = $dashboardRc
        preflight_returncode = $preflightRc
    }

    if ($status -eq "imported") {
        $registry = @($registry + [pscustomobject]$entry)
        Write-Registry -Items $registry -Path $RegistryPath
    }

    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value @(
        "",
        "FINAL SUMMARY",
        "finished_utc: $finished",
        "status: $status",
        "import_returncode: $importRc",
        "dashboard_returncode: $dashboardRc",
        "preflight_returncode: $preflightRc"
    )

    Write-Host ""
    Write-Host "============== CLOUD ZIP WATCH SUMMARY =============="
    Write-Host "ZIP: $($Zip.Name)"
    Write-Host "SHA256: $sha"
    Write-Host "Status: $status"
    Write-Host "Log: $logPath"
    Write-Host "Registry: $RegistryPath"
    Write-Host "Import RC: $importRc"
    Write-Host "Dashboard RC: $dashboardRc"
    Write-Host "Preflight RC: $preflightRc"
    Write-Host "====================================================="

    if ($status -ne "imported") {
        throw "Import workflow failed for $($Zip.Name). See $logPath"
    }
    return $true
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

if ($PollSeconds -lt 1) {
    throw "PollSeconds must be >= 1"
}

$watchPath = $WatchFolder
if (-not [System.IO.Path]::IsPathRooted($watchPath)) {
    $watchPath = Join-Path $repoRoot $watchPath
}
$watchPath = (New-Item -ItemType Directory -Force -Path $watchPath).FullName

$resultsDir = Join-Path $repoRoot "results"
New-Item -ItemType Directory -Force -Path $resultsDir | Out-Null
$registryPath = Join-Path $resultsDir "imported_cloud_zips.json"
if (-not (Test-Path -LiteralPath $registryPath)) {
    Write-Utf8NoBom -Path $registryPath -Text "[]`n"
}

Write-Host "Watching: $watchPath"
Write-Host "Registry: $registryPath"
Write-Host "PollSeconds: $PollSeconds"
Write-Host "Once: $Once"
Write-Host "DryRun: $DryRun"

do {
    $zips = @(Get-ChildItem -LiteralPath $watchPath -Recurse -File -Filter "apd_cloud_run_*.zip" |
        Sort-Object LastWriteTimeUtc, FullName)
    $processed = $false
    foreach ($zip in $zips) {
        $processed = Process-Zip -Zip $zip -RepoRoot $repoRoot -RegistryPath $registryPath -DryRun:$DryRun
        if ($processed) {
            break
        }
    }

    if ($Once) {
        if (-not $processed) {
            Write-Host "No new apd_cloud_run_*.zip files to import."
        }
        break
    }

    if (-not $processed) {
        Start-Sleep -Seconds $PollSeconds
    }
} while ($true)
