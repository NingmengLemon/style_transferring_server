"""WikiArt 风格目录管理。

风格候选定义来自外部 JSON 配置文件（默认 ``config/styles.json``），
运行时按需从 WikiArt 元数据中匹配代表性风格图并生成预览图。
"""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps

from .config import Settings, settings
from .logging_config import get_logger

logger = get_logger()


@dataclass(frozen=True)
class StyleInfo:
    """一个可供前端选择的风格。"""

    style_id: str
    name: str
    artist: str
    description: str
    preview_url: str
    image_path: Path


@dataclass(frozen=True)
class StyleCandidate:
    """外部配置里定义的风格候选。"""

    style_id: str
    name: str
    artist: str
    description: str
    query: str
    fallback_genre: str


def load_style_candidates(config_path: Path) -> tuple[StyleCandidate, ...]:
    """从 JSON 配置文件读取风格候选定义。"""

    if not config_path.exists():
        logger.warning("styles config not found: %s", config_path)
        return ()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("failed to read styles config %s: %s", config_path, exc)
        return ()

    entries = raw.get("styles", []) if isinstance(raw, dict) else raw
    candidates: list[StyleCandidate] = []
    for entry in entries:
        try:
            candidates.append(
                StyleCandidate(
                    style_id=entry["style_id"],
                    name=entry["name"],
                    artist=entry["artist"],
                    description=entry["description"],
                    query=entry["query"],
                    fallback_genre=entry["fallback_genre"],
                )
            )
        except (KeyError, TypeError) as exc:
            logger.error("invalid style entry skipped: %s (%s)", entry, exc)
    return tuple(candidates)


class StyleRegistry:
    """按需从 WikiArt 元数据中选择少量代表性风格图。"""

    def __init__(self, config: Settings = settings) -> None:
        self._config = config
        self._styles: dict[str, StyleInfo] | None = None

    @property
    def wikiart_dir(self) -> Path:
        return self._config.wikiart_dir

    @property
    def styles(self) -> dict[str, StyleInfo]:
        if self._styles is None:
            self._styles = self._load_styles()
        return self._styles

    def list_for_api(self) -> list[dict[str, str]]:
        """返回符合前端 API 文档的风格列表。"""

        return [
            {
                "style_id": style.style_id,
                "name": style.name,
                "artist": style.artist,
                "description": style.description,
                "preview_url": style.preview_url,
            }
            for style in self.styles.values()
        ]

    def get(self, style_id: str) -> StyleInfo | None:
        """按风格 ID 查找风格。"""

        return self.styles.get(style_id)

    def _load_styles(self) -> dict[str, StyleInfo]:
        from .config import ensure_runtime_dirs

        ensure_runtime_dirs(self._config)
        candidates = load_style_candidates(self._config.styles_config)
        csv_path = self.wikiart_dir / "classes.csv"
        rows = list(self._iter_csv_rows(csv_path)) if csv_path.exists() else []
        if not rows:
            logger.warning("wikiart classes.csv not found under %s", self.wikiart_dir)

        styles: dict[str, StyleInfo] = {}
        for candidate in candidates:
            image_path = self._find_image(rows, candidate)
            if image_path is None:
                logger.warning("no matching image for style '%s'", candidate.style_id)
                continue
            preview_url = self._ensure_preview(candidate.style_id, image_path)
            styles[candidate.style_id] = StyleInfo(
                style_id=candidate.style_id,
                name=candidate.name,
                artist=candidate.artist,
                description=candidate.description,
                preview_url=preview_url,
                image_path=image_path,
            )
        logger.info("style registry loaded: %d/%d styles", len(styles), len(candidates))
        return styles

    def _iter_csv_rows(self, csv_path: Path) -> Iterable[dict[str, str]]:
        with csv_path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            yield from reader

    def _find_image(
        self, rows: list[dict[str, str]], candidate: StyleCandidate
    ) -> Path | None:
        query = candidate.query.lower()
        fallback_genre = candidate.fallback_genre
        matches = [row for row in rows if query in row.get("filename", "").lower()]
        if not matches:
            artist_name = candidate.artist.lower()
            matches = [
                row for row in rows if row.get("artist", "").lower() == artist_name
            ]
        if not matches:
            matches = [
                row
                for row in rows
                if row.get("filename", "").startswith(f"{fallback_genre}/")
            ]

        for row in matches:
            path = self.wikiart_dir / row.get("filename", "")
            if path.is_file():
                return path
        return None

    def _ensure_preview(self, style_id: str, source_path: Path) -> str:
        preview_path = self._config.style_static_dir / f"{style_id}.jpg"
        if preview_path.exists():
            return f"/static/styles/{style_id}.jpg"
        try:
            with Image.open(source_path) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((self._config.preview_size, self._config.preview_size))
                image.save(preview_path, "JPEG", quality=88, optimize=True)
        except Exception:
            logger.exception("failed to build preview for '%s', copying raw", style_id)
            shutil.copyfile(source_path, preview_path)
        return f"/static/styles/{style_id}.jpg"


style_registry = StyleRegistry()
