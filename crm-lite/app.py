"""Local CRM inspired by the two reference projects. Run: python app.py."""

from __future__ import annotations

import csv
import io
import os
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request, Response


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("CRM_DB_PATH", ROOT / "data" / "crm.db"))
STATUSES = ("Новый", "В работе", "Квалифицирован", "Выигран", "Проигран")
STAGES = ("Поиск", "Квалификация", "Предложение", "Переговоры", "Успешно", "Отказ")
FIELDS = (
    "name", "company", "email", "phone", "source", "industry", "country",
    "status", "stage", "amount", "probability", "close_date", "assignee",
    "priority", "satisfaction", "case_status", "follow_up",
)

app = Flask(__name__)
app.json.ensure_ascii = False


@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            industry TEXT NOT NULL DEFAULT '',
            country TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Новый',
            stage TEXT NOT NULL DEFAULT 'Поиск',
            amount REAL NOT NULL DEFAULT 0 CHECK(amount >= 0),
            probability INTEGER NOT NULL DEFAULT 0 CHECK(probability BETWEEN 0 AND 100),
            close_date TEXT NOT NULL DEFAULT '',
            assignee TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT 'Средний',
            satisfaction REAL,
            case_status TEXT NOT NULL DEFAULT '',
            follow_up TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'done', 'cancelled')),
            due_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
        CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(stage);
        CREATE INDEX IF NOT EXISTS idx_notes_lead ON notes(lead_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(status, due_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_lead ON tasks(lead_id);
        """)


def rowdict(row):
    return dict(row) if row else None


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def create_task(conn, lead_id, kind, title, due_at):
    """Keep at most one open task of each kind for a lead."""
    existing = conn.execute(
        "SELECT 1 FROM tasks WHERE lead_id = ? AND kind = ? AND status = 'open'",
        (lead_id, kind),
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO tasks (lead_id, kind, title, due_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (lead_id, kind, title, iso(due_at), iso(utc_now())),
        )


def apply_workflow(conn, lead_id, previous, current):
    """Create and resolve tasks when a lead advances through the funnel."""
    now = utc_now()
    terminal = current["status"] in ("Выигран", "Проигран") or current["stage"] in ("Успешно", "Отказ")
    if terminal:
        conn.execute(
            "UPDATE tasks SET status = 'cancelled', completed_at = ? WHERE lead_id = ? AND status = 'open'",
            (iso(now), lead_id),
        )
        return
    if previous is None:
        create_task(conn, lead_id, "first_contact", "Связаться с клиентом", now + timedelta(minutes=15))
    if current["status"] == "Квалифицирован" and (previous is None or previous["status"] != "Квалифицирован"):
        create_task(conn, lead_id, "proposal", "Подготовить предложение", now + timedelta(days=2))
    if current["stage"] in ("Предложение", "Переговоры") and (previous is None or previous["stage"] != current["stage"]):
        create_task(conn, lead_id, "follow_up", "Уточнить решение по предложению", now + timedelta(days=2))


def clean_payload(raw, partial=False):
    if not isinstance(raw, dict):
        return None, "Ожидается объект JSON"
    payload = {}
    for key in FIELDS:
        if key not in raw:
            continue
        value = raw[key]
        if key in ("amount", "probability", "satisfaction"):
            if value in (None, "") and key == "satisfaction":
                payload[key] = None
                continue
            try:
                value = float(value)
            except (ValueError, TypeError):
                return None, f"Поле {key}: требуется число"
            if key == "probability":
                if not value.is_integer() or not 0 <= value <= 100:
                    return None, "Вероятность должна быть целым числом от 0 до 100"
                value = int(value)
            elif key == "amount" and value < 0:
                return None, "Сумма не может быть отрицательной"
            elif key == "satisfaction" and not 0 <= value <= 10:
                return None, "Оценка должна быть от 0 до 10"
        else:
            value = str(value or "").strip()[:250]
        payload[key] = value
    if not partial and not payload.get("name"):
        return None, "Укажите имя клиента"
    if "name" in payload and not payload["name"]:
        return None, "Имя клиента не может быть пустым"
    if "status" in payload and payload["status"] not in STATUSES:
        return None, "Недопустимый статус"
    if "stage" in payload and payload["stage"] not in STAGES:
        return None, "Недопустимый этап сделки"
    for key in ("close_date", "follow_up"):
        if payload.get(key):
            try:
                date.fromisoformat(payload[key])
            except ValueError:
                return None, f"Поле {key}: требуется дата YYYY-MM-DD"
    return payload, None


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/leads")
def list_leads():
    search = request.args.get("search", "").strip()[:100]
    status = request.args.get("status", "").strip()
    stage = request.args.get("stage", "").strip()
    clauses, args = [], []
    if search:
        clauses.append("(name LIKE ? OR company LIKE ? OR email LIKE ? OR phone LIKE ?)")
        args.extend([f"%{search}%"] * 4)
    if status:
        clauses.append("status = ?")
        args.append(status)
    if stage:
        clauses.append("stage = ?")
        args.append(stage)
    sql = "SELECT * FROM leads" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY updated_at DESC, id DESC"
    with db() as conn:
        rows = conn.execute(sql, args).fetchall()
    return jsonify([rowdict(row) for row in rows])


@app.post("/api/leads")
def create_lead():
    payload, error = clean_payload(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400
    keys = list(payload)
    with db() as conn:
        cur = conn.execute(
            f"INSERT INTO leads ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
            [payload[key] for key in keys],
        )
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (cur.lastrowid,)).fetchone()
        apply_workflow(conn, cur.lastrowid, None, row)
    return jsonify(rowdict(row)), 201


@app.get("/api/leads/<int:lead_id>")
def get_lead(lead_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        notes = conn.execute("SELECT * FROM notes WHERE lead_id = ? ORDER BY id DESC", (lead_id,)).fetchall()
    if not row:
        return jsonify(error="Клиент не найден"), 404
    result = rowdict(row)
    result["notes"] = [rowdict(note) for note in notes]
    return jsonify(result)


@app.put("/api/leads/<int:lead_id>")
def update_lead(lead_id):
    payload, error = clean_payload(request.get_json(silent=True), partial=True)
    if error:
        return jsonify(error=error), 400
    if not payload:
        return jsonify(error="Нет полей для изменения"), 400
    assignments = ", ".join(f"{key} = ?" for key in payload)
    with db() as conn:
        previous = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not previous:
            return jsonify(error="Клиент не найден"), 404
        cur = conn.execute(
            f"UPDATE leads SET {assignments}, updated_at = datetime('now') WHERE id = ?",
            [*payload.values(), lead_id],
        )
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        apply_workflow(conn, lead_id, previous, row)
    return jsonify(rowdict(row))


@app.delete("/api/leads/<int:lead_id>")
def delete_lead(lead_id):
    with db() as conn:
        cur = conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    return ("", 204) if cur.rowcount else (jsonify(error="Клиент не найден"), 404)


@app.post("/api/leads/<int:lead_id>/notes")
def add_note(lead_id):
    raw = request.get_json(silent=True) or {}
    body = str(raw.get("body") or "").strip()[:2000]
    if not body:
        return jsonify(error="Введите текст заметки"), 400
    with db() as conn:
        if not conn.execute("SELECT 1 FROM leads WHERE id = ?", (lead_id,)).fetchone():
            return jsonify(error="Клиент не найден"), 404
        cur = conn.execute("INSERT INTO notes (lead_id, body) VALUES (?, ?)", (lead_id, body))
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(rowdict(row)), 201


@app.delete("/api/notes/<int:note_id>")
def delete_note(note_id):
    with db() as conn:
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return ("", 204) if cur.rowcount else (jsonify(error="Заметка не найдена"), 404)


@app.get("/api/tasks")
def list_tasks():
    status = request.args.get("status", "open")
    if status not in ("open", "done", "cancelled", "all"):
        return jsonify(error="Недопустимый статус задачи"), 400
    sql = "SELECT tasks.*, leads.name AS lead_name, leads.company AS company, leads.assignee AS assignee FROM tasks JOIN leads ON leads.id = tasks.lead_id"
    args = []
    if status != "all":
        sql += " WHERE tasks.status = ?"
        args.append(status)
    sql += " ORDER BY CASE tasks.status WHEN 'open' THEN 0 ELSE 1 END, tasks.due_at, tasks.id"
    with db() as conn:
        rows = conn.execute(sql, args).fetchall()
    now = iso(utc_now())
    result = [rowdict(row) for row in rows]
    for task in result:
        task["overdue"] = task["status"] == "open" and task["due_at"] <= now
    return jsonify(result)


@app.patch("/api/tasks/<int:task_id>")
def complete_task(task_id):
    raw = request.get_json(silent=True) or {}
    if raw.get("status") != "done":
        return jsonify(error="Поддерживается только завершение задачи"), 400
    with db() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            return jsonify(error="Задача не найдена"), 404
        if task["status"] != "open":
            return jsonify(error="Задача уже закрыта"), 409
        now = iso(utc_now())
        conn.execute("UPDATE tasks SET status = 'done', completed_at = ? WHERE id = ?", (now, task_id))
        if task["kind"] == "first_contact":
            conn.execute(
                "UPDATE leads SET status = 'В работе', updated_at = datetime('now') WHERE id = ? AND status = 'Новый'",
                (task["lead_id"],),
            )
        result = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return jsonify(rowdict(result))


@app.get("/api/overview")
def overview():
    with db() as conn:
        rows = [rowdict(r) for r in conn.execute("SELECT * FROM leads ORDER BY updated_at DESC, id DESC")]
        task_rows = [rowdict(r) for r in conn.execute("SELECT * FROM tasks WHERE status = 'open'")]
    count = len(rows)
    won = [r for r in rows if r["status"] == "Выигран" or r["stage"] == "Успешно"]
    open_deals = [r for r in rows if r["stage"] not in ("Успешно", "Отказ") and r["status"] not in ("Выигран", "Проигран")]
    by_source = defaultdict(int)
    by_stage = defaultdict(lambda: {"count": 0, "amount": 0})
    by_rep = defaultdict(lambda: {"count": 0, "amount": 0})
    revenue_months = defaultdict(float)
    for row in rows:
        by_source[row["source"] or "Другое"] += 1
        by_stage[row["stage"]]["count"] += 1
        by_stage[row["stage"]]["amount"] += row["amount"]
        if row["assignee"]:
            by_rep[row["assignee"]]["count"] += 1
            if row in won:
                by_rep[row["assignee"]]["amount"] += row["amount"]
        if row in won and row["close_date"]:
            revenue_months[row["close_date"][:7]] += row["amount"]
    scores = [r["satisfaction"] for r in rows if r["satisfaction"] is not None]
    today = date.today().isoformat()
    now = iso(utc_now())
    return jsonify({
        "total": count,
        "qualified": sum(r["status"] == "Квалифицирован" for r in rows),
        "won": len(won),
        "win_rate": round(len(won) / max(1, len(won) + sum(r["status"] == "Проигран" or r["stage"] == "Отказ" for r in rows)) * 100),
        "pipeline": round(sum(r["amount"] for r in open_deals), 2),
        "forecast": round(sum(r["amount"] * r["probability"] / 100 for r in open_deals), 2),
        "revenue": round(sum(r["amount"] for r in won), 2),
        "satisfaction": round(sum(scores) / len(scores), 1) if scores else None,
        "open_cases": sum(r["case_status"].lower() in ("open", "in progress", "открыт", "в работе") for r in rows),
        "due": sum(task["due_at"] <= now for task in task_rows) + sum(bool(r["follow_up"]) and r["follow_up"] <= today and r["status"] not in ("Выигран", "Проигран") for r in rows),
        "open_tasks": len(task_rows),
        "by_source": dict(by_source),
        "by_stage": {stage: by_stage[stage] for stage in STAGES},
        "by_rep": dict(by_rep),
        "revenue_months": dict(sorted(revenue_months.items())),
        "top_deals": sorted(rows, key=lambda r: r["amount"], reverse=True)[:5],
        "recent": rows[:6],
    })


@app.get("/api/export.csv")
def export_csv():
    with db() as conn:
        rows = conn.execute("SELECT * FROM leads ORDER BY id").fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", *FIELDS, "created_at", "updated_at"])
    for row in rows:
        writer.writerow([row[key] for key in ["id", *FIELDS, "created_at", "updated_at"]])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=crm-leads.csv"})


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5050")), debug=False)
