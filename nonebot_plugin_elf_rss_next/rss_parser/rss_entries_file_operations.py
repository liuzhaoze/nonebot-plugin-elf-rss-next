from typing import Any

from tinydb import Query, TinyDB
from tinydb.operations import delete

from ..utils import extract_entry_fields


def write_entry(db: TinyDB, entry: dict[str, Any]):
    if not entry.get("to_send"):
        db.update(delete("to_send"), Query().hash == str(entry.get("hash")))
    db.upsert(extract_entry_fields(entry), Query().hash == str(entry.get("hash")))
