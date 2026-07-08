"""WikiArt 风格目录管理。"""

from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps

from .config import STYLE_STATIC_DIR, WIKIART_DIR, ensure_runtime_dirs, settings


@dataclass(frozen=True)
class StyleInfo:
    """一个可供前端选择的风格。"""

    style_id: str
    name: str
    artist: str
    description: str
    preview_url: str
    image_path: Path


STYLE_CANDIDATES: tuple[dict[str, str], ...] = (
    {
        "style_id": "vangogh",
        "name": "梵高星空",
        "artist": "Vincent van Gogh",
        "description": "后印象派旋涡笔触和高饱和色彩风格",
        "query": "vincent-van-gogh_the-starry-night-1889",
        "fallback_genre": "Post_Impressionism",
    },
    {
        "style_id": "picasso",
        "name": "毕加索立体主义",
        "artist": "Pablo Picasso",
        "description": "几何分解、平面化与抽象结构风格",
        "query": "pablo-picasso",
        "fallback_genre": "Analytical_Cubism",
    },
    {
        "style_id": "monet",
        "name": "莫奈印象派",
        "artist": "Claude Monet",
        "description": "明亮色彩、柔和光影和印象派笔触",
        "query": "claude-monet",
        "fallback_genre": "Impressionism",
    },
    {
        "style_id": "kandinsky",
        "name": "康定斯基表现主义",
        "artist": "Wassily Kandinsky",
        "description": "强烈色块、抽象构成和表现主义张力",
        "query": "wassily-kandinsky",
        "fallback_genre": "Expressionism",
    },
    {
        "style_id": "hokusai",
        "name": "葛饰北斋浮世绘",
        "artist": "Katsushika Hokusai",
        "description": "清晰轮廓、装饰性色面和浮世绘风格",
        "query": "katsushika-hokusai_a-colored-version-of-the-big-wave",
        "fallback_genre": "Ukiyo_e",
    },
    {
        "style_id": "munch",
        "name": "蒙克表现主义",
        "artist": "Edvard Munch",
        "description": "扭曲线条、强烈情绪和表现主义色彩",
        "query": "edvard-munch_anxiety",
        "fallback_genre": "Expressionism",
    },
)


class StyleRegistry:
    """按需从 WikiArt 元数据中选择少量代表性风格图。"""

    def __init__(self, wikiart_dir: Path = WIKIART_DIR) -> None:
        self.wikiart_dir = wikiart_dir
        self._styles: dict[str, StyleInfo] | None = None

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
        ensure_runtime_dirs()
        csv_path = self.wikiart_dir / "classes.csv"
        rows = list(self._iter_csv_rows(csv_path)) if csv_path.exists() else []
        styles: dict[str, StyleInfo] = {}
        for candidate in STYLE_CANDIDATES:
            image_path = self._find_image(rows, candidate)
            if image_path is None:
                continue
            preview_url = self._ensure_preview(candidate["style_id"], image_path)
            styles[candidate["style_id"]] = StyleInfo(
                style_id=candidate["style_id"],
                name=candidate["name"],
                artist=candidate["artist"],
                description=candidate["description"],
                preview_url=preview_url,
                image_path=image_path,
            )
        return styles

    def _iter_csv_rows(self, csv_path: Path) -> Iterable[dict[str, str]]:
        with csv_path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            yield from reader

    def _find_image(
        self, rows: list[dict[str, str]], candidate: dict[str, str]
    ) -> Path | None:
        query = candidate["query"].lower()
        fallback_genre = candidate["fallback_genre"]
        matches = [row for row in rows if query in row.get("filename", "").lower()]
        if not matches:
            artist_name = candidate["artist"].lower()
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
        preview_path = STYLE_STATIC_DIR / f"{style_id}.jpg"
        if preview_path.exists():
            return f"/static/styles/{style_id}.jpg"
        try:
            with Image.open(source_path) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((settings.preview_size, settings.preview_size))
                image.save(preview_path, "JPEG", quality=88, optimize=True)
        except Exception:
            shutil.copyfile(source_path, preview_path)
        return f"/static/styles/{style_id}.jpg"


style_registry = StyleRegistry()
