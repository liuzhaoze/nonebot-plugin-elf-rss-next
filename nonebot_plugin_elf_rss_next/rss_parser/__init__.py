"""
# RSS 解析步骤

## 预处理
| 优先级 |          步骤          |
|--------|------------------------|
|   20   |     找到新增的文章     |
|   21   |      过滤非法文章      |
|   22   |过滤已经发送过的重复文章|

## 文章处理
|   优先级    |          步骤          |
|-------------|------------------------|
|      0      |    检查文档是否有效    |
|     20      |      处理文档标题      |
|     40      |      处理文档图片      |
|     49      |  决定是否处理文档正文  |
| 50 (默认值) |      处理文档正文      |
|     60      |      移除指定内容      |
|     61      |        翻译消息        |
|     70      |      添加文章链接      |
|     71      |      添加文章时间      |
|     100     |      创建下载任务      |

## 后处理
|   优先级    |      步骤      |
|-------------|----------------|
| 50 (默认值) |    发送消息    |
|     100     | 关闭数据库连接 |
"""

import re
import sqlite3
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

import arrow
import emoji
from nonebot import logger, require
from pyquery import PyQuery as pq
from yarl import URL

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

if TYPE_CHECKING:
    from ..rss import RSS

from ..globals import plugin_config
from ..utils import get_entry_datetime, get_entry_hash
from . import rss_entries_file_operations as FileIO
from .cache_db_manager import (
    initialize_cache_db,
    insert_into_cache_db,
    is_entry_duplicated,
)
from .context import Context
from .html_document_processor import handle_html_tags
from .image_processor import get_image_cqcode
from .message_sender import send_message
from .rss_parser import ParsingHandlerManager, RSSParser
from .translation import translate
from .utils import get_summary

__all__ = ["RSSParser"]


@ParsingHandlerManager.preprocess_handler(priority=20)
async def find_new_entries(ctx: Context, rss: "RSS"):
    """预处理第 1 步：找到新增的文章"""
    db = ctx.tinydb
    old_entry_hashes = {entry.get("hash") for entry in db.all()}

    for entry in ctx.entries:
        entry_hash = get_entry_hash(entry)
        if entry_hash not in old_entry_hashes:
            entry["hash"] = entry_hash
            ctx.new_entries.append(entry)

    ctx.new_entries.sort(key=get_entry_datetime)


@ParsingHandlerManager.preprocess_handler(priority=21)
async def filter_invalid_entries(ctx: Context, rss: "RSS"):
    """预处理第 2 步：过滤非法文章"""
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
async def filter_duplicate_entries(ctx: Context, rss: "RSS"):
    """预处理第 3 步：过滤已经发送过的重复文章"""
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
            logger.info(f"[{rss.name}]去重模式下发现重复文章，已过滤")
            FileIO.write_entry(ctx.tinydb, entry)
        else:
            filtered_entries.append(entry)

    ctx.new_entries = filtered_entries


@ParsingHandlerManager.process_handler(priority=0)
async def validate_entry(ctx: Context, rss: "RSS"):
    """检查当前处理的文章是否有效"""
    if not ctx.entry:
        logger.error(f"[{rss.name}]未能正确装填待处理的文章，终止后续处理")
        ctx.continue_process = False


@ParsingHandlerManager.process_handler(priority=20)
async def handle_entry_title(ctx: Context, rss: "RSS"):
    """处理文章标题"""
    if rss.only_feed_pic:
        # 仅推送图片模式下不处理标题
        return

    entry = ctx.entry

    entry_title = entry.get("title", "无标题")
    if not plugin_config.blockquote:
        entry_title = re.sub(r" - 转发 .*", "", entry_title)

    entry_title = "标题：" + entry_title

    if rss.only_feed_title:
        ctx.msg_text_buffer += emoji.emojize(entry_title, language="alias")
        return

    # 判断标题与正文的相似度，避免标题正文一样，或者标题为正文前缀等情况
    try:
        summary_doc = pq(get_summary(entry))
        if not plugin_config.blockquote:
            summary_doc.remove("blockquote")
        similarity = SequenceMatcher(
            None, summary_doc.text()[: len(entry_title)], entry_title
        )
        if similarity.ratio() > 0.6:
            # 标题与正文相似时取消显示标题
            entry_title = ""
    except Exception as e:
        logger.warning(f"[{rss.name}]没有正文内容: {e}")

    ctx.msg_text_buffer += emoji.emojize(entry_title, language="alias")


@ParsingHandlerManager.process_handler(priority=40)
async def handle_images(ctx: Context, rss: "RSS"):
    """处理文章图片"""
    if rss.only_feed_title:
        # 仅推送标题模式下不处理图片
        return

    if rss.only_feed_pic:
        # 仅推送图片模式下不推送文本
        ctx.msg_text_buffer = ""

    entry = ctx.entry

    if entry.get("image_content"):
        ctx.msg_image_buffer += await get_image_cqcode(
            URL(entry.get("gif_url", "")),
            rss.use_proxy,
            rss.download_pic,
            rss.sanitized_name,
            entry["image_content"],
        )
        return

    entry_doc = pq(get_summary(entry))
    entry_images = list(entry_doc("img").items())
    if 0 < rss.max_image_number < len(entry_images):
        ctx.msg_image_buffer += (
            f"图片数量限制已启用，仅显示 {rss.max_image_number} 张图片\n"
        )
        entry_images = entry_images[: rss.max_image_number]
    for img in entry_images:
        url = img.attr("src")
        ctx.msg_image_buffer += await get_image_cqcode(
            URL(url), rss.use_proxy, rss.download_pic, rss.sanitized_name
        )

    # 处理视频
    if entry_video := entry_doc("video"):
        ctx.msg_image_buffer += "\n视频封面："
        for video in entry_video.items():
            url = video.attr("poster")
            ctx.msg_image_buffer += await get_image_cqcode(
                URL(url), rss.use_proxy, rss.download_pic, rss.sanitized_name
            )


