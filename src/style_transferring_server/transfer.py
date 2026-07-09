"""基于 PyTorch / VGG 的快速神经风格迁移服务。"""

from __future__ import annotations

import asyncio
import io
import time
import uuid
from pathlib import Path
from typing import Any, Final, cast

import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError
from torchvision.models import VGG19_Weights, vgg19
from torchvision.transforms import functional as TF

from .config import settings
from .constants import (
    DEFAULT_QUALITY,
    RESULT_FILENAME_PREFIX,
    RESULT_IMAGE_FORMAT,
    RGB_CHANNELS,
    SMOOTHNESS_FILTER_THRESHOLD,
    SMOOTHNESS_RADIUS_SCALE,
    SUPPORTED_IMAGE_FORMATS,
    SUPPORTED_UPLOAD_EXTENSIONS,
    WARMUP_IMAGE_SIZE,
    WARMUP_RGB_VALUE,
    ApiPath,
    ErrorCode,
    HttpStatus,
    ImageConstraint,
    StaticSubdir,
    TransferDefault,
)
from .logging_config import get_logger
from .responses import ApiError
from .schemas import Quality, TransferParameters, TransferResult
from .styles import StyleInfo

logger = get_logger()


# 各质量档位的长边像素、外层步数与每步 LBFGS 内迭代次数。
#
# 关键：真正决定风格转移充分度的是「closure 评估总次数 ≈ STEPS × LBFGS_MAX_ITER」
# 以及 LBFGS 的 strong_wolfe line search（拟牛顿法充分收敛），而非 style_weight。
# 早期实现用 max_iter=1 且无 line search，退化为低效一阶更新，导致「强度拉满也不够」。
#
# 经 RTX4060 Laptop 实测校准（含冷启动后稳态，空载 GPU）：
#   fast≈1.5s、normal≈3.5s、hd≈8s。fast 满足实时预算；normal/hd 为高质量档。
MAX_SIDE_BY_QUALITY: Final[dict[Quality, int]] = {
    "fast": 384,
    "normal": 448,
    "hd": 576,
}
STEPS_BY_QUALITY: Final[dict[Quality, int]] = {"fast": 6, "normal": 8, "hd": 10}
LBFGS_MAX_ITER_BY_QUALITY: Final[dict[Quality, int]] = {
    "fast": 8,
    "normal": 10,
    "hd": 12,
}
MILLISECONDS_PER_SECOND: Final[int] = 1000


