"""配置加载与风格候选解析的单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

from style_transferring_server.config import Settings
from style_transferring_server.styles import load_style_candidates


def test_json_config_loaded(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"port": 9123, "log_level": "DEBUG", "warmup": False}),
        encoding="utf-8",
    )
    monkeypatch.setenv("STYLE_SERVER_CONFIG", str(config_file))
    settings = Settings()
    assert settings.port == 9123
    assert settings.log_level == "DEBUG"
    assert settings.warmup is False


def test_env_overrides_json(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"port": 9123}), encoding="utf-8")
    monkeypatch.setenv("STYLE_SERVER_CONFIG", str(config_file))
    monkeypatch.setenv("STYLE_SERVER_PORT", "7777")
    settings = Settings()
    # 环境变量优先级高于 JSON 文件。
    assert settings.port == 7777


def test_init_overrides_all(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"port": 9123}), encoding="utf-8")
    monkeypatch.setenv("STYLE_SERVER_CONFIG", str(config_file))
    monkeypatch.setenv("STYLE_SERVER_PORT", "7777")
    settings = Settings(port=5555)
    # 显式构造参数优先级最高。
    assert settings.port == 5555


def test_derived_dirs() -> None:
    settings = Settings(data_dir=Path("/tmp/data"))
    assert settings.output_dir == Path("/tmp/data/outputs")
    assert settings.results_dir == Path("/tmp/data/outputs/static/results")
    assert settings.wikiart_dir == Path("/tmp/data/dataset/wikiart")


def test_load_style_candidates(tmp_path: Path) -> None:
    config_file = tmp_path / "styles.json"
    config_file.write_text(
        json.dumps(
            {
                "styles": [
                    {
                        "style_id": "s1",
                        "name": "n1",
                        "artist": "a1",
                        "description": "d1",
                        "query": "q1",
                        "fallback_genre": "g1",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    candidates = load_style_candidates(config_file)
    assert len(candidates) == 1
    assert candidates[0].style_id == "s1"


def test_load_style_candidates_missing_file(tmp_path: Path) -> None:
    assert load_style_candidates(tmp_path / "nope.json") == ()


def test_load_style_candidates_skips_invalid(tmp_path: Path) -> None:
    config_file = tmp_path / "styles.json"
    config_file.write_text(
        json.dumps(
            {
                "styles": [
                    {
                        "style_id": "ok",
                        "name": "n",
                        "artist": "a",
                        "description": "d",
                        "query": "q",
                        "fallback_genre": "g",
                    },
                    {"style_id": "broken"},
                ]
            }
        ),
        encoding="utf-8",
    )
    candidates = load_style_candidates(config_file)
    assert len(candidates) == 1
    assert candidates[0].style_id == "ok"
