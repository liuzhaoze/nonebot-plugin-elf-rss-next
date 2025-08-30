import re
from copy import deepcopy

from nonebot import require
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from yarl import URL

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

from ..rss import RSS
from ..scheduler import create_rss_update_job, remove_rss_update_job
from . import elf


def handle_edit_name(rss: RSS, value: str, event=None):
    remove_rss_update_job(rss)
    old_rss_entries_file = store.get_plugin_data_file(f"{rss.sanitized_name}.json")
    rss.name = value
    if old_rss_entries_file.exists():
        old_rss_entries_file.rename(
            store.get_plugin_data_file(f"{rss.sanitized_name}.json")
        )


def handle_edit_url(rss: RSS, value: str, event=None):
    rss.url = URL(value)


def handle_edit_user_id(rss: RSS, value: str, event=None):
    if event is None:
        return
    if isinstance(event, GroupMessageEvent):
        elf.send("❌ 禁止在群组中修改订阅账号，如要取消订阅请使用 del 命令！")
        return
    if value == "-1":
        rss.user_id = set()
        return

    new_users = {int(uid) for uid in value.split(",") if len(uid) > 0}
    if value.startswith(","):
        rss.user_id |= new_users
    else:
        rss.user_id = new_users


def handle_edit_group_id(rss: RSS, value: str, event=None):
    if event is None:
        return
    if isinstance(event, GroupMessageEvent):
        raise Exception("❌ 禁止在群组中修改订阅账号，如要取消订阅请使用 del 命令！")
    if value == "-1":
        rss.group_id = set()
        return

    new_groups = {int(gid) for gid in value.split(",") if len(gid) > 0}
    if value.startswith(","):
        rss.group_id |= new_groups
    else:
        rss.group_id = new_groups


def handle_edit_use_proxy(rss: RSS, value: str, event=None):
    rss.use_proxy = bool(int(value))


def handle_edit_frequency(rss: RSS, value: str, event=None):
    if re.search(r"[_*/,-]", value):
        rss.frequency = value
    else:
        if int(float(value)) < 1:
            rss.frequency = "1"
        else:
            rss.frequency = str(int(float(value)))


def handle_edit_translation(rss: RSS, value: str, event=None):
    rss.translation = bool(int(value))


def handle_edit_only_feed_title(rss: RSS, value: str, event=None):
    rss.only_feed_title = bool(int(value))


def handle_edit_only_feed_pic(rss: RSS, value: str, event=None):
    rss.only_feed_pic = bool(int(value))


def handle_edit_download_pic(rss: RSS, value: str, event=None):
    rss.download_pic = bool(int(value))


def handle_edit_cookie(rss: RSS, value: str, event=None):
    rss.cookie = value


def handle_edit_white_list_keyword(rss: RSS, value: str, event=None):
    if value == "-1":
        rss.white_list_keyword = ""
        return
    re.compile(value)
    rss.white_list_keyword = value


def handle_edit_black_list_keyword(rss: RSS, value: str, event=None):
    if value == "-1":
        rss.black_list_keyword = ""
        return
    re.compile(value)
    rss.black_list_keyword = value


def handle_edit_deduplication_modes(rss: RSS, value: str, event=None):
    if not value.startswith(("+", "-")):
        raise Exception("❌ mode 参数错误")
    operation = value[0]
    mode = value[1:]
    if mode not in {"title", "link", "image", "or"}:
        raise Exception("❌ mode 参数错误")
    if operation == "+":
        rss.deduplication_modes.add(mode)
    else:
        rss.deduplication_modes.discard(mode)


def handle_edit_max_image_number(rss: RSS, value: str, event=None):
    if not value.isdigit() or int(value) < 0:
        raise Exception("❌ max_image_number 参数错误")
    rss.max_image_number = int(value)


def handle_exit_content_to_remove(rss: RSS, value: str, event=None):
    if not value.startswith(("+", "-")):
        raise Exception("❌ hexie 参数错误")
    operation = value[0]
    keyword = value[1:]
    if operation == "+":
        rss.content_to_remove.add(keyword)
    else:
        rss.content_to_remove.discard(keyword)


def handle_edit_send_merge_msg(rss: RSS, value: str, event=None):
    rss.send_merged_msg = bool(int(value))


def handle_edit_stop(rss: RSS, value: str, event=None):
    rss.stop = bool(int(value))


EDIT_HANDLERS = {
    "name": handle_edit_name,
    "url": handle_edit_url,
    "qq": handle_edit_user_id,
    "qun": handle_edit_group_id,
    "proxy": handle_edit_use_proxy,
    "freq": handle_edit_frequency,
    "trans": handle_edit_translation,
    "ot": handle_edit_only_feed_title,
    "op": handle_edit_only_feed_pic,
    "dp": handle_edit_download_pic,
    "cookie": handle_edit_cookie,
    "wkey": handle_edit_white_list_keyword,
    "bkey": handle_edit_black_list_keyword,
    "mode": handle_edit_deduplication_modes,
    "image": handle_edit_max_image_number,
    "hexie": handle_exit_content_to_remove,
    "merge": handle_edit_send_merge_msg,
    "stop": handle_edit_stop,
}


@elf.assign("edit")
async def edit_rss(
    event: PrivateMessageEvent | GroupMessageEvent, name: str, options: list[str]
):
    rss = RSS.get_by_name(name)
    if (
        (not rss)
        or (isinstance(event, PrivateMessageEvent) and event.user_id not in rss.user_id)
        or (isinstance(event, GroupMessageEvent) and event.group_id not in rss.group_id)
    ):
        await elf.finish("❌ 找不到该订阅")

    old_name = rss.name
    new_rss = deepcopy(rss)

    for option in options:
        key, value = option.split("=", 1)
        if key not in EDIT_HANDLERS.keys():
            await elf.finish(f"❌ 属性 {key} 不存在")

        try:
            EDIT_HANDLERS[key](new_rss, value, event)
        except Exception as e:
            await elf.finish(f"❌ 修改 {key} 失败，错误信息:\n{e}")

    # 参数更新完毕，写入数据库
    new_rss.upsert(old_name)

    # 更新定时任务
    if not new_rss.stop:
        # 更新之后的 RSS 没有停止更新，则添加定时任务
        await create_rss_update_job(new_rss)
    elif not rss.stop:
        # 更新之后的 RSS 停止更新了，说明想让原来的 RSS 停止更新，则删除定时任务
        remove_rss_update_job(rss)

    await elf.finish("👏 修改成功")
