"""公开目录收据，不把目录缺失解释为详情不存在。"""
import json
import sqlite3
from pathlib import Path

def save_catalog(path, items):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS catalog (id TEXT PRIMARY KEY, source TEXT NOT NULL, payload TEXT NOT NULL)')
        for item in items:
            db.execute('INSERT OR REPLACE INTO catalog VALUES (?, ?, ?)', (item['id'], item['source'], json.dumps(item, ensure_ascii=False)))
    return len(items)

def save_detail_entries(path, entries):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS detail_entries (visit_id INTEGER PRIMARY KEY, item_id TEXT NOT NULL, business_key TEXT NOT NULL, source TEXT NOT NULL, payload TEXT NOT NULL)')
        for entry in entries:
            if entry['catalog_fact']['identity'] != entry['id']:
                raise ValueError('catalog and detail identity mismatch')
            db.execute('INSERT INTO detail_entries (item_id, business_key, source, payload) VALUES (?, ?, ?, ?)',
                       (entry['id'], entry['detail_fact']['business_key'], entry['source'], json.dumps(entry, ensure_ascii=False)))
    return len(entries)

def read_detail_entries(path):
    with sqlite3.connect(path) as db:
        rows = db.execute('SELECT payload FROM detail_entries ORDER BY visit_id').fetchall()
    return [json.loads(row[0]) for row in rows]
