import nonebot

from .config import Config

# 全局变量
global_config = nonebot.get_driver().config
plugin_config = nonebot.get_plugin_config(Config).elf_rss
