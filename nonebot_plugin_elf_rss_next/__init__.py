import asyncio

import nonebot
from nonebot import logger, on_metaevent, require
from nonebot.adapters.onebot.v11 import Bot
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

from .config import Config
from .rss import RSS
from .scheduler import create_rss_update_job
from .utils import send_msg_to_superusers

__plugin_meta__ = PluginMetadata(
    name="ELF_RSS Next",
    description="RSS订阅机器人“ELF_RSS”的独立插件版本",
    usage="TODO:",
    type="application",
    homepage="https://github.com/liuzhaoze/nonebot-plugin-elf-rss-next",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

global_config = nonebot.get_driver().config
plugin_config = nonebot.get_plugin_config(Config)

startup = on_metaevent(temp=True)


@startup.handle()
async def startup_handler(bot: Bot):
    """初始化"""
    logger.info(f"RSS数据目录: {store.get_plugin_data_dir()}")

    rss_data_file = store.get_plugin_data_file("rss_data.json")
    logger.info(f"加载RSS数据文件: {rss_data_file}")
    rss_list = RSS.load_rss_data(rss_data_file)

    if len(rss_list) == 0:
        msg = "尚无订阅数据，配置和使用方法参照: TODO:"
        logger.warning(msg)
        await send_msg_to_superusers(bot, global_config.superusers, f"ELF_RSS: {msg}")
    else:
        msg = f"已加载 {len(rss_list)} 项订阅数据"
        logger.info(msg)
        await send_msg_to_superusers(bot, global_config.superusers, f"ELF_RSS: {msg}")

    logger.info("启动检查订阅更新定时任务")
    await asyncio.gather(
        *[create_rss_update_job(rss) for rss in rss_list if not rss.stop]
    )
    logger.success("初始化完成")
