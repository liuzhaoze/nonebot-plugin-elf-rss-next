from dataclasses import dataclass, field
from sqlite3 import Connection
from typing import Any

from nonebot import logger
from tinydb import TinyDB


@dataclass
class Context:
    """用于存储 RSS 解析过程中的上下文"""

    # RSS 标题
    title: str = ""
    # RSS 文章列表
    entries: list[dict[str, Any]] = field(default_factory=list)
    # 新增的 RSS 文章列表
    new_entries: list[dict[str, Any]] = field(default_factory=list)
    # RSS entries file 对应的 TinyDB 实例
    tinydb: TinyDB | None = None
    # 去重缓存数据库的连接对象
    conn: Connection | None = None

    # 消息发送失败计数
    msg_error_count: int = 0
    # 消息标题
    msg_title: str = ""
    # 新增的 RSS 文章对应的解析结果
    msg_contents: dict[str, str] = field(default_factory=dict)
    # 暂存单条 RSS 文章的解析结果
    msg_text_buffer: str = ""
    msg_image_buffer: str = ""

    # 当前正在解析的文章
    entry: dict[str, Any] | None = None

    # 是否继续执行后续 handler
    continue_process: bool = True

    def flush_msg_buffer(self):
        """保存解析结果并清空缓冲区，为下次解析准备"""
        content = self.msg_text_buffer + self.msg_image_buffer
        entry_hash = self.entry["hash"]  # 预处理第 1 步计算得到
        if not content:
            logger.warning(f"对空缓冲区进行了刷新，该条 RSS 文章未被正确解析")
            return
        self.msg_contents[entry_hash] = content
        self.msg_text_buffer = ""
        self.msg_image_buffer = ""

    def flush_msg_contents(self):
        """在消息发送结束后调用，清空已发送的消息内容"""
        self.msg_contents.clear()
