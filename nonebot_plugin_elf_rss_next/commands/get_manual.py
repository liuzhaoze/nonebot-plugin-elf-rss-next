from . import elf


@elf.assign("help")
async def get_manual():
    msg = """ELF_RSS使用帮助
elf help 获取帮助信息
elf add 订阅名 订阅地址 (添加订阅)
elf del 订阅名 [订阅名 ...] (取消订阅)
elf ls (列出所有订阅)
elf info 订阅名 (获取订阅详情)
elf edit 订阅名 属性=值 [属性=值 ...] (修改订阅属性)
详细使用方法参见：https://github.com/liuzhaoze/nonebot-plugin-elf-rss-next"""
    await elf.finish(msg)
