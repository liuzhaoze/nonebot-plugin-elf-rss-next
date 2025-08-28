import contextlib
import hashlib
from email.utils import parsedate_to_datetime
from typing import Any, Optional

import arrow
from asyncache import cached
from cachetools import TTLCache
from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot

from .globals import plugin_config


def get_proxy(use_proxy: bool) -> Optional[str]:
    if not use_proxy or not plugin_config.proxy:
        return None
    return str(plugin_config.proxy)


async def send_msg_to_superusers(bot: Bot, superusers: set[str], msg: str):
    try:
        for su in superusers:
            await bot.send_private_msg(user_id=int(su), message=f"ELF_RSS: {msg}")
    except Exception as e:
        logger.error(f"消息推送至超级用户失败: {e}")


@cached(TTLCache(maxsize=1, ttl=300))
async def get_bot_friend_id_list(bot: Bot) -> set[int]:
    """获取机器人好友列表，结果缓存5分钟"""
    friends = await bot.get_friend_list()
    return {friend["user_id"] for friend in friends}


@cached(TTLCache(maxsize=1, ttl=300))
async def get_bot_group_id_list(bot: Bot) -> set[int]:
    """获取机器人群组列表，结果缓存5分钟"""
    groups = await bot.get_group_list()
    return {group["group_id"] for group in groups}


async def extract_valid_user_id(bot: Bot, user_ids: set[int]) -> set[int]:
    """提取有效的用户ID"""
    bot_users = await get_bot_friend_id_list(bot)
    valid, invalid = user_ids & bot_users, user_ids - bot_users
    if invalid:
        logger.warning(
            f"用户 {', '.join(map(str, invalid))} 不是机器人 {bot.self_id} 的好友"
        )
    return valid


async def extract_valid_group_id(bot: Bot, group_ids: set[int]) -> set[int]:
    """提取有效的群组ID"""
    bot_groups = await get_bot_group_id_list(bot)
    valid, invalid = group_ids & bot_groups, group_ids - bot_groups
    if invalid:
        logger.warning(
            f"机器人 {bot.self_id} 未加入群组 {', '.join(map(str, invalid))}"
        )
    return valid


def extract_entry_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """提取RSS条目中需要的字段"""
    wanted = ["guid", "title", "link", "published", "updated", "hash"]
    if entry.get("to_send"):
        wanted += ["to_send", "content", "summary"]
    return {k: v for k in wanted if (v := entry.get(k))}


def get_entry_hash(entry: dict[str, Any]) -> str:
    """计算RSS条目的哈希值"""
    unique_str = str(entry.get("guid", entry.get("link", "")))
    return hashlib.md5(unique_str.encode("utf-8")).hexdigest()


def get_entry_datetime(entry: dict[str, Any]):
    datetime = entry.get("published", entry.get("updated"))
    if not datetime:
        return arrow.now()

    with contextlib.suppress(Exception):
        datetime = parsedate_to_datetime(datetime)
    return arrow.get(datetime)


def chunk_list(lst: list[Any], chunk_size: int):
    """将列表分块"""
    for i in range(0, len(lst), chunk_size):
        yield lst[i : i + chunk_size]
