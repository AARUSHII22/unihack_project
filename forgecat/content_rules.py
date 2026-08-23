from __future__ import annotations

import json

from forgecat.db import get_connection


def get_field_rules(field_name: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT rules_json FROM content_field_rules WHERE field_name = ?",
        (field_name,),
    ).fetchone()
    conn.close()
    return json.loads(row["rules_json"]) if row else {}


def all_field_rules() -> dict[str, dict]:
    conn = get_connection()
    rows = conn.execute("SELECT field_name, rules_json FROM content_field_rules").fetchall()
    conn.close()
    return {r["field_name"]: json.loads(r["rules_json"]) for r in rows}
