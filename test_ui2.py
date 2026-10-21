"""Regression tests for Manager Helper's actual SQLite operations.

Runs against an isolated temporary database, never the user's workspace.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QGuiApplication
import ui2


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [
            patch.object(ui2, "ROOT", self.root),
            patch.object(ui2, "DB", self.root / "workspace.db"),
            patch.object(ui2, "SETTINGS", self.root / "settings.json"),
        ]
        for item in self.patches:
            item.start()
        self.ws = ui2.Workspace()

    def tearDown(self):
        self.ws._ticker.stop()
        self.ws.db.close()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_create_lane_task_and_edit_exactly_once(self):
        board = self.ws.boards()[0]["id"]
        before = len(self.ws.lanes(board))
        self.ws.addLane(board, "Проверка")
        lanes = self.ws.lanes(board)
        self.assertEqual(len(lanes), before + 1)
        lane = next(x for x in lanes if x["name"] == "Проверка")
        self.ws.addTask(lane["id"], "Тест заявки", "Описание", "", "#6fc4ff")
        tasks = self.ws.tasks(lane["id"])
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual(task["title"], "Тест заявки")
        self.ws.saveTask(task["id"], "Обновлённая заявка", "Новое описание", "", "#6fc4ff")
        self.assertEqual(self.ws.task(task["id"])["title"], "Обновлённая заявка")
        self.assertEqual(len(self.ws.tasks(lane["id"])), 1)

    def test_telegram_and_notes(self):
        board = self.ws.boards()[0]["id"]
        lane = self.ws.lanes(board)[0]["id"]
        self.ws.addTask(lane, "Заявка", "", "", "")
        task_id = self.ws.tasks(lane)[0]["id"]
        self.ws.configureTask(task_id, "", "", "", "https://t.me/c/123456789/42")
        self.assertEqual(self.ws.task(task_id)["telegram_url"], "https://t.me/c/123456789/42")
        self.ws.configureTask(task_id, "", "", "", "https://example.com/phishing")
        self.assertEqual(self.ws.task(task_id)["telegram_url"], "https://t.me/c/123456789/42")
        self.ws.addFolder("Документы")
        folder = next(x for x in self.ws.folders() if x["name"] == "Документы")
        self.ws.addNote(folder["id"], "Заметка", "Текст")
        note = self.ws.notes(folder["id"])[0]
        self.ws.saveNote(note["id"], "Заметка 2", "Обновлено")
        self.assertEqual(self.ws.note(note["id"])["body"], "Обновлено")

    def test_backup_and_migration_are_additive(self):
        self.assertTrue((self.root / "backups").is_dir())
        self.ws.addBoard("Существующая")
        self.ws.db.close()
        self.ws._ticker.stop()
        self.ws = ui2.Workspace()
        self.assertIn("Существующая", [x["name"] for x in self.ws.boards()])


if __name__ == "__main__":
    unittest.main()
