"""Download Affine-S6 weights and the Ai-Humanizer GGUF into the local cache."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from jobfinder.config import (
    AFFINE_CACHE_DIR,
    AFFINE_S6_MODEL_ID,
    AFFINE_S6_REVISION,
    AFFINE_S6_URL,
    HF_TOKEN,
    HUMANIZER_CACHE_DIR,
    HUMANIZER_GGUF_FILE,
    HUMANIZER_MODEL_ID,
    HUMANIZER_URL,
    ROOT_DIR,
)

SnapshotFn = Callable[..., str]
HubDownloadFn = Callable[..., str]

AFFINE_ALLOW = (
    "config.json",
    "generation_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
    "model.safetensors.index.json",
    "*.safetensors",
    "LICENSE",
)


@dataclass
class DownloadItem:
    name: str
    repo: str
    url: str
    path: Path
    ready: bool
    detail: str


def affine_weights_ready() -> bool:
    if not (AFFINE_CACHE_DIR / "config.json").is_file():
        return False
    return any(AFFINE_CACHE_DIR.glob("*.safetensors"))


def humanizer_weights_ready() -> bool:
    cached = HUMANIZER_CACHE_DIR / HUMANIZER_GGUF_FILE
    return cached.is_file() and cached.stat().st_size > 1_000_000


def affine_model_source() -> tuple[str, str | None]:
    """Local cache path if weights exist, otherwise the Hugging Face repo id."""
    if affine_weights_ready():
        return str(AFFINE_CACHE_DIR), None
    return AFFINE_S6_MODEL_ID, AFFINE_S6_REVISION


def _package_ok(module: str) -> bool:
    try:
        __import__(module)
    except ImportError:
        return False
    return True


def cache_status() -> list[DownloadItem]:
    affine_ok = affine_weights_ready()
    gguf_ok = humanizer_weights_ready()
    torch_ok = _package_ok("torch") and _package_ok("transformers")
    llama_ok = _package_ok("llama_cpp")
    return [
        DownloadItem(
            name="Affine-S6 weights",
            repo=AFFINE_S6_MODEL_ID,
            url=AFFINE_S6_URL,
            path=AFFINE_CACHE_DIR,
            ready=affine_ok,
            detail="ready" if affine_ok else "missing (~8 GB)",
        ),
        DownloadItem(
            name="Humanizer GGUF",
            repo=HUMANIZER_MODEL_ID,
            url=HUMANIZER_URL,
            path=HUMANIZER_CACHE_DIR / HUMANIZER_GGUF_FILE,
            ready=gguf_ok,
            detail="ready" if gguf_ok else f"missing {HUMANIZER_GGUF_FILE} (~2.1 GB)",
        ),
        DownloadItem(
            name="torch + transformers",
            repo="torch, transformers, accelerate",
            url="",
            path=ROOT_DIR,
            ready=torch_ok,
            detail="installed" if torch_ok else "missing — pip install -e '.[ml]'",
        ),
        DownloadItem(
            name="llama-cpp-python",
            repo="llama-cpp-python",
            url="",
            path=ROOT_DIR,
            ready=llama_ok,
            detail="installed" if llama_ok else "missing — pip install -e '.[humanizer]'",
        ),
    ]


def download_affine(*, downloader: SnapshotFn | None = None) -> Path:
    from huggingface_hub import snapshot_download

    AFFINE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    snap = downloader or snapshot_download
    path = snap(
        repo_id=AFFINE_S6_MODEL_ID,
        revision=AFFINE_S6_REVISION,
        token=HF_TOKEN or None,
        local_dir=str(AFFINE_CACHE_DIR),
        allow_patterns=list(AFFINE_ALLOW),
    )
    return Path(path)


def download_humanizer(*, downloader: HubDownloadFn | None = None) -> Path:
    from jobfinder.humanizer import ensure_gguf

    if downloader is not None:
        HUMANIZER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = downloader(
            repo_id=HUMANIZER_MODEL_ID,
            filename=HUMANIZER_GGUF_FILE,
            token=HF_TOKEN or None,
            local_dir=str(HUMANIZER_CACHE_DIR),
        )
        return Path(path)
    return ensure_gguf()


def install_extras() -> None:
    import subprocess
    import sys

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-e",
        ".[ml,humanizer]",
    ]
    result = subprocess.run(cmd, cwd=str(ROOT_DIR), check=False)
    if result.returncode != 0:
        raise RuntimeError(
            "pip install -e '.[ml,humanizer]' failed. "
            "Install build tools (g++, cmake) and retry."
        )


def download_all(
    *,
    affine: bool = True,
    humanizer: bool = True,
    packages: bool = False,
    affine_downloader: SnapshotFn | None = None,
    humanizer_downloader: HubDownloadFn | None = None,
) -> dict[str, Path | str]:
    results: dict[str, Path | str] = {}
    if packages:
        install_extras()
        results["packages"] = "installed"
    if affine:
        results["affine"] = download_affine(downloader=affine_downloader)
    if humanizer:
        results["humanizer"] = download_humanizer(downloader=humanizer_downloader)
    return results
