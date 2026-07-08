"""命令行启动入口，基于 Typer。

配置来源优先级（高到低）：命令行参数 > 环境变量 > JSON 配置文件 > 默认值。

命令行参数通过写入 ``STYLE_SERVER_*`` 环境变量生效——应用进程在首次
构建 ``Settings`` 单例时读取它们，从而避免对已实例化的单例做脆弱的猴子补丁。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
import uvicorn

app = typer.Typer(
    add_completion=False,
    help="个性化数字艺术创作系统后端启动器。",
)


def _set_env(name: str, value: object | None) -> None:
    """将非 None 的 CLI 覆盖写入对应环境变量。"""

    if value is None:
        return
    if isinstance(value, bool):
        os.environ[name] = "1" if value else "0"
    else:
        os.environ[name] = str(value)


@app.command()
def serve(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="JSON 配置文件路径（等价于设置 STYLE_SERVER_CONFIG）。",
    ),
    host: Optional[str] = typer.Option(None, help="监听地址。"),
    port: Optional[int] = typer.Option(None, help="监听端口。"),
    log_level: Optional[str] = typer.Option(
        None,
        "--log-level",
        help="日志级别：DEBUG/INFO/WARNING/ERROR/CRITICAL。",
    ),
    log_file: Optional[Path] = typer.Option(None, help="日志输出文件路径。"),
    log_json: Optional[bool] = typer.Option(
        None, "--log-json/--no-log-json", help="是否使用 JSON 结构化日志。"
    ),
    pretrained_vgg: Optional[bool] = typer.Option(
        None,
        "--pretrained-vgg/--no-pretrained-vgg",
        help="是否加载预训练 VGG19 权重。",
    ),
    warmup: Optional[bool] = typer.Option(
        None, "--warmup/--no-warmup", help="是否在启动时预热模型。"
    ),
    reload: bool = typer.Option(False, help="开发模式自动重载。"),
) -> None:
    """启动 HTTP 服务。"""

    if config is not None:
        os.environ["STYLE_SERVER_CONFIG"] = str(config)
    _set_env("STYLE_SERVER_HOST", host)
    _set_env("STYLE_SERVER_PORT", port)
    _set_env("STYLE_SERVER_LOG_LEVEL", log_level)
    _set_env("STYLE_SERVER_LOG_FILE", log_file)
    _set_env("STYLE_SERVER_LOG_JSON", log_json)
    _set_env("STYLE_SERVER_PRETRAINED_VGG", pretrained_vgg)
    _set_env("STYLE_SERVER_WARMUP", warmup)

    # 在设置好环境变量后再构建 settings，确保 CLI 覆盖生效。
    from .config import Settings

    settings = Settings()

    uvicorn.run(
        "style_transferring_server.app:app",
        host=settings.host,
        port=settings.port,
        reload=reload,
        log_level=settings.log_level.lower(),
    )


def main() -> None:
    """项目脚本入口。"""

    app()


if __name__ == "__main__":
    main()
