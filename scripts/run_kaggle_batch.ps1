param(
    [Parameter(Mandatory=$true)][string]$Model,
    [Parameter(Mandatory=$true)][string]$Language,
    [Parameter(Mandatory=$true)][int]$ShardId,
    [Parameter(Mandatory=$true)][int]$NShards,
    [Parameter(Mandatory=$true)][int]$MaxImages,
    [Parameter(Mandatory=$true)][string]$RunLabel,
    [string]$KernelSlug = "",
    [ValidateSet("main", "h5", "robustness")][string]$Grid = "main",
    [ValidateSet("auto", "p100")][string]$CudaProfile = "auto",
    [ValidateSet("", "kaggle", "colab")][string]$RecommendedRunnerFilter = "",
    [int]$PollSeconds = 60,
    [int]$TimeoutMinutes = 720,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

function Get-RepoRoot {
    $scriptPath = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $scriptPath "..")).Path
}

function Convert-ToSlug {
    param([string]$Text)
    $slug = $Text.ToLowerInvariant() -replace "[^a-z0-9]+", "-"
    $slug = $slug.Trim("-")
    if (-not $slug) { throw "RunLabel cannot be slugified: $Text" }
    return $slug
}

function Get-VenvBasePython {
    param([string]$RepoRoot)
    $cfgPath = Join-Path $RepoRoot ".venv\pyvenv.cfg"
    if (-not (Test-Path -LiteralPath $cfgPath)) { return $null }
    $homeLine = Get-Content -LiteralPath $cfgPath | Where-Object { $_ -match '^home\s*=' } | Select-Object -First 1
    if (-not $homeLine) { return $null }
    $homeDir = ($homeLine -split '=', 2)[1].Trim()
    if (-not $homeDir) { return $null }
    $candidate = Join-Path $homeDir "python.exe"
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    return $null
}

function Enable-ProjectPythonPath {
    param([string]$RepoRoot)
    $sitePackages = Join-Path $RepoRoot ".venv\Lib\site-packages"
    if (-not (Test-Path -LiteralPath $sitePackages)) { return }
    if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
        $env:PYTHONPATH = $sitePackages
        return
    }
    $parts = $env:PYTHONPATH -split ';'
    if ($parts -notcontains $sitePackages) {
        $env:PYTHONPATH = "$sitePackages;$env:PYTHONPATH"
    }
}

function Get-KaggleCommand {
    try {
        $null = & py -m kaggle --version 2>$null
        return @("py", "-m", "kaggle")
    } catch {
        # Fall through to project/global CLI checks.
    }
    $repoRoot = Get-RepoRoot
    $projectPython = Get-ProjectPython -RepoRoot $repoRoot
    if ($projectPython) {
        try {
            $null = & $projectPython -m kaggle --version 2>$null
            return @($projectPython, "-m", "kaggle")
        } catch {
            # Fall through to global CLI checks.
        }
    }
    $cmd = Get-Command kaggle.exe -ErrorAction SilentlyContinue
    if ($cmd) { return @($cmd.Source) }
    try {
        $null = & python -m kaggle --version 2>$null
        return @("python", "-m", "kaggle")
    } catch {
        throw "Kaggle CLI not found. Install/authenticate with: python -m pip install --user kaggle ; python -m kaggle auth login"
    }
}

function Enable-KaggleProcessToken {
    param([string[]]$KaggleCmd)
    if ($env:KAGGLE_API_TOKEN) {
        Write-Host "Kaggle API token already present in process environment."
        return
    }
    # ``kaggle auth print-access-token`` can block indefinitely on this host.
    # The CLI already falls back to its stored authenticated credentials for
    # every command below, so avoid that optional token lookup altogether.
    Write-Host "Using stored Kaggle CLI credentials."
}

function Invoke-Kaggle {
    param([string[]]$KaggleCmd, [string[]]$ArgList, [switch]$AllowFailure)
    $exe = $KaggleCmd[0]
    $prefix = @()
    if ($KaggleCmd.Count -gt 1) { $prefix = $KaggleCmd[1..($KaggleCmd.Count - 1)] }
    $allArgs = @($prefix + $ArgList)
    Write-Host "+ $exe $($allArgs -join ' ')"
    & $exe @allArgs
    $code = $LASTEXITCODE
    if ($code -ne 0 -and -not $AllowFailure) {
        throw "Kaggle command failed with exit code $code"
    }
    return $code
}

function Invoke-KaggleCapture {
    param([string[]]$KaggleCmd, [string[]]$ArgList, [switch]$AllowFailure)
    $exe = $KaggleCmd[0]
    $prefix = @()
    if ($KaggleCmd.Count -gt 1) { $prefix = $KaggleCmd[1..($KaggleCmd.Count - 1)] }
    $allArgs = @($prefix + $ArgList)
    Write-Host "+ $exe $($allArgs -join ' ')"
    $output = & $exe @allArgs 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0 -and -not $AllowFailure) {
        $output | ForEach-Object { Write-Host $_ }
        throw "Kaggle command failed with exit code $code"
    }
    return [pscustomobject]@{ Code = $code; Output = ($output -join "`n") }
}

function Get-KernelState {
    param([string]$Text)
    $lower = $Text.ToLowerInvariant()
    if ($lower -match "complete|successful|succeeded") { return "complete" }
    if ($lower -match "error|fail|cancel") { return "failed" }
    if ($lower -match "running|queued|pending|preparing|starting") { return "running" }
    return "unknown"
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $enc)
}

function Write-JsonFile {
    param([object]$Object, [string]$Path)
    $json = $Object | ConvertTo-Json -Depth 20
    Write-Utf8NoBom -Path $Path -Text ($json + "`n")
}

function Get-ProjectPython {
    param([string]$RepoRoot)
    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        try {
            $null = & $venvPython -c "pass" 2>$null
            return $venvPython
        } catch {
            # uv trampoline can be present but unusable on this host.
        }
    }
    $basePython = Get-VenvBasePython -RepoRoot $RepoRoot
    if ($basePython) {
        Enable-ProjectPythonPath -RepoRoot $RepoRoot
        return $basePython
    }
    return "python"
}

