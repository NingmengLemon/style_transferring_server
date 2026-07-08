"""日志配置：支持普通文本与 JSON 结构化两种格式，可选写文件。"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings, settings

LOGGER_NAME = "style_transferring_server"


class JsonLogFormatter(logging.Formatter):
    """将日志记录序列化为单行 JSON，便于采集与检索。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 附带通过 extra 传入的结构化字段。
        for key, value in record.__dict__.items():
            if key in _RESERVED_ATTRS or key.startswith("_"):
                continue
            payload.setdefault(key, value)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_RESERVED_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys()) | {
    "message",
    "asctime",
    "taskName",
}


def get_logger() -> logging.Logger:
    """返回项目统一 logger。"""

    return logging.getLogger(LOGGER_NAME)


def configure_logging(target: Settings = settings) -> logging.Logger:
    """按配置初始化日志处理器。可重复调用（幂等）。"""

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(target.log_level)
    logger.handlers.clear()
    logger.propagate = False

    if target.log_json:
        formatter: logging.Formatter = JsonLogFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if target.log_file is not None:
        log_path = Path(target.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
