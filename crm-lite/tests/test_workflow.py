"""Workflow invariants: task creation, idempotency, completion and closure."""

import tempfile
import unittest
from pathlib import Path

import app as crm


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_path = crm.DB_PATH
        crm.DB_PATH = Path(self.temp.name) / "test.db"
        crm.init_db()
        self.client = crm.app.test_client()

    def tearDown(self):
        crm.DB_PATH = self.original_path
        self.temp.cleanup()

    def create(self):
        response = self.client.post("/api/leads", json={"name": "Тестовый клиент"})
        self.assertEqual(response.status_code, 201)
        return response.json["id"]

    def test_new_lead_creates_first_contact_task(self):
        lead_id = self.create()
        tasks = self.client.get("/api/tasks").json
        self.assertEqual([(t["lead_id"], t["kind"]) for t in tasks], [(lead_id, "first_contact")])

    def test_qualification_creates_proposal_task_once(self):
        lead_id = self.create()
        self.client.put(f"/api/leads/{lead_id}", json={"status": "Квалифицирован"})
        self.client.put(f"/api/leads/{lead_id}", json={"status": "Квалифицирован"})
        tasks = self.client.get("/api/tasks").json
        self.assertEqual([t["kind"] for t in tasks], ["first_contact", "proposal"])

    def test_first_contact_completion_moves_new_lead_to_work(self):
        lead_id = self.create()
        task_id = self.client.get("/api/tasks").json[0]["id"]
        response = self.client.patch(f"/api/tasks/{task_id}", json={"status": "done"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(f"/api/leads/{lead_id}").json["status"], "В работе")
        self.assertEqual(self.client.get("/api/tasks").json, [])

    def test_closed_deal_cancels_open_tasks(self):
        lead_id = self.create()
        self.client.put(f"/api/leads/{lead_id}", json={"stage": "Предложение"})
        self.assertEqual(len(self.client.get("/api/tasks").json), 2)
        self.client.put(f"/api/leads/{lead_id}", json={"status": "Выигран", "stage": "Успешно"})
        self.assertEqual(self.client.get("/api/tasks").json, [])
        self.assertEqual(len(self.client.get("/api/tasks?status=cancelled").json), 2)


if __name__ == "__main__":
    unittest.main()
