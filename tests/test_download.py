from pathlib import Path

from jobfinder.config import HUMANIZER_GGUF_FILE
from jobfinder.download import (
    affine_model_source,
    affine_weights_ready,
    cache_status,
    download_all,
    download_affine,
    humanizer_weights_ready,
)


def test_affine_model_source_uses_repo_when_cache_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("jobfinder.download.AFFINE_CACHE_DIR", tmp_path / "affine-s6")
    assert affine_weights_ready() is False
    model_id, revision = affine_model_source()
    assert model_id == "WebScraper991923/Affine-S6"
    assert revision


def test_download_all_uses_injected_downloaders(tmp_path, monkeypatch):
    affine_dir = tmp_path / "affine-s6"
    gguf_dir = tmp_path / "gguf"
    monkeypatch.setattr("jobfinder.download.AFFINE_CACHE_DIR", affine_dir)
    monkeypatch.setattr("jobfinder.download.HUMANIZER_CACHE_DIR", gguf_dir)
    monkeypatch.setattr("jobfinder.config.HUMANIZER_CACHE_DIR", gguf_dir)

    def fake_snap(**kwargs):
        dest = Path(kwargs["local_dir"])
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "config.json").write_text("{}")
        (dest / "model.safetensors").write_bytes(b"weights")
        assert "WebScraper991923/Affine-S6" in kwargs["repo_id"]
        return str(dest)

    def fake_hub(**kwargs):
        dest = Path(kwargs["local_dir"])
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / kwargs["filename"]
        path.write_bytes(b"0" * 1_000_001)
        return str(path)

    results = download_all(
        affine_downloader=fake_snap,
        humanizer_downloader=fake_hub,
    )
    assert affine_weights_ready() is True
    assert humanizer_weights_ready() is True
    assert Path(results["affine"]).exists()
    assert Path(results["humanizer"]).stat().st_size > 1_000_000
    model_id, revision = affine_model_source()
    assert Path(model_id) == affine_dir
    assert revision is None


def test_download_affine_passes_allow_patterns(tmp_path, monkeypatch):
    monkeypatch.setattr("jobfinder.download.AFFINE_CACHE_DIR", tmp_path)
    seen = {}

    def fake_snap(**kwargs):
        seen.update(kwargs)
        (tmp_path / "config.json").write_text("{}")
        (tmp_path / "model.safetensors").write_bytes(b"x")
        return str(tmp_path)

    path = download_affine(downloader=fake_snap)
    assert path == tmp_path
    assert "*.safetensors" in seen["allow_patterns"]
    assert seen["token"] is None or isinstance(seen["token"], str)


def test_cache_status_lists_models_not_secrets():
    blob = " ".join(f"{item.detail} {item.repo}" for item in cache_status())
    assert "WebScraper991923/Affine-S6" in blob
    assert "mradermacher/Ai-Humanizer-Llama-3.2-3B-GGUF" in blob
    assert HUMANIZER_GGUF_FILE in blob
    assert "hf_" not in blob
    assert "re_" not in blob
