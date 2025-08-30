from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent

from ..rss import RSS
from . import elf


@elf.assign("ls")
async def list_rss(event: PrivateMessageEvent | GroupMessageEvent):
    if isinstance(event, PrivateMessageEvent):
        rss_list = [rss for rss in RSS.load_rss_data() if event.user_id in rss.user_id]
    elif isinstance(event, GroupMessageEvent):
        rss_list = [
            rss for rss in RSS.load_rss_data() if event.group_id in rss.group_id
        ]

    if not rss_list:
        await elf.finish("❌ 当前没有任何订阅")

    msgs = [f"📄 当前有 {len(rss_list)} 条订阅"]
    for rss in rss_list:
        msgs.append(f"{'🔴' if rss.stop else '🟢'} {rss.name}")
    await elf.finish("\n".join(msgs))