function ConvertTo-PythonLiteral {
    param([object]$Value)
    if ($null -eq $Value) { return "None" }
    if ($Value -is [bool]) { if ($Value) { return "True" } else { return "False" } }
    if ($Value -is [int] -or $Value -is [long] -or $Value -is [double]) { return [string]$Value }
    $s = [string]$Value
    $s = $s.Replace("\", "\\").Replace("'", "\'")
    return "'$s'"
}

function New-KaggleScript {
    param([hashtable]$Config)
    $pairs = @()
    foreach ($key in $Config.Keys) {
        $pairs += "    '$key': $(ConvertTo-PythonLiteral $Config[$key]),"
    }
    $configLiteral = "{`n$($pairs -join "`n")`n}"
    return @"
"""Kaggle-side APD batch runner generated by scripts/run_kaggle_batch.ps1."""

from __future__ import annotations

import base64
import csv
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

CONFIG = $configLiteral
WORKING = pathlib.Path("/kaggle/working")


def run(cmd: list[str], *, cwd: pathlib.Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(cwd) if cwd else None, env=os.environ.copy())


def run_capture(cmd: list[str], *, cwd: pathlib.Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd), flush=True)
    try:
        proc = subprocess.run(
            cmd,
            check=check,
            cwd=str(cwd) if cwd else None,
            env=os.environ.copy(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        if check:
            raise
        proc = subprocess.CompletedProcess(cmd, 127, stdout=f"{exc}\n")
    print(proc.stdout, flush=True)
    return proc


def load_hf_token_from_kaggle_secret() -> bool:
    """Load the optional gated-model token without exposing its value."""
    try:
        from kaggle_secrets import UserSecretsClient
    except ImportError:
        print("Kaggle secrets client unavailable; HF_TOKEN not loaded", flush=True)
        return False
    try:
        token = UserSecretsClient().get_secret("HF_TOKEN")
    except Exception as exc:
        print(f"HF_TOKEN Kaggle secret unavailable: {type(exc).__name__}", flush=True)
        return False
    if not token or not token.strip():
        print("HF_TOKEN Kaggle secret is empty", flush=True)
        return False
    os.environ["HF_TOKEN"] = token.strip()
    os.environ["HUGGING_FACE_HUB_TOKEN"] = token.strip()
    print("HF_TOKEN loaded from Kaggle Secrets (value hidden)", flush=True)
    return True


def require_hf_model_access(model: str) -> None:
    """Fail before provisioning when a gated Hugging Face model is unavailable."""
    if not load_hf_token_from_kaggle_secret():
        raise RuntimeError(
            "HF_TOKEN could not be read from Kaggle Secrets. Enable HF_TOKEN in the "
            "notebook's Secrets panel, then Save & Run All before starting this batch."
        )

    url = f"https://huggingface.co/{model}/resolve/main/model_index.json"
    request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"Authorization": f"Bearer {os.environ['HF_TOKEN']}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Hugging Face access preflight failed: {exc.reason}") from exc

    if status != 200:
        raise RuntimeError(
            f"HF_TOKEN cannot access {model} (HTTP {status}). Confirm model access and "
            "a token with public gated-repository read permission before launching."
        )
    print("HF_TOKEN and gated-model access preflight passed", flush=True)


def print_gpu_diagnostics() -> str:
    print("=== Python diagnostics ===", flush=True)
    run_capture([sys.executable, "--version"], check=False)
    print("Python sys.version:", sys.version, flush=True)
    print("=== GPU diagnostics: nvidia-smi ===", flush=True)
    proc = run_capture(["nvidia-smi"], check=False)
    return proc.stdout or ""


def install_cuda_profile(repo_dir: pathlib.Path, nvidia_smi_output: str) -> None:
    profile = str(CONFIG.get("cuda_profile", "auto")).lower()
    if profile == "auto":
        print("CUDA profile: auto (using project uv.lock stack)", flush=True)
        return
    if profile != "p100":
        raise ValueError(f"Unsupported cuda_profile: {profile!r}")

    if "p100" not in nvidia_smi_output.lower() and "tesla p100" not in nvidia_smi_output.lower():
        print(
            "CUDA profile p100 requested, but nvidia-smi did not report P100. "
            "Keeping project uv.lock stack.",
            flush=True,
        )
        return

    print(
        "CUDA profile: p100. Installing PyTorch 2.7.1 + CUDA 11.8 wheels "
        "inside the temporary Kaggle uv environment with uv pip install.",
        flush=True,
    )
    help_proc = run_capture([sys.executable, "-m", "uv", "pip", "install", "--help"], cwd=repo_dir, check=False)
    if help_proc.returncode != 0:
        raise RuntimeError("Could not inspect uv pip install --help before P100 install")
    reinstall_flag = "--reinstall" if "--reinstall" in help_proc.stdout else "--force-reinstall"
    run(
        [
            sys.executable,
            "-m",
            "uv",
            "pip",
            "install",
            "--python",
            "/tmp/apd-venv/bin/python",
            reinstall_flag,
            "torch==2.7.1",
            "torchvision==0.22.1",
            "torchaudio==2.7.1",
            "--index-url",
            "https://download.pytorch.org/whl/cu118",
        ],
        cwd=repo_dir,
    )


def torch_cuda_probe(repo_dir: pathlib.Path, nvidia_smi_output: str) -> None:
    print("=== GPU diagnostics: torch CUDA probe ===", flush=True)
    probe = r'''
import torch

print("torch.__version__:", torch.__version__, flush=True)
print("torch.version.cuda:", torch.version.cuda, flush=True)
print("torch.cuda.is_available():", torch.cuda.is_available(), flush=True)
if torch.cuda.is_available():
    print("torch.cuda.get_device_name(0):", torch.cuda.get_device_name(0), flush=True)
    try:
        print("torch.cuda.get_device_capability(0):", torch.cuda.get_device_capability(0), flush=True)
    except Exception as exc:
        print("torch.cuda.get_device_capability(0): unavailable:", repr(exc), flush=True)
else:
    raise RuntimeError("CUDA is not available to torch")

x = torch.ones((1,), device="cuda")
print("CUDA smoke tensor:", x + 1, flush=True)
torch.cuda.synchronize()
print("CUDA smoke test OK", flush=True)
'''
    proc = run_capture([sys.executable, "-m", "uv", "run", "python", "-c", probe], cwd=repo_dir, check=False)
    text = (nvidia_smi_output + "\n" + proc.stdout).lower()
    is_p100 = "p100" in text or "tesla p100" in text
    profile = str(CONFIG.get("cuda_profile", "auto")).lower()
    if proc.returncode == 0:
        if is_p100:
            print(
                "WARNING: Kaggle assigned a P100, but the current torch/CUDA smoke test passed. "
                "Continuing because compatibility was verified before model downloads.",
                flush=True,
            )
        return
    if is_p100:
        raise RuntimeError(
            f"Kaggle CLI assigned a P100 GPU and cuda_profile={profile!r} failed the "
            "pre-generation CUDA smoke test. Aborting before downloading Hugging Face "
            "models. Try -CudaProfile p100 for the explicit PyTorch 2.7.1 + CUDA 11.8 "
            "candidate stack, or keep production on a non-P100 Kaggle GPU."
        )
    raise RuntimeError("PyTorch/CUDA smoke test failed before generation; see diagnostics above.")


def remove_path(path: pathlib.Path) -> None:
    if path.exists():
        shutil.rmtree(path) if path.is_dir() else path.unlink()


def free_transient_disk() -> None:
    print("=== Freeing transient disk before final ZIP ===", flush=True)
    for raw in ["/tmp/hf-cache", "/tmp/uv-cache", "/tmp/pip-cache", "/root/.cache/pip", "/root/.cache/uv"]:
        path = pathlib.Path(raw)
        if path.exists():
            print("removing", path, flush=True)
            remove_path(path)


def make_rescue_zip(output_root: pathlib.Path, rescue_zip: pathlib.Path) -> None:
    metadata_files = sorted(output_root.glob("images/main/metadata_*.parquet"))
    if not metadata_files:
        print("rescue zip skipped: no metadata parquet yet", flush=True)
        return
    tmp_base = rescue_zip.with_suffix(".tmp")
    tmp_zip = tmp_base.with_suffix(".zip")
    if tmp_zip.exists():
        tmp_zip.unlink()
    print(f"writing rescue zip: {rescue_zip.name}", flush=True)
    archive = pathlib.Path(shutil.make_archive(str(tmp_base), "zip", output_root))
    archive.replace(rescue_zip)
    size_mib = rescue_zip.stat().st_size / (1024 * 1024)
    print(f"rescue zip ready: {rescue_zip.name} ({size_mib:.2f} MiB)", flush=True)


def run_generation_with_rescue(
    cmd: list[str],
    *,
    cwd: pathlib.Path,
    output_root: pathlib.Path,
    rescue_zip: pathlib.Path,
) -> None:
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.Popen(cmd, cwd=str(cwd), env=os.environ.copy())
    last_zip_at = 0.0
    last_metadata_mtime = 0.0
    try:
        while proc.poll() is None:
            time.sleep(60)
            metadata_files = sorted(output_root.glob("images/main/metadata_*.parquet"))
            if not metadata_files:
                continue
            metadata_mtime = max(p.stat().st_mtime for p in metadata_files)
            now = time.time()
            if metadata_mtime > last_metadata_mtime and now - last_zip_at >= 600:
                make_rescue_zip(output_root, rescue_zip)
                last_metadata_mtime = metadata_mtime
                last_zip_at = now
        if proc.returncode != 0:
            make_rescue_zip(output_root, rescue_zip)
            raise subprocess.CalledProcessError(proc.returncode, cmd)
        make_rescue_zip(output_root, rescue_zip)
    except BaseException:
        try:
            make_rescue_zip(output_root, rescue_zip)
        except Exception as exc:  # noqa: BLE001 - best-effort rescue during failures.
            print(f"rescue zip failed during exception handling: {type(exc).__name__}: {exc}", flush=True)
        raise


def install_tokenizer_extras(repo_dir: pathlib.Path) -> None:
    python_path = pathlib.Path("/tmp/apd-venv/bin/python")
    if not python_path.exists():
        raise FileNotFoundError(f"Expected uv project python at {python_path}")
    print("=== Installing tokenizer extras into /tmp/apd-venv ===", flush=True)
    run([
        sys.executable,
        "-m",
        "uv",
        "pip",
        "install",
        "--python",
        str(python_path),
        "sentencepiece>=0.2",
        "tiktoken>=0.7",
        "protobuf>=4.25",
    ], cwd=repo_dir)


def install_alt_diffusion_compatibility_shim(repo_dir: pathlib.Path) -> None:
    """Restore the legacy module name referenced by AltDiffusion's model index."""
    if CONFIG.get("model") != "BAAI/AltDiffusion-m18":
        return
    python_path = pathlib.Path("/tmp/apd-venv/bin/python")
    if not python_path.exists():
        raise FileNotFoundError(f"Expected uv project python at {python_path}")
    shim = '''from diffusers.pipelines.deprecated.alt_diffusion.modeling_roberta_series import (\n    RobertaSeriesModelWithTransformation,\n)\n'''
    code = '''import pathlib\nimport diffusers\nshim = {shim!r}\npath = pathlib.Path(diffusers.__file__).resolve().parent / "pipelines" / "alt_diffusion.py"\npath.write_text(shim, encoding="utf-8")\nprint("Installed AltDiffusion compatibility shim:", path, flush=True)\n'''.format(shim=shim)
    run([str(python_path), "-c", code], cwd=repo_dir)


def patch_cloud_runner_internal_zip(repo_dir: pathlib.Path) -> None:
    path = repo_dir / "scripts" / "cloud_generation_runner.py"
    text = path.read_text(encoding="utf-8")
    old = '''def make_zip(output_root: Path, zip_base: Path) -> Path:
    zip_base.parent.mkdir(parents=True, exist_ok=True)
    archive = shutil.make_archive(str(zip_base), "zip", root_dir=output_root)
    return Path(archive)
'''
    new = '''def make_zip(output_root: Path, zip_base: Path) -> Path:
    zip_base.parent.mkdir(parents=True, exist_ok=True)
    log.info("skip internal zip; caller packages output_root")
    return zip_base.with_suffix(".zip")
'''
    if old not in text:
        raise RuntimeError("Could not patch cloud_generation_runner.py make_zip")
    path.write_text(text.replace(old, new), encoding="utf-8")
    print("Patched cloud_generation_runner.py to skip internal ZIP", flush=True)


def patch_cloud_runner_recommended_filter(repo_dir: pathlib.Path) -> None:
    path = repo_dir / "scripts" / "cloud_generation_runner.py"
    text = path.read_text(encoding="utf-8")
    if "--recommended-runner-filter" in text:
        print("cloud_generation_runner.py already supports recommended-runner-filter", flush=True)
        return
    text = text.replace(
        "    runner: str | None,\n    done_ids: set[str],",
        "    recommended_runner_filter: str | None,\n    done_ids: set[str],",
    )
    text = text.replace(
        '    if runner:\n        df = df[df["recommended_runner"] == runner]',
        '    if recommended_runner_filter:\n        df = df[df["recommended_runner"] == recommended_runner_filter]',
    )
    text = text.replace(
        "        runner=args.runner,\n        done_ids=done_ids,",
        "        recommended_runner_filter=args.recommended_runner_filter or args.runner,\n        done_ids=done_ids,",
    )
    text = text.replace(
        '                f"runner={args.runner}",',
        '                f"runner={args.runner}",\n                f"recommended_runner_filter={args.recommended_runner_filter or args.runner}",',
    )
    text = text.replace(
        '    parser.add_argument("--runner", choices=["kaggle", "colab"], required=True)',
        '    parser.add_argument("--runner", choices=["kaggle", "colab"], required=True)\n    parser.add_argument("--recommended-runner-filter", choices=["kaggle", "colab"], default=None)',
    )
    path.write_text(text, encoding="utf-8")
    print("Patched cloud_generation_runner.py recommended-runner-filter support", flush=True)


def patch_cloud_runner_manifest_robustness(repo_dir: pathlib.Path) -> None:
    path = repo_dir / "scripts" / "cloud_generation_runner.py"
    text = path.read_text(encoding="utf-8")
    changed = False
    if "def normalize_manifest(" not in text:
        marker = "\n\ndef select_rows(\n"
        helper = r'''

def normalize_manifest(manifest: pd.DataFrame, *, default_grid: str | None) -> pd.DataFrame:
    df = manifest.copy()
    df.columns = [str(col).strip() for col in df.columns]
    if "grid" not in df.columns:
        if "shard_group" in df.columns:
            df["grid"] = df["shard_group"].astype(str).str.split("|", n=1).str[0]
        elif default_grid:
            df["grid"] = default_grid
    required = {
        "model",
        "language",
        "grid",
        "recommended_runner",
        "prompt_status",
        "image_id",
        "occupation",
        "seed",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(
            "Manifest is missing required columns "
            f"{missing}; available columns are {list(df.columns)}"
        )
    return df
'''
        if marker not in text:
            raise RuntimeError("Could not patch cloud_generation_runner.py manifest normalizer")
        text = text.replace(marker, helper + marker, 1)
        changed = True
    replacements = {
        "    df = manifest.copy()\n    df = df[(df[\"model\"] == model) & (df[\"language\"] == language)]":
            "    df = normalize_manifest(manifest, default_grid=grid)\n    df = df[(df[\"model\"] == model) & (df[\"language\"] == language)]",
        "        recommended_runner_filter=args.recommended_runner_filter or args.runner,":
            "        recommended_runner_filter=args.recommended_runner_filter,",
        '                f"recommended_runner_filter={args.recommended_runner_filter or args.runner}",':
            '                f"recommended_runner_filter={args.recommended_runner_filter}",',
    }
    for old, new in replacements.items():
        if old in text:
            text = text.replace(old, new)
            changed = True
    if changed:
        path.write_text(text, encoding="utf-8")
        print("Patched cloud_generation_runner.py manifest robustness", flush=True)
    else:
        print("cloud_generation_runner.py manifest robustness already present", flush=True)


def patch_local_backend_pipeline_overrides(repo_dir: pathlib.Path) -> None:
    path = repo_dir / "src" / "apd" / "generate" / "local_backend.py"
    text = path.read_text(encoding="utf-8")
    changed = False
    if "AltDiffusionPipeline" not in text:
        old = '''        self.pipe = AutoPipelineForText2Image.from_pretrained(
            model,
            torch_dtype=dtype,
        ).to(self.device)
'''
        new = '''        pipeline_cls = AutoPipelineForText2Image
        if model == "BAAI/AltDiffusion-m18":
            from diffusers import AltDiffusionPipeline  # noqa: WPS433

            pipeline_cls = AltDiffusionPipeline
        self.pipe = pipeline_cls.from_pretrained(
            model,
            torch_dtype=dtype,
        ).to(self.device)
'''
        if old not in text:
            raise RuntimeError("Could not patch local_backend.py pipeline override")
        text = text.replace(old, new)
        changed = True
    if 'load_kwargs["variant"] = "fp16"' not in text:
        old = '''        self.pipe = pipeline_cls.from_pretrained(
            model,
            torch_dtype=dtype,
        ).to(self.device)
'''
        new = '''        load_kwargs = {"torch_dtype": dtype}
        if model == "kandinsky-community/kandinsky-3":
            load_kwargs["variant"] = "fp16"
            load_kwargs["use_safetensors"] = True
        self.pipe = pipeline_cls.from_pretrained(
            model,
            **load_kwargs,
        )
        if model == "kandinsky-community/kandinsky-3" and self.device == "cuda":
            self.pipe.enable_sequential_cpu_offload()
        elif model == "stabilityai/stable-diffusion-3.5-medium" and self.device == "cuda":
            self.pipe.enable_model_cpu_offload()
        else:
            self.pipe = self.pipe.to(self.device)
'''
        if old not in text:
            raise RuntimeError("Could not patch local_backend.py Kandinsky fp16 variant")
        text = text.replace(old, new)
        changed = True
    if "RobertaSeriesModelWithTransformation" not in text:
        old = '''        if model == "BAAI/AltDiffusion-m18":
            from diffusers import AltDiffusionPipeline  # noqa: WPS433

            pipeline_cls = AltDiffusionPipeline
        load_kwargs = {"torch_dtype": dtype}
'''
        new = '''        if model == "BAAI/AltDiffusion-m18":
            from diffusers import AltDiffusionPipeline  # noqa: WPS433
            from diffusers.pipelines.deprecated.alt_diffusion.modeling_roberta_series import (  # noqa: WPS433
                RobertaSeriesModelWithTransformation,
            )
            from transformers import XLMRobertaTokenizer  # noqa: WPS433

            pipeline_cls = AltDiffusionPipeline
        load_kwargs = {"torch_dtype": dtype}
        if model == "BAAI/AltDiffusion-m18":
            load_kwargs["text_encoder"] = RobertaSeriesModelWithTransformation.from_pretrained(
                model, subfolder="text_encoder", torch_dtype=dtype
            )
            load_kwargs["tokenizer"] = XLMRobertaTokenizer.from_pretrained(
                model, subfolder="tokenizer"
            )
'''
        if old not in text:
            raise RuntimeError("Could not patch local_backend.py AltDiffusion components")
        text = text.replace(old, new)
        changed = True
    if "model_source = model" not in text:
        if "import pathlib\n" not in text:
            text = text.replace("import logging\n", "import logging\nimport pathlib\n", 1)
        if "import sys\n" not in text:
            text = text.replace("import time\n", "import time\nimport sys\n", 1)
        if "import importlib\n" not in text:
            text = text.replace("import io\n", "import io\nimport importlib\n", 1)
        old = '''        self.pipe = pipeline_cls.from_pretrained(
            model,
            **load_kwargs,
        )
'''
        new = '''        model_source = model
        if model == "BAAI/AltDiffusion-m18":
            # This legacy checkpoint declares a custom ``alt_diffusion``
            # text-encoder module that is no longer hosted upstream.  Make a
            # writable local snapshot and restore that tiny compatibility
            # module beside the text encoder before loading the pipeline.
            from huggingface_hub import snapshot_download  # noqa: WPS433

            model_source = snapshot_download(
                model,
                local_dir="/tmp/apd-alt-diffusion-m18",
            )
            compatibility_module = (
                pathlib.Path(model_source) / "text_encoder" / "alt_diffusion.py"
            )
            compatibility_module.write_text(
                "from diffusers.pipelines.deprecated.alt_diffusion.modeling_roberta_series "
                "import RobertaSeriesModelWithTransformation\\n",
                encoding="utf-8",
            )
            # The legacy model index imports ``alt_diffusion`` by its bare
            # module name, so expose the component folder to that import.
            sys.path.insert(0, str(compatibility_module.parent))
            # Diffusers 0.37 checks supplied components against its current
            # import registry.  Register the recovered legacy module as a
            # pipeline module so the loader accepts the checkpoint's native
            # Roberta-series text encoder without an invalid class check.
            import diffusers.pipelines  # noqa: WPS433

            setattr(
                diffusers.pipelines,
                "alt_diffusion",
                importlib.import_module("alt_diffusion"),
            )
            print(
                "Installed local AltDiffusion text-encoder compatibility module:",
                compatibility_module,
                flush=True,
            )
        self.pipe = pipeline_cls.from_pretrained(
            model_source,
            **load_kwargs,
        )
'''
        if old not in text:
            raise RuntimeError("Could not patch local_backend.py AltDiffusion local snapshot")
        text = text.replace(old, new)
        changed = True
    if 'sd2-community/stable-diffusion-2-1' not in text:
        old = '''        model_source = model
        if model == "BAAI/AltDiffusion-m18":
'''
        new = '''        model_source = (
            "sd2-community/stable-diffusion-2-1"
            if model == "stabilityai/stable-diffusion-2-1"
            else model
        )
        if model == "BAAI/AltDiffusion-m18":
'''
        if old not in text:
            raise RuntimeError("Could not patch local_backend.py SD 2.1 source override")
        text = text.replace(old, new, 1)
        changed = True
    if changed:
        path.write_text(text, encoding="utf-8")
        print("Patched local_backend.py pipeline overrides", flush=True)
    else:
        print("local_backend.py already supports pipeline overrides", flush=True)


def patch_cloud_runner_model_source(repo_dir: pathlib.Path) -> None:
    """Persist the actual public source when a retired model is mirrored."""
    path = repo_dir / "scripts" / "cloud_generation_runner.py"
    text = path.read_text(encoding="utf-8")
    if '"model_source"' in text:
        print("cloud_generation_runner.py already records model_source", flush=True)
        return
    old = '''        "model": row["model"],
        "occupation": row["occupation"],
'''
    new = '''        "model": row["model"],
        "model_source": (
            "sd2-community/stable-diffusion-2-1"
            if row["model"] == "stabilityai/stable-diffusion-2-1"
            else row["model"]
        ),
        "occupation": row["occupation"],
'''
    if old not in text:
        raise RuntimeError("Could not patch cloud_generation_runner.py model_source")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("Patched cloud_generation_runner.py model_source provenance", flush=True)


def install_current_metadata(repo_dir: pathlib.Path) -> None:
    payload = CONFIG.get("current_metadata_b64")
    if not payload:
        src = pathlib.Path("/kaggle/src/current_metadata.parquet")
        if src.exists():
            dest = repo_dir / "images" / "main" / "metadata.parquet"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f"Installed current metadata snapshot: {src} -> {dest}", flush=True)
            return
        print("No current metadata snapshot provided; using repository metadata", flush=True)
        return
    dest = repo_dir / "images" / "main" / "metadata.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(base64.b64decode(payload))
    print(f"Installed embedded current metadata snapshot -> {dest}", flush=True)


