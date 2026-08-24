param(
    [int]$PollSeconds = 300,
    [int]$StopAfterHours = 10,
    [int]$MaxRetriesPerBatch = 12,
    [string]$CurrentRunLabel = "",
    [string]$CurrentKernelSlug = "",
    [int]$StartQueueIndex = 0,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$repoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $PSCommandPath) "..")).Path
$logsDir = Join-Path $repoRoot "results\logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
$supervisorLog = Join-Path $logsDir ("kaggle_overnight_supervisor_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))
$deadline = (Get-Date).AddHours($StopAfterHours)

function Write-Log {
    param([string]$Message)
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Write-Host $line
    Add-Content -LiteralPath $supervisorLog -Value $line -Encoding UTF8
}

function Invoke-ProjectPython {
    param([string[]]$ArgList)
    $python = Join-Path $repoRoot ".venv\Scripts\python.exe"
    & $python @ArgList
}

function Get-KaggleStatus {
    param([string]$KernelSlug)
    $output = & py -m kaggle kernels status $KernelSlug 2>&1
    return ($output -join "`n")
}

function Get-KernelState {
    param([string]$Text)
    $lower = $Text.ToLowerInvariant()
    if ($lower -match "complete|success|succeeded") { return "complete" }
    if ($lower -match "error|failed|failure|cancel|canceled|cancelled") { return "failed" }
    if ($lower -match "running|queued|pending") { return "running" }
    return "unknown"
}

function Import-CompletedKernelOutput {
    param(
        [string]$RunLabel,
        [string]$KernelSlug
    )
    $downloadDir = Join-Path $repoRoot ("cloud_inbox\kaggle_{0}" -f $RunLabel)
    $expectedZip = Join-Path $downloadDir ("apd_cloud_run_{0}.zip" -f $RunLabel)
    Write-Log "Recovering completed kernel output for $RunLabel into $downloadDir"
    if (Test-Path -LiteralPath $downloadDir) {
        Remove-Item -LiteralPath $downloadDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
    & py -m kaggle kernels output $KernelSlug -p $downloadDir -o --file-pattern ("apd_cloud_run_{0}\.zip" -f $RunLabel)
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Kaggle output download failed for $RunLabel with exit code $LASTEXITCODE"
        return $false
    }
    $zips = @(Get-ChildItem -LiteralPath $downloadDir -Recurse -File -Filter "*.zip")
    if ($zips.Count -ne 1 -or $zips[0].FullName -ne (Resolve-Path -LiteralPath $expectedZip -ErrorAction SilentlyContinue).Path) {
        Write-Log "Expected exactly one ZIP at $expectedZip; found $($zips.Count)."
        foreach ($zip in $zips) { Write-Log "ZIP candidate: $($zip.FullName)" }
        return $false
    }
    Invoke-ProjectPython -ArgList @("scripts\import_cloud_zip.py", $expectedZip)
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Import failed for $expectedZip with exit code $LASTEXITCODE"
        return $false
    }
    Invoke-ProjectPython -ArgList @("scripts\09_progress_dashboard.py")
    Write-Log "Recovered and imported completed kernel output: $RunLabel"
    return $true
}

function Save-FailedKernelLogs {
    param(
        [string]$RunLabel,
        [string]$KernelSlug
    )
    $logDir = Join-Path $repoRoot ("results\cloud_runs\{0}" -f $RunLabel)
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $logs = & py -m kaggle kernels logs $KernelSlug 2>&1
    $text = ($logs -join "`n")
    Set-Content -LiteralPath (Join-Path $logDir "kaggle_failure.log") -Value $text -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $logsDir ("kaggle_{0}_failure.log" -f $RunLabel)) -Value $text -Encoding UTF8
    Write-Log "Saved failed kernel logs for $RunLabel under $logDir"
}

function Wait-ExistingRunImport {
    param(
        [string]$RunLabel,
        [string]$KernelSlug
    )
    $runLog = Join-Path $logsDir ("kaggle_{0}_run.out.log" -f $RunLabel)
    Write-Log "Waiting for existing run/import: $RunLabel"
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $runLog) {
            $tail = (Get-Content -LiteralPath $runLog -Tail 120 -ErrorAction SilentlyContinue) -join "`n"
            if ($tail -match "Kaggle batch complete: $([regex]::Escape($RunLabel))") {
                Write-Log "Existing run already imported: $RunLabel"
                return $true
            }
        }
        $status = Get-KaggleStatus -KernelSlug $KernelSlug
        Write-Log "Existing kernel status: $status"
        $state = Get-KernelState -Text $status
        if ($state -eq "complete") {
            return (Import-CompletedKernelOutput -RunLabel $RunLabel -KernelSlug $KernelSlug)
        }
        if ($state -eq "failed") {
            Save-FailedKernelLogs -RunLabel $RunLabel -KernelSlug $KernelSlug
            return $false
        }
        Start-Sleep -Seconds $PollSeconds
    }
    Write-Log "Deadline reached while waiting for existing run: $RunLabel"
    return $false
}

