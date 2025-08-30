from typing import Any

from tinydb import Query, TinyDB
from tinydb.operations import delete

from ..globals import plugin_config
from ..utils import extract_entry_fields, get_entry_datetime


def write_entry(db: TinyDB, entry: dict[str, Any]):
    if not entry.get("to_send"):
        db.update(delete("to_send"), Query().hash == str(entry.get("hash")))
    db.upsert(extract_entry_fields(entry), Query().hash == str(entry.get("hash")))


def truncate_file(db: TinyDB, num_new_entries: int):
    """限制 rss entries file 中条目的数量"""
    limit = plugin_config.rss_entries_file_limit + num_new_entries
    retains = db.all()
    retains.sort(key=get_entry_datetime)
    retains = retains[-limit:]
    db.truncate()
    db.insert_multiple(retains)
