import asyncio
import re

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from async_timeout import timeout
from nonebot import logger, require

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

from .rss import RSS


async def check_rss_update(rss: RSS):
    """检查单个RSS订阅的更新"""
    logger.info(f"检查RSS订阅更新: {rss.name}")
    try:
        second = 1.0
        async with timeout(30 * second):
            await TODO: 获取RSS更新
    except asyncio.TimeoutError:
        logger.error(f"{rss.name} 检查更新超时，结束此次任务!")


async def create_rss_update_job(rss: RSS):
    """创建检查RSS更新定时任务"""
    # 删除已存在的重名任务
    if scheduler.get_job(rss.name):
        scheduler.remove_job(rss.name)

    # 确保用户、群组、频道三个订阅目标至少有一个
    if not any([rss.user_id, rss.group_id, rss.guild_channel_id]):
        logger.warning(f"RSS订阅 {rss.name} 没有有效的订阅目标，跳过创建任务")
        return

    # 创建触发器
    if re.search(r"[_*/,-]", rss.frequency):
        cron_expression = ["*/5", "*", "*", "*", "*"]
        for index, value in enumerate(rss.frequency.split("_")):
            if value:
                cron_expression[index] = value
        try:
            trigger = CronTrigger(
                minute=cron_expression[0],
                hour=cron_expression[1],
                day=cron_expression[2],
                month=cron_expression[3],
                day_of_week=cron_expression[4],
            )
        except Exception as e:
            logger.error(f"创建RSS订阅 {rss.name} 的 CronTrigger 失败: {e}")
            return
    else:
        try:
            trigger = IntervalTrigger(minutes=int(rss.frequency), jitter=10)
        except Exception as e:
            logger.error(f"创建RSS订阅 {rss.name} 的 IntervalTrigger 失败: {e}")
            return

    # 添加定时任务
    scheduler.add_job(
        func=check_rss_update,
        trigger=trigger,
        args=(rss,),
        id=rss.name,
        misfire_grace_time=30,
        max_instances=1,
        coalesce=True,
    )
    logger.success(f"定时任务 {rss.name} 创建成功")

    # 立即执行一次订阅更新
    await check_rss_update(rss)
