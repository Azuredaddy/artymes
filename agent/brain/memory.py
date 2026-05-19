import sqlite3
import json
import os
from datetime import datetime
from typing import Optional
import chromadb
from chromadb.utils import embedding_functions
from config import MEMORY_DB_PATH, CHROMA_PATH


class ArtyMemory:
    def __init__(self):
        os.makedirs(os.path.dirname(MEMORY_DB_PATH), exist_ok=True)
        os.makedirs(CHROMA_PATH, exist_ok=True)
        self._init_sqlite()
        self._init_chroma()

    # ── SQLite: conversation history ──────────────────────────────────────────

    def _init_sqlite(self):
        self.conn = sqlite3.connect(MEMORY_DB_PATH, check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                session_id TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS training_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'open',
                confidence REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS procedures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                steps_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        self.conn.commit()

    def save_message(self, role: str, content: str, session_id: str = None):
        self.conn.execute(
            "INSERT INTO conversations (role, content, timestamp, session_id) VALUES (?, ?, ?, ?)",
            (role, content, datetime.now().isoformat(), session_id)
        )
        self.conn.commit()

    def get_recent_messages(self, limit: int = 20) -> list[dict]:
        cursor = self.conn.execute(
            "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = cursor.fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def save_training_note(self, topic: str, content: str, source: str = None):
        self.conn.execute(
            "INSERT INTO training_notes (topic, content, source, timestamp) VALUES (?, ?, ?, ?)",
            (topic, content, source, datetime.now().isoformat())
        )
        self.conn.commit()
        self.add_to_knowledge(content, metadata={"type": "training", "topic": topic})

    def save_task(self, title: str, description: str = None, confidence: float = 1.0) -> int:
        cursor = self.conn.execute(
            "INSERT INTO tasks (title, description, confidence, created_at) VALUES (?, ?, ?, ?)",
            (title, description, confidence, datetime.now().isoformat())
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_open_tasks(self) -> list[dict]:
        cursor = self.conn.execute(
            "SELECT id, title, description, confidence FROM tasks WHERE status = 'open'"
        )
        return [{"id": r[0], "title": r[1], "description": r[2], "confidence": r[3]}
                for r in cursor.fetchall()]

    def update_task_status(self, task_id: int, status: str):
        self.conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now().isoformat(), task_id)
        )
        self.conn.commit()

    # ── ChromaDB: semantic knowledge base ─────────────────────────────────────

    def _init_chroma(self):
        self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)
        ef = embedding_functions.DefaultEmbeddingFunction()
        self.knowledge = self.chroma.get_or_create_collection(
            name="arty_knowledge",
            embedding_function=ef
        )

    def add_to_knowledge(self, text: str, metadata: dict = None):
        doc_id = f"doc_{datetime.now().timestamp()}"
        self.knowledge.add(
            documents=[text],
            metadatas=[metadata or {}],
            ids=[doc_id]
        )

    def search_knowledge(self, query: str, n_results: int = 5) -> list[str]:
        if self.knowledge.count() == 0:
            return []
        results = self.knowledge.query(
            query_texts=[query],
            n_results=min(n_results, self.knowledge.count())
        )
        return results["documents"][0] if results["documents"] else []

    def build_context_for_query(self, query: str) -> str:
        snippets = self.search_knowledge(query)
        if not snippets:
            return ""
        joined = "\n---\n".join(snippets)
        return f"Relevant knowledge from your training:\n{joined}"

    def save_procedure(self, name: str, steps: list):
        existing = self.conn.execute(
            "SELECT id FROM procedures WHERE name = ?", (name,)
        ).fetchone()
        now = datetime.now().isoformat()
        if existing:
            self.conn.execute(
                "UPDATE procedures SET steps_json = ?, updated_at = ? WHERE name = ?",
                (json.dumps(steps), now, name)
            )
        else:
            self.conn.execute(
                "INSERT INTO procedures (name, steps_json, recorded_at) VALUES (?, ?, ?)",
                (name, json.dumps(steps), now)
            )
        self.conn.commit()

    def load_procedure(self, name: str) -> dict | None:
        row = self.conn.execute(
            "SELECT name, steps_json FROM procedures WHERE name = ?", (name,)
        ).fetchone()
        if not row:
            return None
        return {"name": row[0], "steps": json.loads(row[1])}

    def list_procedures(self) -> list:
        rows = self.conn.execute(
            "SELECT name, recorded_at FROM procedures ORDER BY name"
        ).fetchall()
        return [{"name": r[0], "recorded_at": r[1]} for r in rows]
