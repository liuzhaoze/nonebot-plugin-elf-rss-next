from asyncache import cached
from cachetools import TTLCache
from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot


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


async def filter_valid_user_id(bot: Bot, user_ids: set[int]) -> set[int]:
    """过滤出有效的用户ID"""
    bot_users = await get_bot_friend_id_list(bot)
    valid, invalid = user_ids & bot_users, user_ids - bot_users
    if invalid:
        logger.warning(
            f"用户 {', '.join(map(str, invalid))} 不是机器人 {bot.self_id} 的好友"
        )
    return valid


async def filter_valid_group_id(bot: Bot, group_ids: set[int]) -> set[int]:
    """过滤出有效的群组ID"""
    bot_groups = await get_bot_group_id_list(bot)
    valid, invalid = group_ids & bot_groups, group_ids - bot_groups
    if invalid:
        logger.warning(
            f"机器人 {bot.self_id} 未加入群组 {', '.join(map(str, invalid))}"
        )
    return valid
