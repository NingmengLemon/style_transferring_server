"""命令行启动入口。"""

from __future__ import annotations

import uvicorn

from .config import settings


def main() -> None:
    """通过项目脚本启动 Uvicorn 服务。"""

    uvicorn.run(
        "style_transferring_server.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
