"""针对前端 API 契约的回归测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["message"] == "success"
    assert body["data"]["status"] == "running"
    assert set(body["data"].keys()) == {"status", "model_loaded", "device"}


def test_styles_shape(client: TestClient) -> None:
    resp = client.get("/api/styles")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    styles = body["data"]["styles"]
    assert isinstance(styles, list) and styles
    first = styles[0]
    assert set(first.keys()) == {
        "style_id",
        "name",
        "artist",
        "description",
        "preview_url",
    }
    assert first["preview_url"].startswith("/static/styles/")


def test_style_transfer_success(client: TestClient, jpeg_bytes: bytes) -> None:
    resp = client.post(
        "/api/style-transfer",
        files={"image": ("photo.jpg", jpeg_bytes, "image/jpeg")},
        data={
            "style_id": "vangogh",
            "style_strength": "80",
            "content_weight": "50",
            "smoothness": "30",
            "quality": "fast",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["result_url"].startswith("/static/results/")
    assert isinstance(data["time_ms"], int)
    assert data["parameters"] == {
        "style_strength": 80,
        "content_weight": 50,
        "smoothness": 30,
        "quality": "fast",
    }


def test_style_transfer_png_ok(client: TestClient, png_bytes: bytes) -> None:
    resp = client.post(
        "/api/style-transfer",
        files={"image": ("photo.png", png_bytes, "image/png")},
        data={"style_id": "vangogh"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


def test_style_not_found(client: TestClient, jpeg_bytes: bytes) -> None:
    resp = client.post(
        "/api/style-transfer",
        files={"image": ("photo.jpg", jpeg_bytes, "image/jpeg")},
        data={"style_id": "does-not-exist"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 3001


def test_parameter_out_of_range(client: TestClient, jpeg_bytes: bytes) -> None:
    resp = client.post(
        "/api/style-transfer",
        files={"image": ("photo.jpg", jpeg_bytes, "image/jpeg")},
        data={"style_id": "vangogh", "style_strength": "150"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 3002


def test_invalid_quality(client: TestClient, jpeg_bytes: bytes) -> None:
    resp = client.post(
        "/api/style-transfer",
        files={"image": ("photo.jpg", jpeg_bytes, "image/jpeg")},
        data={"style_id": "vangogh", "quality": "ultra"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 3002


def test_unsupported_extension(client: TestClient, jpeg_bytes: bytes) -> None:
    resp = client.post(
        "/api/style-transfer",
        files={"image": ("photo.gif", jpeg_bytes, "image/gif")},
        data={"style_id": "vangogh"},
    )
    assert resp.status_code == 415
    assert resp.json()["code"] == 2003


def test_corrupted_image(client: TestClient) -> None:
    resp = client.post(
        "/api/style-transfer",
        files={"image": ("photo.jpg", b"not an image", "image/jpeg")},
        data={"style_id": "vangogh"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 2002


def test_missing_image_field(client: TestClient) -> None:
    resp = client.post(
        "/api/style-transfer",
        data={"style_id": "vangogh"},
    )
    # 缺少必填 image 字段，走表单校验统一映射为 1000。
    assert resp.status_code == 400
    assert resp.json()["code"] == 1000
