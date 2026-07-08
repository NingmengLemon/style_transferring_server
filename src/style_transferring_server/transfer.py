"""基于 PyTorch / VGG 的快速神经风格迁移服务。"""

from __future__ import annotations

import asyncio
import io
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError
import torch
import torch.nn.functional as F
from torchvision.models import VGG19_Weights, vgg19
from torchvision.transforms import functional as TF

from .config import RESULTS_DIR, settings
from .responses import ApiError
from .styles import StyleInfo


VALID_QUALITIES = {"fast", "normal", "hd"}
VALID_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_SIDE_BY_QUALITY = {"fast": 384, "normal": 512, "hd": 768}
ITERATIONS_BY_QUALITY = {"fast": 18, "normal": 32, "hd": 48}


@dataclass(frozen=True)
class TransferParameters:
    """风格迁移可调参数。"""

    style_strength: int = 70
    content_weight: int = 50
    smoothness: int = 30
    quality: str = "fast"


class StyleTransferService:
    """封装模型加载、输入校验和 VGG 神经风格迁移。"""

    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model: torch.nn.Module | None = None
        self.model_error: str | None = None
        self._lock = asyncio.Lock()
        self._mean = torch.tensor([0.485, 0.456, 0.406], device=self.device).view(
            1, 3, 1, 1
        )
        self._std = torch.tensor([0.229, 0.224, 0.225], device=self.device).view(
            1, 3, 1, 1
        )
        self._content_layer = 21
        self._style_layers = (0, 5, 10, 19, 28)
        self._capture_layers = set(self._style_layers + (self._content_layer,))

    @property
    def model_loaded(self) -> bool:
        return self.model is not None

    def load_model(self) -> None:
        """加载 VGG19 特征提取网络。"""

        if self.model is not None:
            return
        try:
            weights = (
                VGG19_Weights.IMAGENET1K_V1 if settings.use_pretrained_vgg else None
            )
            model = vgg19(weights=weights).features.eval().to(self.device)
            for parameter in model.parameters():
                parameter.requires_grad_(False)
            self.model = model
            self.model_error = None
        except Exception as exc:
            self.model_error = str(exc)
            self.model = None
            raise ApiError(3003, "model loading failed", 500) from exc

    def validate_parameters(
        self,
        style_strength: int = 70,
        content_weight: int = 50,
        smoothness: int = 30,
        quality: str = "fast",
    ) -> TransferParameters:
        """校验并标准化表单参数。"""

        checks = {
            "style_strength": style_strength,
            "content_weight": content_weight,
            "smoothness": smoothness,
        }
        for name, value in checks.items():
            if value < 0 or value > 100:
                raise ApiError(3002, f"{name} must between 0 and 100", 400)
        if quality not in VALID_QUALITIES:
            raise ApiError(3002, "quality must be fast, normal or hd", 400)
        return TransferParameters(style_strength, content_weight, smoothness, quality)

    async def transfer(
        self,
        image_bytes: bytes,
        filename: str,
        style: StyleInfo,
        params: TransferParameters,
    ) -> dict[str, object]:
        """异步串行执行一次风格迁移，避免显存并发峰值。"""

        async with self._lock:
            return await asyncio.to_thread(
                self._transfer_sync, image_bytes, filename, style, params
            )

    def _transfer_sync(
        self,
        image_bytes: bytes,
        filename: str,
        style: StyleInfo,
        params: TransferParameters,
    ) -> dict[str, object]:
        start = time.perf_counter()
        self.load_model()
        assert self.model is not None

        content_image = self._read_upload(image_bytes, filename)
        style_image = self._read_style(style.image_path)
        max_side = MAX_SIDE_BY_QUALITY[params.quality]
        content_tensor = self._image_to_tensor(content_image, max_side)
        _, _, height, width = content_tensor.shape
        style_tensor = self._image_to_tensor(
            style_image, max_side, target_size=(height, width)
        )

        try:
            output_tensor = self._run_optimization(content_tensor, style_tensor, params)
        except torch.cuda.OutOfMemoryError as exc:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            raise ApiError(3005, "CUDA out of memory", 503) from exc
        except RuntimeError as exc:
            raise ApiError(3004, "style transfer failed", 500) from exc

        output_image = self._tensor_to_image(output_tensor)
        if params.smoothness > 0:
            radius = params.smoothness / 100 * 0.8
            output_image = output_image.filter(
                ImageFilter.SMOOTH_MORE if radius > 0.45 else ImageFilter.SMOOTH
            )

        result_name = f"result_{uuid.uuid4().hex}.png"
        result_path = RESULTS_DIR / result_name
        output_image.save(result_path, "PNG", optimize=True)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return {
            "result_url": f"/static/results/{result_name}",
            "time_ms": int((time.perf_counter() - start) * 1000),
            "parameters": {
                "style_strength": params.style_strength,
                "content_weight": params.content_weight,
                "smoothness": params.smoothness,
                "quality": params.quality,
            },
        }

    def _read_upload(self, image_bytes: bytes, filename: str) -> Image.Image:
        if not image_bytes:
            raise ApiError(2001, "image is required", 400)
        if len(image_bytes) > settings.max_upload_mb * 1024 * 1024:
            raise ApiError(2004, "image exceeds size limit", 413)
        suffix = Path(filename or "").suffix.lower().lstrip(".")
        if suffix not in VALID_EXTENSIONS:
            raise ApiError(2003, "only jpg/png/jpeg supported", 415)
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = ImageOps.exif_transpose(image).convert("RGB")
        except UnidentifiedImageError as exc:
            raise ApiError(2002, "image cannot be read", 400) from exc
        if (
            image.width < 16
            or image.height < 16
            or image.width > 12000
            or image.height > 12000
        ):
            raise ApiError(2005, "invalid image size", 400)
        return image

    def _read_style(self, path: Path) -> Image.Image:
        with Image.open(path) as image:
            return ImageOps.exif_transpose(image).convert("RGB")

    def _image_to_tensor(
        self,
        image: Image.Image,
        max_side: int,
        target_size: tuple[int, int] | None = None,
    ) -> torch.Tensor:
        if target_size is None:
            scale = min(max_side / max(image.width, image.height), 1.0)
            size = (
                max(16, int(image.height * scale)),
                max(16, int(image.width * scale)),
            )
        else:
            size = target_size
        image = image.resize((size[1], size[0]), Image.Resampling.LANCZOS)
        return TF.to_tensor(image).unsqueeze(0).to(self.device)

    def _tensor_to_image(self, tensor: torch.Tensor) -> Image.Image:
        tensor = tensor.detach().clamp(0, 1).cpu().squeeze(0)
        return TF.to_pil_image(tensor)

    def _normalize(self, tensor: torch.Tensor) -> torch.Tensor:
        return (tensor - self._mean) / self._std

    def _extract_features(self, tensor: torch.Tensor) -> dict[int, torch.Tensor]:
        assert self.model is not None
        features: dict[int, torch.Tensor] = {}
        x = self._normalize(tensor)
        for index, layer in enumerate(self.model):
            x = layer(x)
            if index in self._capture_layers:
                features[index] = x
            if index >= max(self._capture_layers):
                break
        return features

    def _gram_matrix(self, tensor: torch.Tensor) -> torch.Tensor:
        batch, channels, height, width = tensor.shape
        features = tensor.view(batch, channels, height * width)
        gram = torch.bmm(features, features.transpose(1, 2))
        return gram / (channels * height * width)

    def _run_optimization(
        self, content: torch.Tensor, style: torch.Tensor, params: TransferParameters
    ) -> torch.Tensor:
        with torch.no_grad():
            content_features = self._extract_features(content)
            style_features = self._extract_features(style)
            style_grams = {
                layer: self._gram_matrix(style_features[layer])
                for layer in self._style_layers
            }

        generated = content.clone().requires_grad_(True)
        optimizer = torch.optim.LBFGS(
            [generated], max_iter=1, history_size=8, line_search_fn=None
        )
        style_weight = 1_000_000.0 * max(params.style_strength, 1) / 70
        content_weight = 10.0 * max(params.content_weight, 1) / 50
        total_variation_weight = 0.00002 * params.smoothness
        iterations = ITERATIONS_BY_QUALITY[params.quality]
        deadline = time.perf_counter() + settings.inference_timeout_s

        for _ in range(iterations):
            if time.perf_counter() > deadline:
                raise ApiError(3006, "inference timeout", 504)

            def closure() -> torch.Tensor:
                optimizer.zero_grad(set_to_none=True)
                generated.data.clamp_(0, 1)
                generated_features = self._extract_features(generated)
                content_loss = F.mse_loss(
                    generated_features[self._content_layer],
                    content_features[self._content_layer],
                )
                style_loss = torch.zeros((), device=self.device)
                for layer in self._style_layers:
                    style_loss = style_loss + F.mse_loss(
                        self._gram_matrix(generated_features[layer]), style_grams[layer]
                    )
                tv_loss = self._total_variation(generated)
                loss = (
                    content_weight * content_loss
                    + style_weight * style_loss
                    + total_variation_weight * tv_loss
                )
                loss.backward()
                return loss

            optimizer.step(closure)

        generated.data.clamp_(0, 1)
        return generated.detach()

    def _total_variation(self, tensor: torch.Tensor) -> torch.Tensor:
        horizontal = torch.mean(torch.abs(tensor[:, :, :, :-1] - tensor[:, :, :, 1:]))
        vertical = torch.mean(torch.abs(tensor[:, :, :-1, :] - tensor[:, :, 1:, :]))
        return horizontal + vertical


style_transfer_service = StyleTransferService()
