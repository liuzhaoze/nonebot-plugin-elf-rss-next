from sqlite3 import Connection
from typing import Any, Literal

from nonebot import logger
from pyquery import PyQuery as pq

from ..globals import plugin_config
from .image_processor import get_image_hash
from .utils import get_summary


def initialize_cache_db(conn: Connection) -> None:
    # 用来去重的 sqlite3 数据表如果不存在就创建一个
    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS main (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "title" TEXT,
    "link" TEXT,
    "image_hash" TEXT,
    "datetime" TEXT DEFAULT (DATETIME('Now', 'LocalTime'))
);"""
    )
    cursor.close()
    conn.commit()
    # 移除超过 plugin_config.cache_expire 天没重复过的记录
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM main WHERE datetime <= DATETIME('Now', 'LocalTime', ?);",
        (f"-{plugin_config.cache_expire} Day",),
    )
    cursor.close()
    conn.commit()


async def is_entry_duplicated(
    conn: Connection,
    entry: dict[str, Any],
    deduplication_modes: set[Literal["title", "link", "image", "or"]],
    use_proxy: bool,
) -> bool:
    cursor = conn.cursor()
    title = entry["title"]
    link = entry["link"]

    try:
        sql_conditions = []
        sql_args = []

        for mode in deduplication_modes:
            if mode == "or":  # 跳过 "or" 标记
                continue

            match mode:
                case "title":
                    sql_conditions.append("title=?")
                    sql_args.append(title)
                case "link":
                    sql_conditions.append("link=?")
                    sql_args.append(link)
                case "image":
                    try:
                        summary_doc = pq(get_summary(entry))
                    except Exception as e:
                        # 无正文内容，跳过图片去重
                        logger.warning(e)
                        continue
                    image_doc = summary_doc("img")
                    if len(image_doc) != 1:
                        # 仅处理只有一张图片的消息
                        continue
                    url = image_doc.attr("src")
                    image_hash = await get_image_hash(url, use_proxy)
                    if image_hash:
                        sql_conditions.append("image_hash=?")
                        sql_args.append(image_hash)
                        entry["image_hash"] = image_hash

        # 如果没有有效条件，直接返回 False
        if not sql_conditions:
            return False

        # 构建查询条件
        if "or" in deduplication_modes:
            sql = f"SELECT id FROM main WHERE ({' OR '.join(sql_conditions)})"
        else:
            sql = f"SELECT id FROM main WHERE {' AND '.join(sql_conditions)}"

        cursor.execute(sql, sql_args)
        result = cursor.fetchone()

        if result is not None:
            result_id = result[0]
            cursor.execute(
                "UPDATE main SET datetime = DATETIME('Now','LocalTime') WHERE id = ?;",
                (result_id,),
            )
            conn.commit()
            return True

        return False

    finally:
        cursor.close()


def insert_into_cache_db(conn: Connection, entry: dict[str, Any]) -> None:
    cursor = conn.cursor()
    title = entry["title"]
    link = entry["link"]
    image_hash = entry.get("image_hash")
    cursor.execute(
        "INSERT INTO main (title, link, image_hash) VALUES (?, ?, ?);",
        (title, link, image_hash),
    )
    cursor.close()
    conn.commit()