class StyleTransferService:
    """封装模型加载、输入校验和 VGG 神经风格迁移。"""

    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model: nn.Sequential | None = None
        self.model_error: str | None = None
        self._lock = asyncio.Lock()
        self._mean = torch.tensor([0.485, 0.456, 0.406], device=self.device).view(
            1, RGB_CHANNELS, 1, 1
        )
        self._std = torch.tensor([0.229, 0.224, 0.225], device=self.device).view(
            1, RGB_CHANNELS, 1, 1
        )
        self._content_layer = 21
        self._style_layers = (0, 5, 10, 19, 28)
        self._capture_layers = set(self._style_layers + (self._content_layer,))
        self._max_capture_layer = max(self._capture_layers)

    @property
    def model_loaded(self) -> bool:
        return self.model is not None

    def load_model(self) -> None:
        """加载 VGG19 特征提取网络。"""

        if self.model is not None:
            return
        try:
            weights = VGG19_Weights.IMAGENET1K_V1 if settings.pretrained_vgg else None
            features = vgg19(weights=weights).features.eval().to(self.device)
            for parameter in features.parameters():
                parameter.requires_grad_(False)
            # torchvision 的 features 运行期就是 nn.Sequential，但其类型标注
            # 被声明为宽泛的 Module，这里显式收窄以便静态检查与迭代。
            self.model = cast(nn.Sequential, features)
            self.model_error = None
            logger.info(
                "VGG19 model loaded (device=%s, pretrained=%s)",
                self.device,
                settings.pretrained_vgg,
            )
        except Exception as exc:
            self.model_error = str(exc)
            self.model = None
            logger.exception("model loading failed")
            raise ApiError(
                ErrorCode.MODEL_LOADING_FAILED,
                "model loading failed",
                HttpStatus.INTERNAL_SERVER_ERROR,
            ) from exc

    def warmup(self) -> None:
        """用一张小图跑一次完整推理，触发 cudnn autotune 与显存分配。

        任何异常都被吞掉：预热失败不应阻止服务启动，真正的错误会在
        首个真实请求时以约定的错误码暴露。
        """

        try:
            self.load_model()
            dummy = Image.new(
                "RGB",
                (WARMUP_IMAGE_SIZE, WARMUP_IMAGE_SIZE),
                (WARMUP_RGB_VALUE, WARMUP_RGB_VALUE, WARMUP_RGB_VALUE),
            )
            content = self._image_to_tensor(dummy, MAX_SIDE_BY_QUALITY[DEFAULT_QUALITY])
            style = self._image_to_tensor(
                dummy,
                MAX_SIDE_BY_QUALITY[DEFAULT_QUALITY],
                target_size=(content.shape[2], content.shape[3]),
            )
            params = TransferParameters.from_form_values(quality=DEFAULT_QUALITY)
            self._run_optimization(content, style, params)
            if torch.cuda.is_available():
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
            logger.info("model warmup completed")
        except Exception:
            logger.warning("model warmup failed; continuing", exc_info=True)

    def validate_parameters(
        self,
        style_strength: int = TransferDefault.STYLE_STRENGTH,
        content_weight: int = TransferDefault.CONTENT_WEIGHT,
        smoothness: int = TransferDefault.SMOOTHNESS,
        quality: str = DEFAULT_QUALITY,
    ) -> TransferParameters:
        """校验并标准化表单参数；保留为兼容测试或外部调用的薄封装。"""

        return TransferParameters.from_form_values(
            style_strength=style_strength,
            content_weight=content_weight,
            smoothness=smoothness,
            quality=quality,
        )

    async def transfer(
        self,
        image_bytes: bytes,
        filename: str,
        style: StyleInfo,
        params: TransferParameters,
    ) -> TransferResult:
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
    ) -> TransferResult:
        start = time.perf_counter()
        self.load_model()
        assert self.model is not None

        logger.info(
            "style-transfer start: style=%s quality=%s params=(%d,%d,%d) size=%dB",
            style.style_id,
            params.quality,
            params.style_strength,
            params.content_weight,
            params.smoothness,
            len(image_bytes),
        )

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
            raise ApiError(
                ErrorCode.CUDA_OUT_OF_MEMORY,
                "CUDA out of memory",
                HttpStatus.SERVICE_UNAVAILABLE,
            ) from exc
        except ApiError:
            raise
        except RuntimeError as exc:
            raise ApiError(
                ErrorCode.STYLE_TRANSFER_FAILED,
                "style transfer failed",
                HttpStatus.INTERNAL_SERVER_ERROR,
            ) from exc

        output_image = self._tensor_to_image(output_tensor)
        if params.smoothness > 0:
            radius = params.smoothness / 100 * SMOOTHNESS_RADIUS_SCALE
            output_image = output_image.filter(
                ImageFilter.SMOOTH_MORE
                if radius > SMOOTHNESS_FILTER_THRESHOLD
                else ImageFilter.SMOOTH
            )

        result_name = f"{RESULT_FILENAME_PREFIX}{uuid.uuid4().hex}.png"
        result_path = settings.results_dir / result_name
        output_image.save(result_path, RESULT_IMAGE_FORMAT, optimize=True)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        elapsed_ms = int((time.perf_counter() - start) * MILLISECONDS_PER_SECOND)
        logger.info(
            "style-transfer done: style=%s quality=%s time_ms=%d result=%s",
            style.style_id,
            params.quality,
            elapsed_ms,
            result_name,
        )
        return TransferResult(
            result_url=f"{ApiPath.STATIC_PREFIX}/{StaticSubdir.RESULTS}/{result_name}",
            time_ms=elapsed_ms,
            parameters=params,
        )

    def _read_upload(self, image_bytes: bytes, filename: str) -> Image.Image:
        if not image_bytes:
            raise ApiError(
                ErrorCode.IMAGE_REQUIRED,
                "image is required",
                HttpStatus.BAD_REQUEST,
            )
        if (
            len(image_bytes)
            > settings.max_upload_mb * ImageConstraint.BYTES_PER_MEBIBYTE
        ):
            raise ApiError(
                ErrorCode.IMAGE_TOO_LARGE,
                "image exceeds size limit",
                HttpStatus.PAYLOAD_TOO_LARGE,
            )
        suffix = Path(filename or "").suffix.lower().lstrip(".")
        if suffix not in SUPPORTED_UPLOAD_EXTENSIONS:
            raise ApiError(
                ErrorCode.IMAGE_UNSUPPORTED_TYPE,
                "only jpg/png/jpeg supported",
                HttpStatus.UNSUPPORTED_MEDIA_TYPE,
            )
        try:
            image = Image.open(io.BytesIO(image_bytes))
            # 校验真实图像内容与声明格式一致，防止伪造扩展名。
            image.verify()
        except (UnidentifiedImageError, SyntaxError, OSError, ValueError) as exc:
            raise ApiError(
                ErrorCode.IMAGE_UNREADABLE,
                "image cannot be read",
                HttpStatus.BAD_REQUEST,
            ) from exc
        actual_format = (image.format or "").lower()
        if actual_format not in SUPPORTED_IMAGE_FORMATS:
            raise ApiError(
                ErrorCode.IMAGE_UNSUPPORTED_TYPE,
                "only jpg/png/jpeg supported",
                HttpStatus.UNSUPPORTED_MEDIA_TYPE,
            )
        # verify() 之后需要重新打开才能继续读取像素。
        try:
            opened_image = Image.open(io.BytesIO(image_bytes))
            converted_image = ImageOps.exif_transpose(opened_image).convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ApiError(
                ErrorCode.IMAGE_UNREADABLE,
                "image cannot be read",
                HttpStatus.BAD_REQUEST,
            ) from exc
        if (
            converted_image.width < ImageConstraint.MIN_SIDE
            or converted_image.height < ImageConstraint.MIN_SIDE
            or converted_image.width > ImageConstraint.MAX_SIDE
            or converted_image.height > ImageConstraint.MAX_SIDE
        ):
            raise ApiError(
                ErrorCode.IMAGE_INVALID_SIZE,
                "invalid image size",
                HttpStatus.BAD_REQUEST,
            )
        return converted_image

    def _read_style(self, path: Path) -> Image.Image:
        try:
            with Image.open(path) as image:
                return ImageOps.exif_transpose(image).convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            # 风格预览图损坏或缺失属于服务端资源问题。
            raise ApiError(
                ErrorCode.STYLE_TRANSFER_FAILED,
                "style transfer failed",
                HttpStatus.INTERNAL_SERVER_ERROR,
            ) from exc

    def _image_to_tensor(
        self,
        image: Image.Image,
        max_side: int,
        target_size: tuple[int, int] | None = None,
    ) -> torch.Tensor:
        if target_size is None:
            scale = min(max_side / max(image.width, image.height), 1.0)
            size = (
                max(ImageConstraint.MIN_SIDE, int(image.height * scale)),
                max(ImageConstraint.MIN_SIDE, int(image.width * scale)),
            )
        else:
            size = target_size
        image = image.resize((size[1], size[0]), Image.Resampling.LANCZOS)
        return cast(torch.Tensor, TF.to_tensor(image).unsqueeze(0).to(self.device))

    def _tensor_to_image(self, tensor: torch.Tensor) -> Image.Image:
        tensor = tensor.detach().clamp(0, 1).cpu().squeeze(0)
        return cast(Image.Image, TF.to_pil_image(tensor))

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
            if index >= self._max_capture_layer:
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
        # strong_wolfe line search + 较大 max_iter：让拟牛顿法在每个外层 step
        # 内充分收敛。实测同等耗时下 style_loss 比 max_iter=1 低数倍。
        optimizer = torch.optim.LBFGS(
            [generated],
            max_iter=LBFGS_MAX_ITER_BY_QUALITY[params.quality],
            history_size=20,
            line_search_fn="strong_wolfe",
        )
        style_weight, content_weight, total_variation_weight = self._loss_weights(
            params
        )
        steps = STEPS_BY_QUALITY[params.quality]
        deadline = time.perf_counter() + settings.timeout_s

        for _ in range(steps):
            if time.perf_counter() > deadline:
                raise ApiError(
                    ErrorCode.INFERENCE_TIMEOUT,
                    "inference timeout",
                    HttpStatus.GATEWAY_TIMEOUT,
                )

            # 注意：不要在 closure 内 clamp 参数。strong_wolfe line search 会
            # 多次评估 closure 并假设目标函数在参数上连续一致，clamp 会篡改
            # 参数导致 line search 的函数值/梯度不匹配。改为每个外层 step 结束后
            # 再 clamp 到合法像素区间。
            def closure() -> torch.Tensor:
                optimizer.zero_grad(set_to_none=True)
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
                cast(Any, loss).backward()
                return loss

            cast(Any, optimizer).step(closure)
            with torch.no_grad():
                generated.clamp_(0, 1)

        generated.data.clamp_(0, 1)
        return generated.detach()

    def _loss_weights(self, params: TransferParameters) -> tuple[float, float, float]:
        """把用户参数映射为损失权重。

        关键设计（基于实测）：视觉风格强度主要由 style:content 权重比决定，
        而单纯提高 style_weight 几乎无效。因此 ``style_strength`` 主要通过
        **指数级降低 content_weight** 来放大风格——比值才是有效杠杆。

        映射区间经像素偏离度扫描校准（style_weight=3e6、fast 档）：
        content_weight 的有效动态范围约在 2000（弱风格）到 5（强风格）之间，
        更低即饱和。因此把 style_strength 0→100 映射到 content_weight 2000→5：

        - strength=0   → content_weight≈2000（强内容约束，接近原图）
        - strength=50  → content_weight≈100
        - strength=100 → content_weight≈5（风格充分覆盖）

        早期实现映射到 50→0.5，整段都落在饱和区，导致「强度调了也看不出变化」。
        ``content_weight`` 参数（0-100）在此基础上做 0.5x~1.5x 线性微调，
        保留用户对内容保留度的独立控制。
        """

        strength = min(max(params.style_strength, 0), 100)
        content = min(max(params.content_weight, 0), 100)

        style_weight = 3_000_000.0
        # 2000·10^(-2.6·strength/100)：strength 0→100 时 2000→5，跨越有效动态范围。
        base_content = 2000.0 * (10.0 ** (-2.6 * strength / 100.0))
        # content_weight 参数（0-100，默认 50）线性缩放 0.5x~1.5x。
        content_weight = base_content * (0.5 + content / 100.0)
        total_variation_weight = 0.00002 * params.smoothness
        return style_weight, content_weight, total_variation_weight

    def _total_variation(self, tensor: torch.Tensor) -> torch.Tensor:
        horizontal = torch.mean(torch.abs(tensor[:, :, :, :-1] - tensor[:, :, :, 1:]))
        vertical = torch.mean(torch.abs(tensor[:, :, :-1, :] - tensor[:, :, 1:, :]))
        return horizontal + vertical


style_transfer_service = StyleTransferService()
