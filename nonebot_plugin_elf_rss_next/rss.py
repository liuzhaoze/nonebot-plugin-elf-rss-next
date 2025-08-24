import re
from dataclasses import dataclass, field
from typing import Any, Optional

import aiohttp
import feedparser
from nonebot import get_bot, logger, require
from nonebot.adapters.onebot.v11 import Bot
from pydantic import HttpUrl
from tinydb import Query, TinyDB
from yarl import URL

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

from .globals import global_config, plugin_config
from .utils import (
    extract_entry_fields,
    extract_valid_group_id,
    extract_valid_user_id,
    get_entry_hash,
    get_proxy,
    send_msg_to_superusers,
)

DB_FILE = store.get_plugin_data_file("rss_database.json")
HEADERS = {
    "Accept": "application/xhtml+xml,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "max-age=0",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Connection": "keep-alive",
    "Content-Type": "application/xml; charset=utf-8",
}


@dataclass
class RSS:
    # 订阅名
    name: str = ""
    # 订阅地址
    url: URL = URL("")
    # 订阅用户
    user_id: set[int] = field(default_factory=set)
    # 订阅群组
    group_id: set[int] = field(default_factory=set)
    # 是否使用代理
    use_proxy: bool = False
    # 更新频率 (分钟/次)
    frequency: str = "5"
    # 是否启用翻译
    translation: bool = False
    # 仅标题
    only_title: bool = False
    # 仅图片
    only_pic: bool = False
    # 仅含有图片
    only_has_pic: bool = False
    # 是否下载图片
    download_pic: bool = False
    # Cookies
    cookie: str = ""
    # 是否下载种子
    download_torrent: bool = False
    # 过滤关键字，支持正则
    download_torrent_keyword: str = ""
    # 黑名单关键词
    black_list_keyword: str = ""
    # 是否上传到群
    upload_to_group: bool = True
    # 去重模式
    duplicate_filter_mode: list[str] = field(default_factory=list)
    # 图片数量限制，防止消息太长刷屏
    max_image_number: int = 0
    # 正文待移除内容，支持正则
    content_to_remove: Optional[str] = None
    # HTTP ETag
    etag: Optional[str] = None
    # 上次更新时间
    last_modified: Optional[str] = None
    # 连续抓取失败的次数，超过 100 就停止更新
    error_count: int = 0
    # 停止更新
    stop: bool = False
    # 是否启用 PikPak 离线下载
    pikpak_offline: bool = False
    # PikPak 离线下载路径匹配正则表达式，用于自动归档文件，例如: r"(?:\[.*?\][\s\S])([\s\S]*)[\s\S]-"
    pikpak_path_key: str = ""
    # 当一次更新多条消息时，是否尝试发送合并消息
    send_merged_msg: bool = False

    def __post_init__(self):
        self._log_prefix = f"[RSS: {self.name}]"

    @staticmethod
    def load_rss_data() -> list["RSS"]:
        """加载全部RSS数据"""

        if not DB_FILE.exists():
            return []

        with TinyDB(
            DB_FILE, encoding="utf-8", sort_keys=True, indent=4, ensure_ascii=False
        ) as db:
            rss_list = [RSS(**item) for item in db.all()]
            return rss_list

    def upsert(self, old_name: Optional[str] = None):
        """
        向数据库中插入或更新RSS订阅信息

        Args:
            old_name (Optional[str]): 在修改订阅名称时使用 (因为修改订阅名称后，无法通过内存中的新名称找到数据库中原来的记录)
        """
        with TinyDB(
            DB_FILE, encoding="utf-8", sort_keys=True, indent=4, ensure_ascii=False
        ) as db:
            if old_name:
                db.update(self.__dict__, Query().name == old_name)
            else:
                db.upsert(self.__dict__, Query().name == self.name)

    def sanitize_name(self) -> str:
        """去除 RSS 订阅名中无法作为文件名的非法字符"""
        name = re.sub(r"[<>:\"/\\|?*]", "_", self.name)
        if name == "rss":
            name = "rss_default"
        return name

    def get_url(self, rsshub_url: HttpUrl = plugin_config.rsshub_url) -> str:
        if self.url.scheme in {"http", "https"}:
            # url 是完整的订阅链接
            return str(self.url)
        else:
            # url 不是完整链接则代表 RSSHub 路由
            base = str(rsshub_url).rstrip("/")
            route = str(self.url).lstrip("/")
            return f"{base}/{route}"

    async def extract_valid_subscribers(self, bot: Bot):
        if self.user_id:
            self.user_id = await extract_valid_user_id(bot, self.user_id)
        if self.group_id:
            self.group_id = await extract_valid_group_id(bot, self.group_id)

    async def update(self):
        bot = get_bot()

        # 检查订阅者是否合法
        await self.extract_valid_subscribers(bot)
        if not any([self.user_id, self.group_id]):
            await self.stop_update_and_notify(bot, reason="当前没有用户或群组订阅该RSS")
            return

        # 抓取 RSS 订阅数据
        data, cached = await self.fetch()
        rss_entries_file = store.get_plugin_data_file(f"{self.sanitize_name()}.json")
        initial_fetch = not rss_entries_file.exists()

        if cached:
            logger.info(f"{self._log_prefix}没有新内容")
            return

        if not data or not data.get("feed"):
            # 抓取不到有效数据
            self.error_count += 1
            logger.warning(
                f"{self._log_prefix}抓取失败，累计失败 {self.error_count} 次"
            )
            notify_msg = (
                "请检查订阅地址" + ("、Cookie " if self.cookie else "") + "和代理设置"
            )

            if initial_fetch:
                if plugin_config.proxy and not self.use_proxy:
                    logger.info(f"{self._log_prefix}首次抓取失败，自动使用代理抓取")
                    self.use_proxy = True
                    self.upsert()
                    await self.update()
                else:
                    await self.stop_update_and_notify(
                        bot, "首次抓取失败，" + notify_msg
                    )

            if self.error_count >= 100:
                await self.stop_update_and_notify(
                    bot, "连续抓取失败超过 100 次，" + notify_msg
                )

            return

        self.error_count = 0

        if initial_fetch:
            # 首次抓取成功，保存数据但不发送消息
            entries = [extract_entry_fields(entry) for entry in data["entries"]]
            for entry in entries:
                entry["hash"] = get_entry_hash(entry)

            with TinyDB(
                rss_entries_file,
                encoding="utf-8",
                sort_keys=True,
                indent=4,
                ensure_ascii=False,
            ) as db:
                db.insert_multiple(entries)

            logger.info(f"{self._log_prefix}首次抓取成功，更新推送已就绪")
            return

        # TODO: 解析更新并发送通知

    async def fetch(self) -> tuple[dict[str, Any], bool]:
        """抓取 RSS 内容"""
        url = URL(self.get_url())
        localhost = {"127.0.0.1", "localhost"}
        proxy = get_proxy(self.use_proxy) if url.host not in localhost else None
        cookie = self.cookie or None
        headers = HEADERS.copy()
        if cookie:
            headers["Cookie"] = cookie

        data, cached = {}, False

        # 存在备选 RSSHub URL 或处于 debug 模式时，不使用 HTTP 缓存
        if not (plugin_config.rsshub_fallback_urls or plugin_config.debug):
            if self.etag:
                headers["If-None-Match"] = self.etag
            if self.last_modified:
                headers["If-Modified-Since"] = self.last_modified

        async with aiohttp.ClientSession(
            headers=headers, raise_for_status=True, timeout=aiohttp.ClientTimeout(10)
        ) as session:
            try:
                async with session.get(url, proxy=proxy) as resp:
                    # 存在备选 RSSHub URL 时，不使用 HTTP 缓存
                    if not plugin_config.rsshub_fallback_urls:
                        self.etag = resp.headers.get("ETag")
                        self.last_modified = resp.headers.get("Last-Modified")
                        self.upsert()

                    if resp.status == 304 or (
                        resp.status == 200
                        and int(resp.headers.get("Content-Length", "1")) == 0
                    ):
                        cached = True

                    data = feedparser.parse(await resp.text())
            except Exception:
                msg = f"{self._log_prefix}链接 {url} 访问失败"
                if not self.url.scheme and plugin_config.rsshub_fallback_urls:
                    # 对 RSSHub 路由尝试使用备用 RSSHub 地址
                    logger.warning(msg + "，尝试访问备用 RSSHub 地址")
                    data = await self.fetch_fallback(session, proxy)
                else:
                    logger.error(msg)

        return data, cached

    async def fetch_fallback(
        self, session: aiohttp.ClientSession, proxy: Optional[str]
    ) -> tuple[dict[str, Any]]:
        """使用备用 RSSHub 地址抓取 RSS"""
        data = {}
        for fallback_url in plugin_config.rsshub_fallback_urls:
            url = URL(self.get_url(fallback_url))
            try:
                async with session.get(url, proxy=proxy) as resp:
                    data = feedparser.parse(await resp.text())
                    # 遍历备用地址直到抓取到有效的 RSS 数据为止
                    if data.get("feed"):
                        break
            except Exception:
                logger.error(f"{self._log_prefix}链接 {url} 访问失败")
                continue
        return data

    async def stop_update_and_notify(self, bot: Bot, reason: str):
        """停止更新订阅并通知超级用户"""
        self.stop = True
        # 更新数据库
        self.upsert()
        # 移除定时任务
        if scheduler.get_job(self.name):
            scheduler.remove_job(self.name)
        # 通知超级用户
        await send_msg_to_superusers(
            bot,
            global_config.superusers,
            f"{self.name}[{self.url}]已停止更新 ({reason})",
        )