def install_current_manifest(repo_dir: pathlib.Path) -> None:
    payload = CONFIG.get("current_manifest_b64")
    if payload:
        dest = repo_dir / "results" / "missing_generation_manifest_2026-06-02.csv"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(base64.b64decode(payload))
        print(f"Installed embedded current manifest snapshot -> {dest}", flush=True)
        return
    src = pathlib.Path("/kaggle/src/current_manifest.csv")
    if not src.exists():
        print("No current manifest snapshot provided; using repository manifest", flush=True)
        return
    dest = repo_dir / "results" / "missing_generation_manifest_2026-06-02.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(f"Installed current manifest snapshot: {src} -> {dest}", flush=True)


def install_target_manifest(repo_dir: pathlib.Path) -> None:
    manifest_payload = CONFIG.get("target_manifest_b64")
    if manifest_payload:
        src = repo_dir / "results" / "missing_generation_manifest_2026-06-02.csv"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(base64.b64decode(manifest_payload))
        print(f"Installed embedded target manifest snapshot -> {src}", flush=True)
        return
    encoded = str(CONFIG.get("target_image_ids_b64", "")).strip()
    text = base64.b64decode(encoded).decode("utf-8") if encoded else ""
    text = text.strip()
    if not text:
        print("No embedded target image_id list provided; using current manifest", flush=True)
        return
    target_ids = [line.strip() for line in text.splitlines() if line.strip()]
    target_set = set(target_ids)
    src = repo_dir / "results" / "missing_generation_manifest_2026-06-02.csv"
    rows = []
    with src.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise RuntimeError(f"Manifest has no header: {src}")
        for row in reader:
            if row.get("image_id") in target_set:
                rows.append(row)
    if not rows:
        raise RuntimeError("Embedded target image_id list matched zero manifest rows")
    with src.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"Installed embedded target manifest: {len(rows)} rows from {len(target_ids)} target ids",
        flush=True,
    )
    print("First target id:", rows[0].get("image_id"), flush=True)
    print("Last target id:", rows[-1].get("image_id"), flush=True)


