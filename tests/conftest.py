"""测试夹具：构造轻量 TestClient，避免加载真实 VGG 与 30GB 数据集。"""

from __future__ import annotations

import io
import os

import pytest

# 测试默认关闭预训练权重下载与启动预热，保证离线可跑、启动快。
os.environ.setdefault("STYLE_SERVER_PRETRAINED_VGG", "0")
os.environ.setdefault("STYLE_SERVER_WARMUP", "0")

from PIL import Image  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from style_transferring_server.app import app  # noqa: E402
from style_transferring_server.styles import StyleInfo, style_registry  # noqa: E402
from style_transferring_server import transfer as transfer_module  # noqa: E402


def _make_image_bytes(fmt: str = "JPEG", size: tuple[int, int] = (64, 64)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (120, 130, 140)).save(buffer, fmt)
    return buffer.getvalue()


@pytest.fixture
def jpeg_bytes() -> bytes:
    return _make_image_bytes("JPEG")


@pytest.fixture
def png_bytes() -> bytes:
    return _make_image_bytes("PNG")


@pytest.fixture(autouse=True)
def fake_style(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """注入一个虚拟风格，避免依赖真实 WikiArt 数据集。"""

    style_path = tmp_path / "fake_style.jpg"
    Image.new("RGB", (64, 64), (10, 20, 30)).save(style_path, "JPEG")
    fake = StyleInfo(
        style_id="vangogh",
        name="梵高星空",
        artist="Vincent van Gogh",
        description="test",
        preview_url="/static/styles/vangogh.jpg",
        image_path=style_path,
    )
    monkeypatch.setattr(style_registry, "_styles", {"vangogh": fake}, raising=False)
    yield


@pytest.fixture(autouse=True)
def fast_transfer(monkeypatch: pytest.MonkeyPatch):
    """将真实推理替换为轻量桩，保证测试快速且不占显存。"""

    service = transfer_module.style_transfer_service

    def fake_run_optimization(content, style, params):
        # 直接返回内容张量，跳过 LBFGS 迭代。
        return content.detach()

    monkeypatch.setattr(service, "_run_optimization", fake_run_optimization)
    monkeypatch.setattr(
        service,
        "load_model",
        lambda: setattr(service, "model", service.model or _StubModule()),
    )
    yield


class _StubModule:
    """占位模型，让 model_loaded 为真但不参与桩化后的推理。"""

    def __iter__(self):
        return iter(())


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
