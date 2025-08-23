from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from nonebot import get_bot, require
from nonebot.adapters.onebot.v11 import Bot
from tinydb import Query, TinyDB
from yarl import URL

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

from . import global_config, plugin_config
from .utils import filter_valid_group_id, filter_valid_user_id, send_msg_to_superusers

DB_FILE = store.get_plugin_data_file("rss_data.json")


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
    # 是否使用图片代理
    img_proxy: bool = False
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
    cookies: str = ""
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

    def get_url(self) -> str:
        if self.url.scheme in {"http", "https"}:
            # url 是完整的订阅链接
            return str(self.url)
        else:
            # url 不是完整链接则代表 RSSHub 路由
            base = str(plugin_config.rsshub_url).rstrip("/")
            route = str(self.url).lstrip("/")
            return f"{base}/{route}"

    async def filter_valid_subscribers(self, bot: Bot):
        if self.user_id:
            self.user_id = await filter_valid_user_id(bot, self.user_id)
        if self.group_id:
            self.group_id = await filter_valid_group_id(bot, self.group_id)

    async def update(self):
        bot = get_bot()

        # 检查订阅者是否合法
        await self.filter_valid_subscribers(bot)
        if not any([self.user_id, self.group_id]):
            await self.stop_update_and_notify(bot, reason="当前没有用户或群组订阅该RSS")
            return

        # TODO: 接着往下重构

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
            f"{self.name}[{self.get_url()}]已停止更新 ({reason})",
        )
