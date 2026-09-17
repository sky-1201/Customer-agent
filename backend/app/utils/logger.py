"""日志工具：结构化 JSON 日志 + trace_id 串联（对标大厂规范）

设计要点：
1. 结构化 JSON：方便接入日志平台（ELK/Loki）检索
2. trace_id：一次请求/对话一个唯一 ID，贯穿该请求所有日志
3. 级别规范：INFO 关键事件 / WARNING 可恢复异常 / ERROR 不可恢复异常
4. 业务字段：通过 extra 传入，自动并入 JSON
"""
import contextvars
import json
import logging
import sys
from datetime import datetime

# trace_id：一次请求/对话的唯一标识（在请求入口设置，如 chat 接口）
_trace_id_var = contextvars.ContextVar("trace_id", default="-")


def set_trace_id(trace_id: str) -> None:
    """在请求入口设置 trace_id（如 chat 接口）"""
    _trace_id_var.set(trace_id)


def get_trace_id() -> str:
    return _trace_id_var.get()


class JsonFormatter(logging.Formatter):
    """结构化 JSON 日志格式

    固定字段：ts / level / logger / trace_id / msg
    业务字段：通过 logger.info(msg, extra={...}) 传入，自动并入
    异常字段：exc（异常堆栈）
    """

    # 标准 LogRecord 字段，其余视为业务 extra 字段
    _STD_FIELDS = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "process", "processName", "taskName", "message", "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": get_trace_id(),
            "msg": record.getMessage(),
        }
        # 业务 extra 字段并入
        for key, value in record.__dict__.items():
            if key not in self._STD_FIELDS and not key.startswith("_"):
                data[key] = value
        # 异常堆栈
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    """初始化日志（main.py 启动时调用一次）"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]  # 清空默认 handler，避免重复输出
    root.setLevel(level)
    # 降噪第三方库（httpx/openai 的请求日志太吵）
    for noisy in ("httpx", "httpcore", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def attach_file_logging(log_dir) -> None:
    """追加文件日志（logs/app.log，滚动切割，本地排障用）。

    必须在 FastAPI lifespan 里调用，不能在模块导入期：
    uvicorn 启动时会用它自己的 log config 重刷 logger handler，
    导入期 attach 的 handler 会被刷掉。
    """
    from logging.handlers import RotatingFileHandler

    log_dir.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(
        log_dir / "app.log", maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(JsonFormatter())
    # root：应用日志（经 propagate 汇聚）；uvicorn.*：ASGI 异常/访问日志
    # （uvicorn 的 logger propagate=False 且有独立 handler，需单独 attach）
    for name in ("", "uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        if not any(isinstance(h, RotatingFileHandler) for h in lg.handlers):
            lg.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    """获取带模块名的 logger（推荐 logger = get_logger(__name__)）"""
    return logging.getLogger(name)
