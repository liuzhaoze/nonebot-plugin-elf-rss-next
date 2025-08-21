from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="ELF_RSS Next",
    description="RSS订阅机器人“ELF_RSS”的独立插件版本",
    usage="TODO:",
    type="application",
    homepage="https://github.com/liuzhaoze/nonebot-plugin-elf-rss-next",
    config=Config,
    supported_adapters={"~onebot.v11"},
)