def main() -> int:
    print("cwd:", pathlib.Path.cwd(), flush=True)
    src = pathlib.Path("/kaggle/src")
    print("/kaggle/src files:", sorted(p.name for p in src.iterdir()) if src.exists() else "missing", flush=True)
    print("CONFIG:", CONFIG, flush=True)
    print("Python:", sys.version, flush=True)

    run_label = CONFIG["run_label"]
    repo_dir = WORKING / "apd-audit"
    output_root = WORKING / f"apd_cloud_run_{run_label}"
    final_zip = WORKING / f"apd_cloud_run_{run_label}.zip"
    rescue_zip = WORKING / f"apd_cloud_run_{run_label}_RESCUE.zip"

    os.environ["UV_PROJECT_ENVIRONMENT"] = "/tmp/apd-venv"
    os.environ["UV_LINK_MODE"] = "copy"
    os.environ["UV_CACHE_DIR"] = "/tmp/uv-cache"
    os.environ["PIP_CACHE_DIR"] = "/tmp/pip-cache"
    os.environ["HF_HOME"] = "/tmp/hf-cache"
    os.environ["TRANSFORMERS_CACHE"] = "/tmp/hf-cache"
    os.environ["DIFFUSERS_CACHE"] = "/tmp/hf-cache"
    require_hf_model_access(CONFIG["model"])
    nvidia_smi_output = print_gpu_diagnostics()

    for target in [repo_dir, output_root]:
        if target.exists():
            shutil.rmtree(target)
    if final_zip.exists():
        final_zip.unlink()
    if rescue_zip.exists():
        rescue_zip.unlink()

    run([
        "git", "clone",
        "--branch", CONFIG.get("repo_branch", "cloud-generation-20260602"),
        "--single-branch",
        CONFIG.get("repo_url", "https://github.com/hlaverde/apd-audit.git"),
        str(repo_dir),
    ])
    patch_cloud_runner_internal_zip(repo_dir)
    patch_cloud_runner_recommended_filter(repo_dir)
    patch_cloud_runner_manifest_robustness(repo_dir)
    patch_local_backend_pipeline_overrides(repo_dir)
    patch_cloud_runner_model_source(repo_dir)
    install_current_metadata(repo_dir)
    install_current_manifest(repo_dir)
    install_target_manifest(repo_dir)
    run([sys.executable, "-m", "pip", "install", "-q", "uv"])
    run([sys.executable, "-m", "uv", "sync", "--extra", "ml"], cwd=repo_dir)
    install_tokenizer_extras(repo_dir)
    install_alt_diffusion_compatibility_shim(repo_dir)
    install_cuda_profile(repo_dir, nvidia_smi_output)
    torch_cuda_probe(repo_dir, nvidia_smi_output)

    cmd = [
        sys.executable, "-m", "uv", "run", "python", "scripts/cloud_generation_runner.py",
        "--manifest", "results/missing_generation_manifest_2026-06-02.csv",
        "--existing-metadata", "images/main/metadata.parquet",
        "--output-root", str(output_root),
        "--runner", "kaggle",
        "--run-id", run_label,
        "--model", CONFIG["model"],
        "--language", CONFIG["language"],
        "--grid", CONFIG.get("grid", "main"),
        "--shard-id", str(CONFIG["shard_id"]),
        "--n-shards", str(CONFIG["n_shards"]),
        "--max-images-per-run", str(CONFIG["max_images_per_run"]),
        "--checkpoint-every", str(CONFIG.get("checkpoint_every", 10)),
        "--classify" if CONFIG.get("classify", True) else "--no-classify",
    ]
    if CONFIG.get("recommended_runner_filter"):
        cmd.extend(["--recommended-runner-filter", str(CONFIG["recommended_runner_filter"])])
    if CONFIG.get("dry_run", False):
        cmd.append("--dry-run")
    run_generation_with_rescue(cmd, cwd=repo_dir, output_root=output_root, rescue_zip=rescue_zip)
    free_transient_disk()

    if rescue_zip.exists():
        print("removing rescue zip after successful generation:", rescue_zip.name, flush=True)
        rescue_zip.unlink()

    for internal_zip in output_root.rglob("*.zip"):
        internal_zip.unlink()
    archive = pathlib.Path(shutil.make_archive(str(final_zip.with_suffix("")), "zip", output_root))

    metadata_files = sorted(output_root.glob("images/main/metadata_*.parquet"))
    if not metadata_files:
        raise FileNotFoundError("No metadata shard parquet was produced")
    metadata_path = metadata_files[-1]
    try:
        import pandas as pd
        n_images = int(len(pd.read_parquet(metadata_path)))
    except Exception:
        n_images = -1

    size_mib = archive.stat().st_size / (1024 * 1024)
    print("RUN_LABEL:", run_label, flush=True)
    print("ZIP name:", archive.name, flush=True)
    print(f"ZIP size: {size_mib:.2f} MiB", flush=True)
    print("Images generated:", n_images, flush=True)
    print("Metadata parquet included:", metadata_path.relative_to(output_root).as_posix(), flush=True)
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        assert any(name.endswith(metadata_path.name) for name in names), metadata_path.name

    for target in [repo_dir, output_root]:
        if target.exists():
            shutil.rmtree(target)
    for junk in [".venv", ".cache", "uv-cache", "pip-cache", "hf-cache"]:
        p = WORKING / junk
        if p.exists():
            shutil.rmtree(p) if p.is_dir() else p.unlink()

    remaining = sorted(p.name for p in WORKING.iterdir())
    expected = [archive.name]
    print("Remaining /kaggle/working entries:", remaining, flush=True)
    if remaining != expected:
        raise RuntimeError(f"Expected only {expected}, found {remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"@
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

if ($ShardId -lt 0 -or $ShardId -ge $NShards) { throw "ShardId must satisfy 0 <= ShardId < NShards" }
if ($MaxImages -lt 1) { throw "MaxImages must be >= 1" }

$runSlug = Convert-ToSlug $RunLabel
if (-not $KernelSlug) {
    $KernelSlug = "henrylaverde/apd-batch-$runSlug"
} elseif ($KernelSlug -notmatch "/") {
    # Kaggle's API requires an owner-qualified kernel id.  Accept a short
    # slug at the CLI boundary, but never write one into kernel-metadata.json.
    $KernelSlug = "henrylaverde/$KernelSlug"
}

$auditDir = Join-Path $repoRoot "kaggle_runner"
$stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) "apd_kaggle_runner"
$runnerDir = Join-Path $stageRoot $runSlug
$configPath = Join-Path $auditDir "apd_run_config.json"
$metadataAuditPath = Join-Path $auditDir "kernel-metadata.json"
$scriptAuditPath = Join-Path $auditDir "script.py"
$metadataPath = Join-Path $runnerDir "kernel-metadata.json"
$scriptPath = Join-Path $runnerDir "script.py"
$metadataSnapshotPath = Join-Path $runnerDir "current_metadata.parquet"
$manifestSnapshotPath = Join-Path $runnerDir "current_manifest.csv"
$downloadDir = Join-Path $repoRoot ("cloud_inbox\kaggle_{0}" -f $RunLabel)
$expectedZip = Join-Path $downloadDir ("apd_cloud_run_{0}.zip" -f $RunLabel)
$expectedRescueZip = Join-Path $downloadDir ("apd_cloud_run_{0}_RESCUE.zip" -f $RunLabel)

