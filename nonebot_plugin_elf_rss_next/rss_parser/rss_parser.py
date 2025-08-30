import re
from typing import Any, Awaitable, Callable

from nonebot import require
from tinydb import TinyDB

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

from ..rss import RSS
from ..utils import chunk_list
from .context import Context

TParsingHandlerFunc = Callable[[Context, RSS], Awaitable[None]]


class ParsingHandler:
    def __init__(
        self,
        func: TParsingHandlerFunc,
        pattern: str = r"(.*)",
        priority: int = 50,
        halt: bool = False,
    ):
        """
        Args:
            func (Callable[..., Any]): 处理逻辑
            pattern (str): 适用的订阅链接模式
            priority (int): 处理优先级，优先级相同时会弃用默认处理器 (即 `pattern=r"(.*)` 处理器)
            halt (bool): 是否中止后续处理 (不执行默认处理需要设置为 `halt=True` 且 `priority<50`)
        """
        self.func = func
        self.pattern = pattern
        self.priority = priority
        self.halt = halt

    def __lt__(self, other: "ParsingHandler") -> bool:
        if not isinstance(other, ParsingHandler):
            raise NotImplementedError
        return self.priority < other.priority


class ParsingHandlerManager:
    preprocess_handlers: list[ParsingHandler] = []
    process_handlers: list[ParsingHandler] = []
    postprocess_handlers: list[ParsingHandler] = []

    @classmethod
    def preprocess_handler(
        cls, pattern: str = r"(.*)", priority: int = 50, halt: bool = False
    ) -> Callable[..., Any]:
        def decorator(func: TParsingHandlerFunc) -> TParsingHandlerFunc:
            cls.preprocess_handlers.append(
                ParsingHandler(func, pattern, priority, halt)
            )
            cls.preprocess_handlers.sort()
            return func

        return decorator

    @classmethod
    def process_handler(
        cls, pattern: str = r"(.*)", priority: int = 50, halt: bool = False
    ) -> Callable[..., Any]:
        def decorator(func: TParsingHandlerFunc) -> TParsingHandlerFunc:
            cls.process_handlers.append(ParsingHandler(func, pattern, priority, halt))
            cls.process_handlers.sort()
            return func

        return decorator

    @classmethod
    def postprocess_handler(
        cls, pattern: str = r"(.*)", priority: int = 50, halt: bool = False
    ) -> Callable[..., Any]:
        def decorator(func: TParsingHandlerFunc) -> TParsingHandlerFunc:
            cls.postprocess_handlers.append(
                ParsingHandler(func, pattern, priority, halt)
            )
            cls.postprocess_handlers.sort()
            return func

        return decorator


def _filter_handlers(handlers: list[ParsingHandler], url: str) -> list[ParsingHandler]:
    # 过滤出匹配 url 的 handler
    tmp = [h for h in handlers if re.search(h.pattern, url)]
    # 删除高优先级同名 handler 对应的默认 handler
    to_remove = [
        (h.func.__name__, r"(.*)", h.priority) for h in tmp if h.pattern != r"(.*)"
    ]
    return [h for h in tmp if (h.func.__name__, h.pattern, h.priority) not in to_remove]


async def _execute_handlers(handlers: list[ParsingHandler], ctx: Context, rss: RSS):
    for h in handlers:
        await h.func(ctx, rss)
        if h.halt or not ctx.continue_process:
            break


class RSSParser:
    def __init__(self, rss: RSS):
        self.rss: RSS = rss
        self.context: Context = Context()  # 解析 RSS 过程中的上下文
        self.preprocess_handlers = _filter_handlers(
            ParsingHandlerManager.preprocess_handlers, self.rss.get_url()
        )
        self.process_handlers = _filter_handlers(
            ParsingHandlerManager.process_handlers, self.rss.get_url()
        )
        self.postprocess_handlers = _filter_handlers(
            ParsingHandlerManager.postprocess_handlers, self.rss.get_url()
        )

    async def parse(self, data: dict[str, Any]):
        title = data["feed"]["title"]
        entries = data["entries"]
        rss_entries_file = store.get_plugin_data_file(
            f"{self.rss.sanitize_name()}.json"
        )
        db = TinyDB(
            rss_entries_file,
            encoding="utf-8",
            sort_keys=True,
            indent=4,
            ensure_ascii=False,
        )

        # 初始化上下文对象
        self.context.title = title
        self.context.entries = entries
        self.context.tinydb = db
        self.context.msg_title = f"【{title}】更新了！"

        # RSS 解析预处理
        await self._preprocess()

        if not self.context.new_entries:
            # 没有新增的 RSS 文章
            # RSS 解析后处理
            await self._postprocess()
            return

        # 为避免发送消息过于频繁，每 5 条更新发送一次消息
        for chunk in chunk_list(self.context.new_entries, 5):
            for entry in chunk:
                self.context.entry = entry
                await self._process()
                self.context.flush_msg_buffer()
            await self._postprocess()
            self.context.flush_msg_contents()

    async def _preprocess(self):
        await _execute_handlers(self.preprocess_handlers, self.context, self.rss)

    async def _process(self):
        await _execute_handlers(self.process_handlers, self.context, self.rss)

    async def _postprocess(self):
        await _execute_handlers(self.postprocess_handlers, self.context, self.rss)
