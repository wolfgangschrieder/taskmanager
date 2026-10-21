"""Regression tests for Manager Helper's actual SQLite operations.

Runs against an isolated temporary database, never the user's workspace.
"""
import os
import json
import sqlite3
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

    def test_delete_task_only_removes_selected_task(self):
        board = self.ws.boards()[0]["id"]
        lane = self.ws.lanes(board)[0]["id"]
        self.ws.addTask(lane, "Оставить", "", "", "")
        self.ws.addTask(lane, "Удалить", "", "", "")
        tasks = self.ws.tasks(lane)
        target = next(task for task in tasks if task["title"] == "Удалить")
        self.ws.deleteTask(target["id"])
        remaining = self.ws.tasks(lane)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["title"], "Оставить")

    def test_delete_empty_column_preserves_tasks(self):
        board = self.ws.boards()[0]["id"]
        self.ws.addLane(board, "Лишняя")
        lane = next(x for x in self.ws.lanes(board) if x["name"] == "Лишняя")
        self.assertTrue(self.ws.deleteEmptyLane(lane["id"]))
        self.ws.addLane(board, "С задачей")
        lane = next(x for x in self.ws.lanes(board) if x["name"] == "С задачей")
        self.ws.addTask(lane["id"], "Не удалять", "", "", "")
        self.assertFalse(self.ws.deleteEmptyLane(lane["id"]))
        self.assertEqual(len(self.ws.tasks(lane["id"])), 1)

    def test_confirmed_column_deletion_removes_its_tasks_only(self):
        board = self.ws.boards()[0]["id"]
        self.ws.addLane(board, "Удаляемая")
        self.ws.addLane(board, "Остаётся")
        lanes = {x["name"]: x["id"] for x in self.ws.lanes(board)}
        self.ws.addTask(lanes["Удаляемая"], "Уходит вместе с колонкой", "", "", "")
        self.ws.addTask(lanes["Остаётся"], "Сохранить", "", "", "")
        self.assertEqual(self.ws.laneTaskCount(lanes["Удаляемая"]), 1)
        self.assertTrue(self.ws.deleteLane(lanes["Удаляемая"]))
        self.assertNotIn("Удаляемая", [x["name"] for x in self.ws.lanes(board)])
        self.assertEqual([x["title"] for x in self.ws.tasks(lanes["Остаётся"])], ["Сохранить"])

    def test_delete_folder_removes_only_its_own_notes(self):
        self.ws.addFolder("Delete me")
        self.ws.addFolder("Keep me")
        folders = {f["name"]: f["id"] for f in self.ws.folders()}
        doomed = folders["Delete me"]
        retained = folders["Keep me"]
        self.ws.addNote(doomed, "Temporary", "Remove")
        self.ws.addNote(retained, "Important", "Preserve")
        self.ws.deleteFolder(doomed)
        self.assertNotIn(doomed, [f["id"] for f in self.ws.folders()])
        self.assertEqual(self.ws.notes(doomed), [])
        self.assertEqual(self.ws.notes(retained)[0]["body"], "Preserve")

    def test_new_columns_inherit_saved_defaults(self):
        board = self.ws.boards()[0]["id"]
        self.ws.saveLaneDefaults("#223344", "#ddeeff", "#55c5ad", 530, False)
        self.ws.addLane(board, "Настроенная колонка")
        lane = next(x for x in self.ws.lanes(board) if x["name"] == "Настроенная колонка")
        self.assertEqual(lane["bg_color"], "#223344")
        self.assertEqual(lane["text_color"], "#ddeeff")
        self.assertEqual(lane["color"], "#55c5ad")
        self.assertEqual(lane["width"], 530)
        self.assertEqual(lane["timer_enabled"], 0)
        self.ws.saveLaneDefaults("#192535", "#ecf2fb", "#79b7e8", 320, True)
        unchanged = next(x for x in self.ws.lanes(board) if x["id"] == lane["id"])
        self.assertEqual(unchanged["width"], 530)

    def test_settings_write_is_atomic_on_replace_failure(self):
        self.ws.saveAppearance("#112233", "#445566")
        original = ui2.SETTINGS.read_bytes()
        with patch.object(ui2.os, "replace", side_effect=OSError("simulated failure")):
            with self.assertRaises(OSError):
                self.ws.saveLaneDefaults("#192535", "#ecf2fb", "#79b7e8", 450, True)
        self.assertEqual(ui2.SETTINGS.read_bytes(), original)
        self.assertEqual(list(self.root.glob(".settings-*.tmp")), [])
        self.ws.saveLaneDefaults("#192535", "#ecf2fb", "#79b7e8", 450, True)
        self.assertEqual(json.loads(ui2.SETTINGS.read_text(encoding="utf-8"))["lane_defaults"]["width"], 450)

    def test_lane_width_persists(self):
        board = self.ws.boards()[0]["id"]
        lane = self.ws.lanes(board)[0]["id"]
        self.ws.styleLane(lane, "#192535", "#ecf2fb", "#79b7e8", 570)
        saved = next(x for x in self.ws.lanes(board) if x["id"] == lane)
        self.assertEqual(saved["width"], 570)

    def test_drag_order_and_cross_column_moves_persist(self):
        board=self.ws.boards()[0]["id"]
        self.ws.addLane(board,"Drag A")
        self.ws.addLane(board,"Drag B")
        lanes=self.ws.lanes(board)
        a=next(x["id"] for x in lanes if x["name"]=="Drag A")
        b=next(x["id"] for x in lanes if x["name"]=="Drag B")
        self.assertTrue(self.ws.reorderLane(b,a))
        ids=[x["id"] for x in self.ws.lanes(board)]
        self.assertLess(ids.index(b),ids.index(a))
        self.ws.addTask(a,"First","","","")
        self.ws.addTask(a,"Second","","","")
        tasks=self.ws.tasks(a)
        first=next(x["id"] for x in tasks if x["title"]=="First")
        second=next(x["id"] for x in tasks if x["title"]=="Second")
        self.assertTrue(self.ws.dropTask(second,a,first))
        self.assertEqual([x["id"] for x in self.ws.tasks(a)],[second,first])
        self.assertTrue(self.ws.dropTask(second,b,0))
        self.assertEqual([x["id"] for x in self.ws.tasks(a)],[first])
        self.assertEqual([x["id"] for x in self.ws.tasks(b)],[second])
        self.assertFalse(self.ws.dropTask(first,b,first))
        self.ws.resizeLane(b,580)
        self.assertEqual(next(x["width"] for x in self.ws.lanes(board) if x["id"]==b),580)

    def test_cross_board_drop_preserves_task_details(self):
        original_board = self.ws.boards()[0]["id"]
        source_lane = self.ws.lanes(original_board)[0]["id"]
        self.ws.addBoard("Separate board")
        second_board = next(b["id"] for b in self.ws.boards() if b["name"] == "Separate board")
        self.ws.addLane(second_board, "Destination")
        target_lane = self.ws.lanes(second_board)[0]["id"]
        self.ws.addTask(source_lane, "Must stay", "Important", "", "")
        task = next(t for t in self.ws.tasks(source_lane) if t["title"] == "Must stay")
        self.assertTrue(self.ws.dropTask(task["id"], target_lane, 0))
        self.assertEqual(self.ws.task(task["id"])["lane_id"], target_lane)
        self.assertEqual(self.ws.task(task["id"])["body"], "Important")
        self.assertEqual(self.ws.tasks(source_lane), [])

    def test_overdue_marker_and_invalid_destination(self):
        board = self.ws.boards()[0]["id"]
        lane = self.ws.lanes(board)[0]["id"]
        self.ws.addTask(lane, "Old", "", "2020-01-01T10:00", "")
        task_id = self.ws.tasks(lane)[0]["id"]
        self.assertTrue(self.ws.isOverdue("2020-01-01T10:00"))
        self.assertFalse(self.ws.isOverdue(""))
        self.assertFalse(self.ws.isOverdue("not-a-date"))
        self.assertFalse(self.ws.moveTaskToLane(task_id, 999999))
        self.assertEqual(self.ws.task(task_id)["lane_id"], lane)

    def test_new_tasks_append_after_reordering(self):
        board = self.ws.boards()[0]["id"]
        lane = self.ws.lanes(board)[0]["id"]
        for title in ("First", "Second"):
            self.ws.addTask(lane, title, "", "", "")
        first, second = [task["id"] for task in self.ws.tasks(lane)]
        self.assertTrue(self.ws.dropTask(second, lane, first))
        self.ws.addTask(lane, "Third", "", "", "")
        self.assertEqual([t["title"] for t in self.ws.tasks(lane)],
                         ["Second", "First", "Third"])

    def test_edit_without_deadline_change_preserves_reminder(self):
        board = self.ws.boards()[0]["id"]
        lane = self.ws.lanes(board)[0]["id"]
        due = "2026-10-22T14:30"
        self.ws.addTask(lane, "Original", "", due, "")
        task_id = self.ws.tasks(lane)[0]["id"]
        self.ws.db.execute("UPDATE tasks SET reminded=1 WHERE id=?", (task_id,))
        self.ws.db.commit()
        self.ws.saveTask(task_id, "Edited", "Changed body", due, "")
        self.assertEqual(self.ws.task(task_id)["reminded"], 1)
        self.ws.saveTask(task_id, "Edited", "Changed body", "2026-10-23T14:30", "")
        self.assertEqual(self.ws.task(task_id)["reminded"], 0)

    def test_schedule_handles_space_and_iso_deadlines(self):
        board = self.ws.boards()[0]["id"]
        lane = self.ws.lanes(board)[0]["id"]
        self.ws.addTask(lane, "Space deadline", "", "2020-01-01 10:00", "")
        self.ws.addTask(lane, "ISO deadline", "", "2020-01-01T11:00", "")
        self.assertEqual([t["title"] for t in self.ws.schedule()],
                         ["Space deadline", "ISO deadline"])
        self.ws.db.execute("UPDATE tasks SET reminded=1 WHERE title='Space deadline'")
        self.ws.db.commit()
        seen = []
        self.ws.alarmRaised.connect(lambda task_id, title, due: seen.append(title))
        self.ws.check_alarms()
        self.assertEqual(seen, ["ISO deadline"])

    def test_oldest_overdue_alarm_wins_across_date_formats(self):
        board = self.ws.boards()[0]["id"]
        lane = self.ws.lanes(board)[0]["id"]
        self.ws.addTask(lane, "Later ISO", "", "2020-01-02T09:00", "")
        self.ws.addTask(lane, "Earlier space", "", "2020-01-01 09:00", "")
        raised = []
        self.ws.alarmRaised.connect(lambda task_id, title, due: raised.append(title))
        self.ws.check_alarms()
        self.assertEqual(raised, ["Earlier space"])

    def test_self_drop_rejected_without_reordering(self):
        board = self.ws.boards()[0]["id"]
        lane = self.ws.lanes(board)[0]["id"]
        self.ws.addTask(lane, "Keep order", "", "", "")
        task = self.ws.tasks(lane)[0]["id"]
        self.assertFalse(self.ws.dropTask(task, lane, task))
        self.assertEqual(self.ws.tasks(lane)[0]["id"], task)

    def test_invalid_due_date_cannot_create_task(self):
        board = self.ws.boards()[0]["id"]
        lane = self.ws.lanes(board)[0]["id"]
        self.assertFalse(self.ws.validDue("2026-13-42 99:99"))
        self.assertTrue(self.ws.validDue("2026-10-21 14:30"))
        self.ws.addTask(lane, "Неверный срок", "", "2026-13-42 99:99", "")
        self.assertEqual(self.ws.tasks(lane), [])

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

    def test_alarm_open_does_not_retrigger_immediately(self):
        board = self.ws.boards()[0]["id"]
        lane = self.ws.lanes(board)[0]["id"]
        self.ws.addTask(lane, "Просроченная", "", "2020-01-01T12:00", "")
        seen = []
        self.ws.alarmRaised.connect(lambda task_id, title, due: seen.append(task_id))
        self.ws.check_alarms()
        self.assertEqual(len(seen), 1)
        self.ws.resolveAlarm(seen[0], "open")
        self.ws.check_alarms()
        self.assertEqual(len(seen), 1)

    def test_backup_contains_saved_data_and_passes_integrity_check(self):
        self.ws.addBoard("Backup proof")
        backup = self.root / "backups" / "manager-helper-manual-2026-10-22.db"
        with patch.object(ui2, "datetime") as clock:
            clock.now.return_value.strftime.return_value = "2026-10-22"
            self.ws._backup("manual")
        self.assertTrue(backup.exists())
        with sqlite3.connect(backup) as snapshot:
            self.assertEqual(snapshot.execute("PRAGMA quick_check").fetchone()[0], "ok")
            self.assertIn("Backup proof", [row[0] for row in snapshot.execute("SELECT name FROM boards")])
        self.assertEqual(list((self.root / "backups").glob(".backup-*.db")), [])

    def test_failed_backup_does_not_publish_incomplete_snapshot(self):
        destination = self.root / "backups" / "manager-helper-failure-2026-10-22.db"
        with patch.object(ui2, "datetime") as clock:
            clock.now.return_value.strftime.return_value = "2026-10-22"
            with patch.object(ui2.os, "replace", side_effect=OSError("simulated")):
                with self.assertRaises(OSError):
                    self.ws._backup("failure")
        self.assertFalse(destination.exists())
        self.assertEqual(list((self.root / "backups").glob(".backup-*.db")), [])

    def test_reopen_preserves_lane_task_order_and_notes(self):
        board = self.ws.boards()[0]["id"]
        first_lane, second_lane = [lane["id"] for lane in self.ws.lanes(board)[:2]]
        self.assertTrue(self.ws.reorderLane(second_lane, first_lane))
        self.ws.addTask(second_lane, "First", "Body 1", "", "")
        self.ws.addTask(second_lane, "Second", "Body 2", "", "")
        first, second = [task["id"] for task in self.ws.tasks(second_lane)]
        self.assertTrue(self.ws.dropTask(second, second_lane, first))
        self.ws.resizeLane(second_lane, 510)
        self.ws.addFolder("Persistent folder")
        folder = next(f["id"] for f in self.ws.folders() if f["name"] == "Persistent folder")
        self.ws.addNote(folder, "Persistent note", "Original")
        note = self.ws.notes(folder)[0]["id"]
        self.ws.saveNote(note, "Persistent note", "Updated")
        self.ws._ticker.stop()
        self.ws.db.close()
        self.ws = ui2.Workspace()
        self.assertEqual(self.ws.lanes(board)[0]["id"], second_lane)
        self.assertEqual(self.ws.lanes(board)[0]["width"], 510)
        self.assertEqual([t["id"] for t in self.ws.tasks(second_lane)], [second, first])
        self.assertEqual(self.ws.note(note)["body"], "Updated")

    def test_backup_and_migration_are_additive(self):
        self.assertTrue((self.root / "backups").is_dir())
        self.ws.addBoard("Существующая")
        self.ws.db.close()
        self.ws._ticker.stop()
        self.ws = ui2.Workspace()
        self.assertIn("Существующая", [x["name"] for x in self.ws.boards()])


if __name__ == "__main__":
    unittest.main()
