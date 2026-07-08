"""项目运行配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
WIKIART_DIR = DATA_DIR / "dataset" / "wikiart"
OUTPUT_DIR = DATA_DIR / "outputs"
STATIC_DIR = OUTPUT_DIR / "static"
RESULTS_DIR = STATIC_DIR / "results"
STYLE_STATIC_DIR = STATIC_DIR / "styles"
UPLOAD_DIR = OUTPUT_DIR / "uploads"


@dataclass(frozen=True)
class Settings:
    """服务端可调参数。"""

    host: str = os.getenv("STYLE_SERVER_HOST", "0.0.0.0")
    port: int = int(os.getenv("STYLE_SERVER_PORT", "8000"))
    max_upload_mb: int = int(os.getenv("STYLE_SERVER_MAX_UPLOAD_MB", "10"))
    inference_timeout_s: float = float(os.getenv("STYLE_SERVER_TIMEOUT_S", "30"))
    preview_size: int = int(os.getenv("STYLE_SERVER_PREVIEW_SIZE", "512"))
    use_pretrained_vgg: bool = os.getenv("STYLE_SERVER_PRETRAINED_VGG", "1") != "0"


settings = Settings()


def ensure_runtime_dirs() -> None:
    """创建运行时输出目录。"""

    for path in (OUTPUT_DIR, STATIC_DIR, RESULTS_DIR, STYLE_STATIC_DIR, UPLOAD_DIR):
        path.mkdir(parents=True, exist_ok=True)