New-Item -ItemType Directory -Force -Path $auditDir | Out-Null
if (Test-Path $runnerDir) { Remove-Item -LiteralPath $runnerDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $runnerDir | Out-Null

$kaggleCmd = Get-KaggleCommand
$projectPython = Get-ProjectPython -RepoRoot $repoRoot
Write-Host "Repo root: $repoRoot"
Write-Host "Kaggle CLI: $($kaggleCmd -join ' ')"
Write-Host "Project Python: $projectPython"

$version = Invoke-KaggleCapture -KaggleCmd $kaggleCmd -ArgList @("--version")
Write-Host $version.Output
Enable-KaggleProcessToken -KaggleCmd $kaggleCmd
# Do not enumerate all private APD kernels here.  That endpoint can stall for
# minutes and is not needed to select, push, poll, or import this batch.

$localMetadataPath = Join-Path $repoRoot "images\main\metadata.parquet"
$localManifestPath = Join-Path $repoRoot "results\missing_generation_manifest_2026-06-02.csv"

$config = @{
    model = $Model
    language = $Language
    shard_id = $ShardId
    n_shards = $NShards
    max_images_per_run = $MaxImages
    run_label = $RunLabel
    repo_url = "https://github.com/hlaverde/apd-audit.git"
    repo_branch = "cloud-generation-20260602"
    grid = $Grid
    checkpoint_every = 10
    classify = $true
    dry_run = $false
    cuda_profile = $CudaProfile
    recommended_runner_filter = $RecommendedRunnerFilter
}

if (Test-Path -LiteralPath $localMetadataPath) {
    Copy-Item -LiteralPath $localMetadataPath -Destination $metadataSnapshotPath -Force
}
if (Test-Path -LiteralPath $localManifestPath) {
    $pendingManifestScript = @'
import sys
from pathlib import Path

import pandas as pd

manifest_path = Path(sys.argv[1])
metadata_path = Path(sys.argv[2])
out_path = Path(sys.argv[3])

manifest = pd.read_csv(manifest_path)
if metadata_path.exists():
    done = pd.read_parquet(metadata_path)
    done_ids = set(done.image_id.astype(str))
    manifest = manifest[~manifest.image_id.astype(str).isin(done_ids)]

out_path.parent.mkdir(parents=True, exist_ok=True)
manifest.to_csv(out_path, index=False)
print('Wrote pending manifest snapshot: {} ({} rows)'.format(out_path, len(manifest)))
'@
    & $projectPython -c $pendingManifestScript $localManifestPath $localMetadataPath $manifestSnapshotPath
    if ($LASTEXITCODE -ne 0) { throw "Failed to build pending manifest snapshot" }

    $targetIdsPath = Join-Path $runnerDir "target_image_ids.txt"
    $targetManifestPath = Join-Path $runnerDir "target_manifest.csv"
    $targetSelectorPath = Join-Path $runnerDir "select_target_ids.py"
    $targetIdsScript = @'
import hashlib
import sys
from pathlib import Path

import pandas as pd

manifest_path = Path(sys.argv[1])
model = sys.argv[2]
language = sys.argv[3]
grid = sys.argv[4]
shard_id = int(sys.argv[5])
n_shards = int(sys.argv[6])
max_images = int(sys.argv[7])
runner_filter = sys.argv[8]
if runner_filter == '__none__':
    runner_filter = None
out_path = Path(sys.argv[9])
target_manifest_path = Path(sys.argv[10])

def stable_shard(image_id: str, n_shards: int) -> int:
    if n_shards <= 1:
        return 0
    digest = hashlib.sha256(image_id.encode('utf-8')).hexdigest()[:16]
    return int(digest, 16) % n_shards

df = pd.read_csv(manifest_path)
print("Target selector argv:", repr(sys.argv), flush=True)
print("Target selector columns:", list(df.columns), flush=True)
df = df[(df["model"] == model) & (df["language"] == language)]
if grid:
    df = df[df["grid"] == grid]
if runner_filter:
    df = df[df["recommended_runner"] == runner_filter]
df = df[df["prompt_status"] == 'ok']
df = df[df["image_id"].astype(str).map(lambda x: stable_shard(x, n_shards) == shard_id)]
if df.empty:
    raise SystemExit('No target image_ids selected for this batch')
# `grid` has already been filtered above. Sorting by it again can fail when
# pandas carries an overlapping column after manifest/metadata reconciliation.
df = df.sort_values(['occupation', 'seed'], kind='stable')
if max_images > 0:
    df = df.head(max_images)
ids = df.image_id.astype(str).tolist()
if not ids:
    raise SystemExit('No target image_ids selected for this batch')
out_path.write_text('\n'.join(ids) + '\n', encoding='utf-8')
target_manifest_path.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(target_manifest_path, index=False)
print('Wrote embedded target image_id list: {} ids -> {}'.format(len(ids), out_path))
print('Wrote embedded target manifest rows: {} -> {}'.format(len(df), target_manifest_path))
print('First target id:', ids[0])
print('Last target id:', ids[-1])
'@
    $runnerFilterArg = if ($RecommendedRunnerFilter) { $RecommendedRunnerFilter } else { "__none__" }
    # PowerShell can strip embedded Python quotes when using ``python -c``.
    # Persisting this tiny selector preserves its column references exactly.
    Write-Utf8NoBom -Path $targetSelectorPath -Text ($targetIdsScript + "`n")
    & $projectPython $targetSelectorPath $manifestSnapshotPath $Model $Language $Grid $ShardId $NShards $MaxImages $runnerFilterArg $targetIdsPath $targetManifestPath
    if ($LASTEXITCODE -ne 0) { throw "Failed to build embedded target image_id list" }
    $targetIdsText = Get-Content -LiteralPath $targetIdsPath -Raw
    $config["target_image_ids_b64"] = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($targetIdsText))
    $targetManifestBytes = [System.IO.File]::ReadAllBytes($targetManifestPath)
    $config["target_manifest_b64"] = [Convert]::ToBase64String($targetManifestBytes)
}

