import re
import sqlite3

from nonebot import logger, require

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

from ..globals import plugin_config
from ..rss import RSS
from ..utils import get_entry_datetime, get_entry_hash
from . import rss_entries_file_operations as FileIO
from .cache_db_manager import initialize_cache_db, is_entry_duplicated
from .context import Context
from .rss_parser import ParsingHandlerManager, RSSParser
from .utils import get_summary

__all__ = ["RSSParser"]


@ParsingHandlerManager.preprocess_handler(priority=20)
async def find_new_entries(ctx: Context, rss: RSS):
    """预处理第 1 步：找到新增的条目"""
    db = ctx.tinydb
    old_entry_hashes = {entry.get("hash") for entry in db.all()}

    for entry in ctx.entries:
        entry_hash = get_entry_hash(entry)
        if entry_hash not in old_entry_hashes:
            entry["hash"] = entry_hash
            ctx.new_entries.append(entry)

    ctx.new_entries.sort(key=get_entry_datetime)


@ParsingHandlerManager.preprocess_handler(priority=21)
async def filter_invalid_entries(ctx: Context, rss: RSS):
    """预处理第 2 步：过滤非法条目"""
    filtered_entries = []

    for entry in ctx.new_entries:
        summary = get_summary(entry)
        should_remove = False
        reason = ""

        # 检查是否包含屏蔽词
        if plugin_config.black_words and re.findall(
            "|".join(plugin_config.black_words), summary
        ):
            should_remove = True
            reason = "检测到包含屏蔽词的消息，已取消发送"
        # 检查消息是否包含白名单关键词
        elif rss.white_list_keyword and not re.search(rss.white_list_keyword, summary):
            should_remove = True
            reason = "消息内容不包含白名单关键词，已取消发送"
        # 检查消息是否包含黑名单关键词
        elif rss.black_list_keyword and (
            re.search(rss.black_list_keyword, summary)
            or re.search(rss.black_list_keyword, entry["title"])
        ):
            should_remove = True
            reason = "检测到包含黑名单关键词的消息，已取消发送"
        # 检查消息是否只包含图片
        elif rss.only_feed_pic and not re.search(r"<img[^>]+>|\[img]", summary):
            should_remove = True
            reason = "开启仅推送图片模式，当前消息不含图片，已取消发送"

        if should_remove:
            logger.info(f"[{rss.name}]{reason}")
            FileIO.write_entry(ctx.tinydb, entry)
        else:
            filtered_entries.append(entry)

    ctx.new_entries = filtered_entries


@ParsingHandlerManager.preprocess_handler(priority=22)
async def filter_duplicate_entries(ctx: Context, rss: RSS):
    """预处理第 3 步：过滤已经发送过的重复条目"""
    if not rss.deduplication_modes:
        return

    filtered_entries = []

    if not ctx.conn:
        ctx.conn = sqlite3.connect(store.get_plugin_cache_file("cache.db"))
        ctx.conn.set_trace_callback(logger.trace)
    initialize_cache_db(ctx.conn)

    for entry in ctx.new_entries:
        duplicated = await is_entry_duplicated(
            ctx.conn, entry, rss.deduplication_modes, rss.use_proxy
        )
        if duplicated:
            logger.info(f"[{rss.name}]去重模式下发现重复条目，已过滤")
            FileIO.write_entry(ctx.tinydb, entry)
        else:
            filtered_entries.append(entry)

    ctx.new_entries = filtered_entries
