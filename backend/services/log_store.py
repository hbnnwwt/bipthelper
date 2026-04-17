import logging
from datetime import datetime
from collections import deque
from threading import Lock

class LogStore:
    """有界日志缓冲区，保存最近 MAX_ENTRIES 条日志"""
    MAX_ENTRIES = 500

    def __init__(self):
        self._buffer = deque(maxlen=self.MAX_ENTRIES)
        self._lock = Lock()

    def append(self, level: str, message: str):
        with self._lock:
            self._buffer.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": level,
                "message": message,
            })

    def get_all(self):
        with self._lock:
            return list(self._buffer)

    def clear(self):
        with self._lock:
            self._buffer.clear()

    def count(self):
        with self._lock:
            return len(self._buffer)


# 全局实例
log_store = LogStore()


class CrawlLogHandler(logging.Handler):
    """将日志同时写入 LogStore"""
    def emit(self, record):
        try:
            msg = self.format(record)
            log_store.append(record.levelname, msg)
        except Exception:
            pass


def setup_crawl_logging():
    """配置爬虫日志，添加 LogStore handler"""
    logger = logging.getLogger("services.crawler")
    handler = CrawlLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# 初始化时设置
setup_crawl_logging()