function Invoke-KaggleBatch {
    param(
        [string]$Model,
        [string]$Language,
        [int]$ShardId,
        [int]$NShards,
        [int]$MaxImages,
        [string]$BaseRunLabel,
        [string]$KernelSlug = ""
    )
    $attempt = 1
    while ($attempt -le $MaxRetriesPerBatch -and (Get-Date) -lt $deadline) {
        $runLabel = "{0}_try{1}" -f $BaseRunLabel, $attempt
        $stdout = Join-Path $logsDir ("kaggle_{0}_run.out.log" -f $runLabel)
        $stderr = Join-Path $logsDir ("kaggle_{0}_run.err.log" -f $runLabel)
        Write-Log "Starting batch $runLabel model=$Model language=$Language shard=$ShardId/$NShards max=$MaxImages"
        if ($DryRun) {
            Write-Log "DRY RUN would call run_kaggle_batch.ps1 for $runLabel"
            return $true
        }
        $args = @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ".\scripts\run_kaggle_batch.ps1",
            "-Model", $Model,
            "-Language", $Language,
            "-ShardId", [string]$ShardId,
            "-NShards", [string]$NShards,
            "-MaxImages", [string]$MaxImages,
            "-RunLabel", $runLabel,
            "-CudaProfile", "p100"
        )
        if ($KernelSlug) {
            $args += @("-KernelSlug", $KernelSlug)
        }
        $proc = Start-Process -FilePath "powershell.exe" -ArgumentList $args -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
        $proc.WaitForExit()
        $proc.Refresh()
        $outTail = ""
        $errTail = ""
        if (Test-Path -LiteralPath $stdout) { $outTail = (Get-Content -LiteralPath $stdout -Tail 80 -ErrorAction SilentlyContinue) -join "`n" }
        if (Test-Path -LiteralPath $stderr) { $errTail = (Get-Content -LiteralPath $stderr -Tail 80 -ErrorAction SilentlyContinue) -join "`n" }
        if ($outTail -match "Kaggle batch complete: $([regex]::Escape($runLabel))") {
            Write-Log "Completed and imported batch $runLabel"
            return $true
        }
        Write-Log "Batch $runLabel exited with code $($proc.ExitCode). Will retry after waiting."
        if ($outTail) { Add-Content -LiteralPath $supervisorLog -Value $outTail -Encoding UTF8 }
        if ($errTail) { Add-Content -LiteralPath $supervisorLog -Value $errTail -Encoding UTF8 }
        Start-Sleep -Seconds $PollSeconds
        $attempt += 1
    }
    Write-Log "Giving up batch after retries/deadline: $BaseRunLabel"
    return $false
}

Set-Location -LiteralPath $repoRoot
Write-Log "Overnight supervisor started. Deadline=$deadline PollSeconds=$PollSeconds MaxRetriesPerBatch=$MaxRetriesPerBatch"

if ($CurrentRunLabel -and $CurrentKernelSlug) {
    $currentImported = Wait-ExistingRunImport -RunLabel $CurrentRunLabel -KernelSlug $CurrentKernelSlug
    if (-not $currentImported) {
        Write-Log "Stopping because the current run did not finish/import before deadline."
        exit 1
    }
}

$queue = @(
    @{ Model = "stabilityai/stable-diffusion-xl-base-1.0"; Language = "es-LatAm"; ShardId = 0; NShards = 4; MaxImages = 500; BaseRunLabel = "sdxl_esLatAm_s0_b500_p100" },
    @{ Model = "stabilityai/stable-diffusion-xl-base-1.0"; Language = "es-LatAm"; ShardId = 1; NShards = 4; MaxImages = 500; BaseRunLabel = "sdxl_esLatAm_s1_b500_p100" },
    @{ Model = "stabilityai/stable-diffusion-xl-base-1.0"; Language = "es-LatAm"; ShardId = 2; NShards = 4; MaxImages = 500; BaseRunLabel = "sdxl_esLatAm_s2_b500_p100" },
    @{ Model = "stabilityai/stable-diffusion-xl-base-1.0"; Language = "es-LatAm"; ShardId = 3; NShards = 4; MaxImages = 500; BaseRunLabel = "sdxl_esLatAm_s3_b500_p100" },
    @{ Model = "stabilityai/stable-diffusion-xl-base-1.0"; Language = "pt-BR";    ShardId = 0; NShards = 4; MaxImages = 500; BaseRunLabel = "sdxl_ptBR_s0_b500_p100" },
    @{ Model = "stabilityai/stable-diffusion-xl-base-1.0"; Language = "pt-BR";    ShardId = 1; NShards = 4; MaxImages = 500; BaseRunLabel = "sdxl_ptBR_s1_b500_p100" },
    @{ Model = "stabilityai/stable-diffusion-xl-base-1.0"; Language = "pt-BR";    ShardId = 2; NShards = 4; MaxImages = 500; BaseRunLabel = "sdxl_ptBR_s2_b500_p100"; KernelSlug = "henrylaverde/apd-batch-sdxl-ptbr-s1-b500-p100-try1" },
    @{ Model = "stabilityai/stable-diffusion-xl-base-1.0"; Language = "pt-BR";    ShardId = 3; NShards = 4; MaxImages = 500; BaseRunLabel = "sdxl_ptBR_s3_b500_p100"; KernelSlug = "henrylaverde/apd-batch-sdxl-ptbr-s1-b500-p100-try1" }
)

if ($StartQueueIndex -lt 0 -or $StartQueueIndex -ge $queue.Count) {
    Write-Log "StartQueueIndex $StartQueueIndex is outside queue bounds 0..$($queue.Count - 1)."
    exit 1
}

foreach ($batch in $queue[$StartQueueIndex..($queue.Count - 1)]) {
    if ((Get-Date) -ge $deadline) {
        Write-Log "Deadline reached before starting next batch."
        break
    }
    $ok = Invoke-KaggleBatch `
        -Model $batch.Model `
        -Language $batch.Language `
        -ShardId $batch.ShardId `
        -NShards $batch.NShards `
        -MaxImages $batch.MaxImages `
        -BaseRunLabel $batch.BaseRunLabel `
        -KernelSlug $batch.KernelSlug
    if (-not $ok) {
        Write-Log "Stopping overnight queue at failed batch $($batch.BaseRunLabel)."
        exit 1
    }
}

Write-Log "Overnight supervisor finished."
Invoke-ProjectPython -ArgList @("scripts\09_progress_dashboard.py")
