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
    entries: Any = None
    # 新增的 RSS 文章列表
    new_entries: list[Any] = field(default_factory=list)
    # RSS entries file 对应的 TinyDB 实例
    tinydb: TinyDB | None = None
    # 去重缓存数据库的连接对象
    conn: Connection | None = None

    # 消息发送失败计数
    msg_error_count: int = 0
    # 消息标题
    msg_header: str = ""
    # 新增的 RSS 文章对应的解析结果
    msg_contents: list[str] = field(default_factory=list)
    # 暂存单条 RSS 文章的解析结果
    msg_buffer: str = ""

    # 当前正在解析的文章
    entry: Any = None

    # 是否继续执行后续 handler
    continue_process: bool = True

    def flush_msg_buffer(self):
        """保存解析结果并清空缓冲区，为下次解析准备"""
        if not self.msg_buffer:
            logger.warning(f"对空缓冲区进行了刷新，该条 RSS 文章未被正确解析")
            return
        self.msg_contents.append(self.msg_buffer)
        self.msg_buffer = ""

    def flush_msg_contents(self):
        """在消息发送结束后调用，清空已发送的消息内容"""
        self.msg_contents.clear()

    "messages就是msg_contents,items不知道是什么意思"
    "messages就是msg_contents,items不知道是什么意思"