@ParsingHandlerManager.process_handler(priority=49)
async def decide_whether_handle_summary(ctx: Context, rss: "RSS"):
    """决定是否处理正文"""
    if rss.only_feed_title or rss.only_feed_pic:
        ctx.continue_process = False


@ParsingHandlerManager.process_handler()
async def handle_summary(ctx: Context, rss: "RSS"):
    """处理文章正文"""
    entry = ctx.entry

    try:
        entry_doc = pq(get_summary(entry))
        article = handle_html_tags(entry_doc)
    except Exception as e:
        logger.warning(f"[{rss.name}]处理正文时出错: {e}")

    ctx.msg_text_buffer += "\n\n" + article


@ParsingHandlerManager.process_handler(priority=60)
async def remove_unwanted_content(ctx: Context, rss: "RSS"):
    """移除指定内容"""
    article = emoji.demojize(ctx.msg_text_buffer)
    if rss.content_to_remove:
        for pattern in rss.content_to_remove:
            article = re.sub(pattern, "", article)
        # 去除多余换行
        while "\n\n\n" in article:
            article = article.replace("\n\n\n", "\n\n")
        article = article.strip()

    ctx.msg_text_buffer = emoji.emojize(article, language="alias")


@ParsingHandlerManager.process_handler(priority=61)
async def translate_message(ctx: Context, rss: "RSS"):
    """翻译消息"""
    if rss.translation:
        translated = await translate(ctx.msg_text_buffer, rss.use_proxy)
        ctx.msg_text_buffer += "\n\n" + translated


@ParsingHandlerManager.process_handler(priority=70)
async def note_link(ctx: Context, rss: "RSS"):
    """添加文章链接"""
    ctx.msg_text_buffer += f"\n\n链接：{ctx.entry.get('link', '无链接')}"


@ParsingHandlerManager.process_handler(priority=71)
async def note_datetime(ctx: Context, rss: "RSS"):
    """添加文章时间"""
    datetime = get_entry_datetime(ctx.entry)
    datetime = (
        datetime.replace(tzinfo="local")
        if datetime > arrow.now()
        else datetime.to("local")
    )
    ctx.msg_text_buffer += f"\n日期：{datetime.format('YYYY年MM月DD日 HH:mm:ss')}"


@ParsingHandlerManager.postprocess_handler()
async def send_messages(ctx: Context, rss: "RSS"):
    if not ctx.msg_contents:
        logger.info(f"[{rss.name}]没有新推送")
        return

    success = False

    if rss.send_merged_msg:
        # 发送合并转发消息
        msgs_to_send = [ctx.msg_title + "\n\n" + c for c in ctx.msg_contents.values()]
        success |= await send_message(rss.user_id, rss.group_id, msgs_to_send)
        if success:
            for entry in ctx.new_entries:
                if rss.deduplication_modes:
                    # 将已发送的条目写入去重数据库
                    insert_into_cache_db(ctx.conn, entry)
                if entry.get("to_send"):
                    # 移除待发送标记
                    entry.pop("to_send")
                # 更新 rss entries file
                FileIO.write_entry(ctx.tinydb, entry)
        else:
            logger.warning(f"[{rss.name}]发送合并消息失败，将使用逐条发送")
            for entry in ctx.new_entries:
                entry["to_send"] = True
            ctx.msg_error_count += len(ctx.msg_contents)

    new_entries_hash_index_map = {e["hash"]: i for i, e in enumerate(ctx.new_entries)}
    if not success:
        for entry_hash, content in ctx.msg_contents.items():
            # 逐条发送消息
            entry = ctx.new_entries[new_entries_hash_index_map[entry_hash]]
            msg_to_send = ctx.msg_title + "\n\n" + content
            success |= await send_message(rss.user_id, rss.group_id, msg_to_send)
            if success:
                if rss.deduplication_modes:
                    # 将已发送的条目写入去重数据库
                    insert_into_cache_db(ctx.conn, entry)
                if entry.get("to_send"):
                    # 移除待发送标记
                    entry.pop("to_send")
            else:
                entry["to_send"] = True
                ctx.msg_error_count += 1
            # 更新 rss entries file
            FileIO.write_entry(ctx.tinydb, entry)

    FileIO.truncate_file(ctx.tinydb, len(ctx.new_entries))

    if success:
        logger.info(
            f"[{rss.name}]推送成功"
            + (f"，失败{ctx.msg_error_count}次" if ctx.msg_error_count else "")
        )
    else:
        logger.error(f"[{rss.name}]推送失败，共失败{ctx.msg_error_count}次")


@ParsingHandlerManager.postprocess_handler(priority=100)
async def close_db_connection(ctx: Context, rss: "RSS"):
    """关闭数据库连接"""
    if ctx.conn:
        ctx.conn.close()
        ctx.conn = None

    if ctx.tinydb:
        ctx.tinydb.close()
        ctx.tinydb = None
