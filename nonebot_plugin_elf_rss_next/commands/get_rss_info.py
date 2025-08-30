from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent

from ..rss import RSS
from . import elf


@elf.assign("info")
async def get_rss_information(
    event: PrivateMessageEvent | GroupMessageEvent, name: str
):
    rss = RSS.get_by_name(name)
    if (
        (not rss)
        or (isinstance(event, PrivateMessageEvent) and event.user_id not in rss.user_id)
        or (isinstance(event, GroupMessageEvent) and event.group_id not in rss.group_id)
    ):
        await elf.finish("❌ 找不到该订阅")

    msgs = [
        f"订阅名：{rss.name} | 状态 {bool2emoji(not rss.stop)}",
        f"订阅地址：{rss.url}",
        f"更新频率：{rss.frequency}",
        f"代理 {bool2emoji(rss.use_proxy)} | Cookie {bool2emoji(len(rss.cookie) > 0)} | 翻译 {bool2emoji(rss.translation)}",
        f"仅标题 {bool2emoji(rss.only_feed_title)} | 仅图片 {bool2emoji(rss.only_feed_pic)}",
        f"下载图片 {bool2emoji(rss.download_pic)} | 合并转发{bool2emoji(rss.send_merged_msg)}",
        f"白名单关键词：{rss.white_list_keyword}",
        f"黑名单关键词：{rss.black_list_keyword}",
        f"去重模式：{rss.deduplication_modes}",
        f"图片数量限制：{rss.max_image_number}",
        f"河蟹关键词：{rss.content_to_remove}",
    ]
    await elf.finish("\n".join(msgs))


def bool2emoji(value: bool) -> str:
    return "✅" if value else "❌"