Write-JsonFile -Object $config -Path $configPath
Write-Utf8NoBom -Path $scriptPath -Text ((New-KaggleScript -Config $config) + "`n")
Copy-Item -LiteralPath $scriptPath -Destination $scriptAuditPath -Force

$kernelTitleSeed = $RunLabel
if ($KernelSlug -and $KernelSlug -match "/") {
    $kernelTitleSeed = ($KernelSlug -split "/", 2)[1]
    $title = $kernelTitleSeed -replace '[_-]+', ' '
} else {
    $title = "APD batch $($kernelTitleSeed -replace '[_-]+', ' ')"
}
$metadata = [ordered]@{
    id = $KernelSlug
    title = $title
    code_file = "script.py"
    language = "python"
    kernel_type = "script"
    is_private = $true
    enable_gpu = $true
    enable_internet = $true
    dataset_sources = @()
    competition_sources = @()
    kernel_sources = @()
}
Write-JsonFile -Object $metadata -Path $metadataPath
Copy-Item -LiteralPath $metadataPath -Destination $metadataAuditPath -Force

python -m json.tool $metadataPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw "kernel-metadata.json failed python -m json.tool" }

Write-Host "Wrote audit config: $configPath"
Write-Host "Wrote generated script: $scriptPath"
Write-Host "Wrote audit script snapshot: $scriptAuditPath"
Write-Host "Wrote kernel metadata: $metadataPath"
if (Test-Path -LiteralPath $metadataSnapshotPath) { Write-Host "Wrote metadata snapshot: $metadataSnapshotPath" }
if (Test-Path -LiteralPath $manifestSnapshotPath) { Write-Host "Wrote manifest snapshot: $manifestSnapshotPath" }
Write-Host "Download dir: $downloadDir"

