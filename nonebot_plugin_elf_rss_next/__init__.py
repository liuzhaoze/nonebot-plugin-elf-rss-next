import asyncio

from nonebot import logger, on_metaevent
from nonebot.adapters.onebot.v11 import Bot
from nonebot.plugin import PluginMetadata

from . import commands
from .config import Config
from .globals import global_config
from .rss import DB_FILE, RSS
from .scheduler import create_rss_update_job
from .utils import send_msg_to_superusers

__plugin_meta__ = PluginMetadata(
    name="ELF_RSS Next",
    description="RSS订阅机器人“ELF_RSS”的独立插件版本",
    usage="https://github.com/liuzhaoze/nonebot-plugin-elf-rss-next/blob/main/README.md",
    type="application",
    homepage="https://github.com/liuzhaoze/nonebot-plugin-elf-rss-next",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

startup = on_metaevent(temp=True)


@startup.handle()
async def startup_handler(bot: Bot):
    """初始化"""
    logger.info(f"加载RSS数据文件: {DB_FILE}")
    rss_list = RSS.load_rss_data()

    if len(rss_list) == 0:
        msg = "尚无订阅数据，配置和使用方法参见：https://github.com/liuzhaoze/nonebot-plugin-elf-rss-next"
        logger.warning(msg)
        await send_msg_to_superusers(bot, global_config.superusers, msg)
    else:
        msg = f"已加载 {len(rss_list)} 项订阅数据"
        logger.info(msg)
        await send_msg_to_superusers(bot, global_config.superusers, msg)

    logger.info("启动检查订阅更新定时任务")
    await asyncio.gather(
        *[create_rss_update_job(rss) for rss in rss_list if not rss.stop]
    )
    logger.success("初始化完成")
