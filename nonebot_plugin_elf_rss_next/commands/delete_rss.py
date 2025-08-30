from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent

from ..rss import RSS
from ..scheduler import create_rss_update_job, remove_rss_update_job
from . import elf


@elf.assign("del")
async def delete_rss(
    event: PrivateMessageEvent | GroupMessageEvent, names: tuple[str, ...]
):
    success: list[str] = []
    fail: list[str] = []

    for name in names:
        rss = RSS.get_by_name(name)
        if rss is None:
            fail.append(name)
            continue

        done = False
        if isinstance(event, PrivateMessageEvent):
            done = rss.remove_subscriber(user_id=event.user_id)
        elif isinstance(event, GroupMessageEvent):
            done = rss.remove_subscriber(group_id=event.group_id)

        if not done:
            fail.append(name)
        else:
            success.append(name)
            if any([rss.user_id, rss.group_id]):
                await create_rss_update_job(rss)
            else:
                remove_rss_update_job(rss)
                rss.destroy()

    msgs: list[str] = []
    if success:
        msgs.append(f"👏 成功取消订阅：{'，'.join(success)}")
    if fail:
        msgs.append(f"❌ 未找到订阅：{'，'.join(fail)}")
    await elf.finish("\n".join(msgs))
