from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot


async def send_msg_to_superusers(bot: Bot, superusers: set[str], msg: str):
    try:
        for su in superusers:
            await bot.send_private_msg(user_id=int(su), message=msg)
    except Exception as e:
        logger.error(f"消息推送至超级用户失败: {e}")