if ($DryRun) {
    Write-Host ""
    Write-Host "DRY RUN: would run:"
    Write-Host "  kaggle kernels push -p `"$runnerDir`" --accelerator gpu"
    Write-Host "  poll: kaggle kernels status $KernelSlug every $PollSeconds seconds up to $TimeoutMinutes minutes"
    Write-Host "  download: kaggle kernels output $KernelSlug -p `"$downloadDir`" -o --file-pattern `"apd_cloud_run_$RunLabel\.zip`""
    Write-Host "  rescue: on failure, download/import apd_cloud_run_$RunLabel`_RESCUE.zip if present"
    Write-Host "  import: `"$projectPython`" scripts\import_cloud_zip.py `"$expectedZip`""
    Write-Host "  grid: $Grid"
    Write-Host "  cuda_profile: $CudaProfile"
    if ($RecommendedRunnerFilter) { Write-Host "  recommended_runner_filter: $RecommendedRunnerFilter" }
    exit 0
}

$push = Invoke-KaggleCapture -KaggleCmd $kaggleCmd -ArgList @(
    "kernels", "push", "-p", $runnerDir, "--accelerator", "gpu"
) -AllowFailure
Write-Host $push.Output
if ($push.Output -match "Maximum weekly GPU quota" -or $push.Output -match "GPU quota") {
    $logsDir = Join-Path $repoRoot "results\logs"
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
    Set-Content -LiteralPath (Join-Path $logsDir ("kaggle_{0}_quota.log" -f $RunLabel)) -Value $push.Output -Encoding UTF8
    Write-Warning "Kaggle GPU quota reached; not polling because no kernel was started."
    exit 2
}
if ($push.Code -ne 0 -or $push.Output -match "Kernel push error") {
    $logsDir = Join-Path $repoRoot "results\logs"
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
    Set-Content -LiteralPath (Join-Path $logsDir ("kaggle_{0}_push_failure.log" -f $RunLabel)) -Value $push.Output -Encoding UTF8
    throw "Kaggle kernel push failed"
}

