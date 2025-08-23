from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from nonebot import require
from tinydb import TinyDB

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

DB_FILE = store.get_plugin_data_file("rss_data.json")


@dataclass
class RSS:
    # 订阅名
    name: str = ""
    # 订阅地址
    url: str = ""
    # 订阅用户
    user_id: list[str] = field(default_factory=list)
    # 订阅群组
    group_id: list[str] = field(default_factory=list)
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
