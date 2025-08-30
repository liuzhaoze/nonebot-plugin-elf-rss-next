from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from yarl import URL

from ..rss import RSS
from ..scheduler import create_rss_update_job
from . import elf


@elf.assign("add")
async def add_rss(event: PrivateMessageEvent | GroupMessageEvent, name: str, url: str):
    if RSS.get_by_name(name) is not None:
        await elf.finish(
            f"⚠️ 已存在同名订阅 {name}，请更换名称或使用 edit 命令追加订阅者"
        )

    rss = RSS(name=name, url=URL(url))
    user = event.user_id if isinstance(event, PrivateMessageEvent) else None
    group = event.group_id if isinstance(event, GroupMessageEvent) else None
    rss.add_subscriber(user_id=user, group_id=group)
    await create_rss_update_job(rss)
    await elf.finish(f"👏 已成功添加订阅 {name}")
