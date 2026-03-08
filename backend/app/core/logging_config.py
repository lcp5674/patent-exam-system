"""结构化日志配置"""
import logging
import sys
from pathlib import Path
from app.config import settings


def setup_logging():
    log_dir = Path(settings.app.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    level = getattr(logging, settings.app.LOG_LEVEL.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # File handler
    fh = logging.FileHandler(str(log_dir / "app.log"), encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Error file handler
    eh = logging.FileHandler(str(log_dir / "error.log"), encoding="utf-8")
    eh.setLevel(logging.ERROR)
    eh.setFormatter(fmt)
    root.addHandler(eh)

    return root

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
