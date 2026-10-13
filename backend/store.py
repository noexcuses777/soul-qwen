import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .schemas import Session

class Store:
    def __init__(self,path):
        self.path=path; Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c: c.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=30)
        try:
            with c: yield c
        finally: c.close()
    def put(self,s):
        with self.connect() as c: c.execute('INSERT OR REPLACE INTO sessions VALUES (?,?)',(s.id,s.model_dump_json()))
    def get(self,id):
        with self.connect() as c: row=c.execute('SELECT payload FROM sessions WHERE id=?',(id,)).fetchone()
        if not row: raise KeyError(id)
        return Session.model_validate_json(row[0])
    def delete(self,id):
        with self.connect() as c: c.execute('DELETE FROM sessions WHERE id=?',(id,))
    def latest(self):
        with self.connect() as c: row=c.execute('SELECT payload FROM sessions ORDER BY rowid DESC LIMIT 1').fetchone()
        return Session.model_validate_json(row[0]) if row else None
