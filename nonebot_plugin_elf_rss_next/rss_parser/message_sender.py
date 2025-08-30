import asyncio
from collections import defaultdict
from typing import Literal

import arrow
from nonebot import get_bot, logger
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment

from ..globals import global_config

sending_lock: defaultdict[tuple[int, str], asyncio.Lock] = defaultdict(asyncio.Lock)


async def send_message_with_lock(
    bot: Bot, target_id: int, target_type: Literal["private", "group"], msg: Message
):
    start_time = arrow.now()
    success = False
    async with sending_lock[(target_id, target_type)]:
        try:
            await bot.send_msg(
                message_type=target_type,
                user_id=target_id,
                group_id=target_id,
                message=msg,
            )
        except Exception as e:
            logger.error(f"向 {target_type}({target_id}) 发送消息失败: {e}")
        else:
            success = True
        finally:
            await asyncio.sleep(
                max(0, 1.5 - (arrow.now() - start_time).total_seconds())
            )
    return success


def wrap_message(bot: Bot, message: str | list[str]) -> Message:
    """
    将消息包装成 Message 对象

    Args:
        bot (Bot): 发送消息的 Bot 实例
        message (str | list[str]): 传入字符串时，发送单条消息；传入列表时，发送合并转发消息
    """
    if isinstance(message, str):
        return Message(message)
    return Message(
        [
            MessageSegment.node_custom(
                int(bot.self_id),
                list(global_config.nickname)[0] if global_config.nickname else "\u200b",
                content=m,
            )
            for m in message
        ]
    )


async def send_message(
    user_id: set[int], group_id: set[int], message: str | list[str]
) -> bool:
    bot = get_bot()
    wrapped_msg = wrap_message(bot, message)
    success = False
    if user_id:
        success |= any(
            asyncio.gather(
                *[
                    send_message_with_lock(bot, uid, "private", wrapped_msg)
                    for uid in user_id
                ]
            )
        )
    if group_id:
        success |= any(
            asyncio.gather(
                *[
                    send_message_with_lock(bot, gid, "group", wrapped_msg)
                    for gid in group_id
                ]
            )
        )
    return success
