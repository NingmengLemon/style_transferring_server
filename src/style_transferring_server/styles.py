"""WikiArt 风格目录管理。

风格候选定义来自外部 JSON 配置文件（默认 ``config/styles.json``），
运行时按需从 WikiArt 元数据中匹配代表性风格图并生成预览图。
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageOps

from .config import Settings, settings
from .constants import (
    STYLE_PREVIEW_IMAGE_FORMAT,
    STYLE_PREVIEW_QUALITY,
    ApiPath,
    StaticSubdir,
)
from .logging_config import get_logger
from .schemas import StyleCandidate, StyleInfo

logger = get_logger()


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
    if not isinstance(entries, list):
        logger.error(
            "styles config must be a list or contain a 'styles' list: %s", config_path
        )
        return ()

    candidates: list[StyleCandidate] = []
    for entry in entries:
        if not isinstance(entry, dict):
            logger.error("invalid style entry skipped: %s", entry)
            continue
        try:
            candidates.append(StyleCandidate.model_validate(entry))
        except ValueError as exc:
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

    def list_for_api(self) -> list[dict[str, Any]]:
        """返回符合前端 API 文档的风格列表。"""

        return [
            style.model_dump(
                mode="json",
                include={"style_id", "name", "artist", "description", "preview_url"},
            )
            for style in self.styles.values()
        ]

    def get(self, style_id: str) -> StyleInfo | None:
        """按风格 ID 查找风格。"""

        return self.styles.get(style_id)

    def _load_styles(self) -> dict[str, StyleInfo]:
        from .config import ensure_runtime_dirs

        ensure_runtime_dirs(self._config)
        logger.info("style registry loading: config=%s", self._config.styles_config)
        candidates = load_style_candidates(self._config.styles_config)
        csv_path = self.wikiart_dir / "classes.csv"
        logger.info("style registry reading wikiart metadata: csv=%s", csv_path)
        rows = list(self._iter_csv_rows(csv_path)) if csv_path.exists() else []
        if not rows:
            logger.warning("wikiart classes.csv not found under %s", self.wikiart_dir)

        styles: dict[str, StyleInfo] = {}
        for candidate in candidates:
            logger.info(
                "style registry resolving candidate: style_id=%s artist=%s query=%s fallback_genre=%s",
                candidate.style_id,
                candidate.artist,
                candidate.query,
                candidate.fallback_genre,
            )
            image_path = self._find_image(rows, candidate)
            if image_path is None:
                logger.warning("no matching image for style '%s'", candidate.style_id)
                continue
            logger.info(
                "style registry matched image: style_id=%s image_path=%s",
                candidate.style_id,
                image_path,
            )
            preview_url = self._ensure_preview(candidate.style_id, image_path)
            logger.info(
                "style registry preview ready: style_id=%s preview_url=%s",
                candidate.style_id,
                preview_url,
            )
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
        preview_filename = f"{style_id}.jpg"
        preview_path = self._config.style_static_dir / preview_filename
        preview_url = (
            f"{ApiPath.STATIC_PREFIX}/{StaticSubdir.STYLES}/{preview_filename}"
        )
        if preview_path.exists():
            logger.info(
                "style preview reused: style_id=%s path=%s", style_id, preview_path
            )
            return preview_url
        logger.info(
            "style preview building: style_id=%s source=%s target=%s",
            style_id,
            source_path,
            preview_path,
        )
        try:
            with Image.open(source_path) as opened_image:
                converted_image = ImageOps.exif_transpose(opened_image).convert("RGB")
                converted_image.thumbnail(
                    (self._config.preview_size, self._config.preview_size)
                )
                converted_image.save(
                    preview_path,
                    STYLE_PREVIEW_IMAGE_FORMAT,
                    quality=STYLE_PREVIEW_QUALITY,
                    optimize=True,
                )
        except Exception:
            logger.exception("failed to build preview for '%s', copying raw", style_id)
            shutil.copyfile(source_path, preview_path)
        logger.info("style preview built: style_id=%s path=%s", style_id, preview_path)
        return preview_url


style_registry = StyleRegistry()