$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
$state = "unknown"
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds $PollSeconds
    $status = Invoke-KaggleCapture -KaggleCmd $kaggleCmd -ArgList @("kernels", "status", $KernelSlug) -AllowFailure
    Write-Host $status.Output
    $state = Get-KernelState -Text $status.Output
    if ($state -eq "complete") { break }
    if ($state -eq "failed") { break }
}

if ($state -ne "complete") {
    Write-Warning "Kaggle run did not complete successfully. State: $state"
    $logs = Invoke-KaggleCapture -KaggleCmd $kaggleCmd -ArgList @("kernels", "logs", $KernelSlug) -AllowFailure
    $logDir = Join-Path $repoRoot ("results\cloud_runs\{0}" -f $RunLabel)
    $logsDir = Join-Path $repoRoot "results\logs"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
    Set-Content -LiteralPath (Join-Path $logDir "kaggle_failure.log") -Value $logs.Output -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $logsDir ("kaggle_{0}_failure.log" -f $RunLabel)) -Value $logs.Output -Encoding UTF8
    Write-Warning "Logs saved under $logDir"
    if (Test-Path $downloadDir) { Remove-Item -LiteralPath $downloadDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
    Invoke-Kaggle -KaggleCmd $kaggleCmd -ArgList @(
        "kernels", "output", $KernelSlug,
        "-p", $downloadDir,
        "-o",
        "--file-pattern", ("apd_cloud_run_{0}_RESCUE\.zip" -f $RunLabel)
    ) -AllowFailure | Out-Null
    if (Test-Path -LiteralPath $expectedRescueZip) {
        Write-Warning "Found rescue ZIP; importing partial completed checkpoint: $expectedRescueZip"
        & $projectPython scripts\import_cloud_zip.py $expectedRescueZip
        & $projectPython scripts\09_progress_dashboard.py
        Write-Warning "Kaggle batch imported from rescue ZIP after non-complete state: $RunLabel"
        exit 0
    }
    Write-Warning "No rescue ZIP was available for import."
    exit 1
}

if (Test-Path $downloadDir) { Remove-Item -LiteralPath $downloadDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null

Invoke-Kaggle -KaggleCmd $kaggleCmd -ArgList @(
    "kernels", "output", $KernelSlug,
    "-p", $downloadDir,
    "-o",
    "--file-pattern", ("apd_cloud_run_{0}\.zip" -f $RunLabel)
)

$zips = @(Get-ChildItem -LiteralPath $downloadDir -Recurse -File -Filter "*.zip")
if ($zips.Count -ne 1 -or $zips[0].FullName -ne (Resolve-Path -LiteralPath $expectedZip -ErrorAction SilentlyContinue).Path) {
    Write-Host "ZIP candidates:"
    $zips | ForEach-Object { Write-Host "  $($_.FullName)" }
    throw "Expected exactly $expectedZip"
}

$badOutput = Get-ChildItem -LiteralPath $downloadDir -Recurse -Force | Where-Object {
    $_.Name -in @(".venv", "apd-audit", "uv-cache", "pip-cache", "hf-cache")
}
if ($badOutput) {
    Write-Warning "Downloaded output contains unexpected folders:"
    $badOutput | ForEach-Object { Write-Warning $_.FullName }
}

& $projectPython scripts\import_cloud_zip.py $expectedZip
& $projectPython scripts\09_progress_dashboard.py
Write-Host "Kaggle batch complete: $RunLabel"
