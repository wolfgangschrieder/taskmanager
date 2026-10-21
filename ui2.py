"""Manager Helper v1.1 desktop workspace bridge."""
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, QTimer, QUrl, QMetaObject
from PySide6.QtGui import QGuiApplication, QDesktopServices
from PySide6.QtQml import QQmlApplicationEngine

ROOT = Path.home() / ".apex_task_control"
ROOT.mkdir(exist_ok=True)
DB = ROOT / "apex.db"
SETTINGS = ROOT / "settings.json"


class Workspace(QObject):
    changed = Signal()
    alarmRaised = Signal(int, str, str)

    def __init__(self):
        super().__init__()
        self.db = sqlite3.connect(DB)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS boards(id INTEGER PRIMARY KEY,name TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS lanes(id INTEGER PRIMARY KEY,board_id INTEGER NOT NULL,name TEXT NOT NULL,position INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,lane_id INTEGER NOT NULL,title TEXT NOT NULL,body TEXT DEFAULT '',checklist TEXT DEFAULT '[]',due TEXT,reminded INTEGER DEFAULT 0,position INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS folders(id INTEGER PRIMARY KEY,name TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY,folder_id INTEGER NOT NULL,title TEXT NOT NULL,body TEXT DEFAULT '',pinned INTEGER DEFAULT 0);
        """)
        self._backup("before-migration")
        self._migrate()
        self._backup("daily")
        self._pending_alarm = None
        self._ticker = QTimer(self)
        self._ticker.timeout.connect(self.check_alarms)
        self._ticker.start(15000)
        QTimer.singleShot(1200, self.check_alarms)

    def _migrate(self):
        for table in ("boards", "lanes", "tasks", "folders", "notes"):
            cols = {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")}
            if "color" not in cols:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN color TEXT DEFAULT ''")
        for table in ("lanes", "tasks"):
            cols = {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")}
            for column in ("bg_color", "text_color"):
                if column not in cols:
                    self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT DEFAULT ''")
        cols = {r["name"] for r in self.db.execute("PRAGMA table_info(lanes)")}
        if "timer_enabled" not in cols:
            self.db.execute("ALTER TABLE lanes ADD COLUMN timer_enabled INTEGER DEFAULT 1")
        if "width" not in cols:
            self.db.execute("ALTER TABLE lanes ADD COLUMN width INTEGER DEFAULT 320")
        task_cols = {r["name"] for r in self.db.execute("PRAGMA table_info(tasks)")}
        if "telegram_url" not in task_cols:
            self.db.execute("ALTER TABLE tasks ADD COLUMN telegram_url TEXT DEFAULT ''")
        if not self.db.execute("SELECT 1 FROM boards").fetchone():
            self.db.execute("INSERT INTO boards(name) VALUES('Работа')")
            board_id = self.db.execute("SELECT last_insert_rowid()").fetchone()[0]
            for position, name in enumerate(("Входящие", "В работе", "Ожидание", "Готово")):
                self.db.execute("INSERT INTO lanes(board_id,name,position) VALUES(?,?,?)", (board_id,name,position))
        self.db.commit()

    def _backup(self, kind="daily"):
        backup_dir=ROOT / "backups"
        backup_dir.mkdir(exist_ok=True)
        destination=backup_dir / ("manager-helper-"+kind+"-"+datetime.now().strftime("%Y-%m-%d")+".db")
        if not destination.exists():
            with sqlite3.connect(destination) as target:
                self.db.backup(target)

    def _query(self, sql, args=()):
        return [dict(row) for row in self.db.execute(sql, args)]

    def _write(self, sql, args=()):
        with self.db:
            self.db.execute(sql, args)
        self.changed.emit()

    @Slot(result="QVariantList")
    def boards(self):
        return self._query("SELECT * FROM boards ORDER BY id")

    @Slot(int, result="QVariantList")
    def lanes(self, board_id):
        return self._query("SELECT * FROM lanes WHERE board_id=? ORDER BY position,id", (board_id,))

    @Slot(int, result="QVariantList")
    def tasks(self, lane_id):
        return self._query("SELECT * FROM tasks WHERE lane_id=? ORDER BY position,id", (lane_id,))

    @Slot(int, result="QVariantMap")
    def task(self, task_id):
        result = self._query("SELECT * FROM tasks WHERE id=?", (task_id,))
        return result[0] if result else {}

    @Slot(result="QVariantList")
    def folders(self):
        return self._query("SELECT * FROM folders ORDER BY id")

    @Slot(int, result="QVariantList")
    def notes(self, folder_id):
        return self._query("SELECT * FROM notes WHERE folder_id=? ORDER BY pinned DESC,id DESC", (folder_id,))

    @Slot(int, result="QVariantMap")
    def note(self, note_id):
        result = self._query("SELECT * FROM notes WHERE id=?", (note_id,))
        return result[0] if result else {}

    @Slot(result="QVariantList")
    def schedule(self):
        now = datetime.now()
        cutoff = (now + timedelta(days=3)).isoformat(timespec="minutes")
        return self._query("""
            SELECT tasks.*, lanes.name AS lane_name, boards.name AS board_name
            FROM tasks JOIN lanes ON tasks.lane_id=lanes.id
            JOIN boards ON lanes.board_id=boards.id
            WHERE tasks.due IS NOT NULL AND tasks.due<=?
            AND lanes.timer_enabled=1 AND tasks.reminded=0
            ORDER BY tasks.due,tasks.id
        """, (cutoff,))

    @Slot(int, str, str, str, str)
    def saveTask(self, task_id, title, body, due, color):
        title = title.strip()
        if not title:
            return
        if task_id:
            self._write("UPDATE tasks SET title=?,body=?,due=?,color=?,reminded=0 WHERE id=?",
                        (title,body,due or None,color,task_id))

    @Slot(int, str, str, str, str)
    def addTask(self, lane_id, title, body, due, color):
        if title.strip():
            self._write("INSERT INTO tasks(lane_id,title,body,due,color) VALUES(?,?,?,?,?)",
                        (lane_id,title.strip(),body,due or None,color))

    @Slot(int, str, str, str, int)
    def styleLane(self, lane_id, background, foreground, accent, width):
        self._write("UPDATE lanes SET bg_color=?,text_color=?,color=?,width=? WHERE id=?",
                    (background,foreground,accent,max(240,min(720,width)),lane_id))

    @Slot(int, str, str, str)
    def styleTask(self, task_id, background, foreground, accent):
        self._write("UPDATE tasks SET bg_color=?,text_color=?,color=? WHERE id=?",
                    (background,foreground,accent,task_id))

    @Slot(int, str, str, str, str)
    def configureTask(self, task_id, background, foreground, accent, telegram_url):
        """Save appearance and optional Telegram deep link for a task."""
        telegram_url = telegram_url.strip()
        if telegram_url:
            url = QUrl.fromUserInput(telegram_url)
            scheme = url.scheme().lower()
            host = url.host().lower()
            if not ((scheme == "https" and host in ("t.me", "telegram.me", "telegram.dog"))
                    or (scheme == "tg" and url.isValid())):
                return
            telegram_url = url.toString()
        self._write("UPDATE tasks SET bg_color=?,text_color=?,color=?,telegram_url=? WHERE id=?",
                    (background,foreground,accent,telegram_url,task_id))

    @Slot(str, result=bool)
    def openTelegram(self, raw_url):
        """Open only Telegram links with the Windows default protocol handler/browser."""
        url = QUrl.fromUserInput(raw_url.strip())
        scheme, host = url.scheme().lower(), url.host().lower()
        if not ((scheme == "https" and host in ("t.me", "telegram.me", "telegram.dog"))
                or (scheme == "tg" and url.isValid())):
            return False
        return QDesktopServices.openUrl(url)

    @Slot(int, bool)
    def timerLane(self, lane_id, enabled):
        self._write("UPDATE lanes SET timer_enabled=? WHERE id=?", (int(enabled),lane_id))

    @Slot(int, str)
    def renameLane(self, lane_id, name):
        if name.strip():
            self._write("UPDATE lanes SET name=? WHERE id=?", (name.strip(),lane_id))

    @Slot(int, str)
    def renameBoard(self, board_id, name):
        if name.strip():
            self._write("UPDATE boards SET name=? WHERE id=?", (name.strip(),board_id))

    @Slot(int, str)
    def addLane(self, board_id, name):
        if name.strip():
            self._write("INSERT INTO lanes(board_id,name,position) VALUES(?,?,COALESCE((SELECT MAX(position)+1 FROM lanes WHERE board_id=?),0))",
                        (board_id,name.strip(),board_id))

    @Slot(str)
    def addBoard(self, name):
        if name.strip():
            self._write("INSERT INTO boards(name) VALUES(?)", (name.strip(),))

    @Slot(int)
    def deleteTask(self, task_id):
        self._write("DELETE FROM tasks WHERE id=?", (task_id,))

    @Slot(str)
    def addFolder(self, name):
        if name.strip():
            self._write("INSERT INTO folders(name) VALUES(?)", (name.strip(),))

    @Slot(int, str)
    def renameFolder(self, folder_id, name):
        if name.strip():
            self._write("UPDATE folders SET name=? WHERE id=?", (name.strip(),folder_id))

    @Slot(int, str, str)
    def addNote(self, folder_id, title, body):
        self._write("INSERT INTO notes(folder_id,title,body) VALUES(?,?,?)", (folder_id,title or "Новая запись",body))

    @Slot(int, str, str)
    def saveNote(self, note_id, title, body):
        self._write("UPDATE notes SET title=?,body=? WHERE id=?", (title or "Без названия",body,note_id))

    @Slot(int)
    def deleteNote(self, note_id):
        self._write("DELETE FROM notes WHERE id=?", (note_id,))

    @Slot(int)
    def deleteFolder(self, folder_id):
        with self.db:
            self.db.execute("DELETE FROM notes WHERE folder_id=?", (folder_id,))
            self.db.execute("DELETE FROM folders WHERE id=?", (folder_id,))
        self.changed.emit()

    @Slot(int, int)
    def moveTask(self, task_id, lane_id):
        self._write("UPDATE tasks SET lane_id=? WHERE id=?", (lane_id,task_id))

    @Slot(result="QVariantMap")
    def appearance(self):
        try:
            data=json.loads(SETTINGS.read_text(encoding="utf-8"))
            return data if isinstance(data,dict) else {}
        except (OSError,ValueError):
            return {}

    @Slot(str, str)
    def saveAppearance(self, background, accent):
        settings=self.appearance()
        settings.update(background=background,accent=accent)
        SETTINGS.write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding="utf-8")
        self.changed.emit()

    @Slot()
    def check_alarms(self):
        if self._pending_alarm is not None:
            return
        now=datetime.now().isoformat(timespec="minutes")
        result=self._query("""
            SELECT tasks.* FROM tasks JOIN lanes ON tasks.lane_id=lanes.id
            WHERE tasks.due IS NOT NULL AND tasks.due<=? AND tasks.reminded=0
            AND lanes.timer_enabled=1 ORDER BY tasks.due,tasks.id LIMIT 1
        """, (now,))
        if result:
            task=result[0]
            self._pending_alarm=task["id"]
            self.alarmRaised.emit(task["id"],task["title"],task["due"])

    @Slot(int, str)
    def resolveAlarm(self, task_id, action):
        if task_id != self._pending_alarm:
            return
        if action=="done":
            self._write("UPDATE tasks SET reminded=1 WHERE id=?", (task_id,))
        elif action=="snooze":
            due=(datetime.now()+timedelta(minutes=15)).isoformat(timespec="minutes")
            self._write("UPDATE tasks SET due=?,reminded=0 WHERE id=?", (due,task_id))
        elif action=="open":
            # Opening the editor does not mark the task as completed.
            pass
        self._pending_alarm=None
        if action!="open":
            QTimer.singleShot(1000,self.check_alarms)


def main():
    app=QGuiApplication([])
    engine=QQmlApplicationEngine()
    workspace=Workspace()
    engine.rootContext().setContextProperty("workspace",workspace)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name("ui2.qml"))))
    if not engine.rootObjects():
        raise RuntimeError("Unable to load ui2.qml")
    if os.environ.get("APEX_SMOKE_TEST") == "1":
        def smoke():
            try:
                board_id=workspace.boards()[0]["id"]
                before=len(workspace.lanes(board_id))
                if not QMetaObject.invokeMethod(engine.rootObjects()[0], "smokeCrud"):
                    raise RuntimeError("QML smokeCrud method unavailable")
                lanes=workspace.lanes(board_id)
                if len(lanes) != before + 1:
                    raise RuntimeError(f"Expected one new lane, got {len(lanes)-before}")
                if len(workspace.tasks(lanes[-1]["id"])) != 1:
                    raise RuntimeError("Task dialog did not persist exactly one task")
                print("QML CRUD SMOKE PASSED: one lane and one task", flush=True)
            except Exception as exc:
                print(f"QML CRUD SMOKE FAILED: {exc}", flush=True)
                app.exit(2)
                return
            app.quit()
        QTimer.singleShot(500, smoke)
    screenshot_path=os.environ.get("MANAGER_HELPER_SCREENSHOT")
    if screenshot_path:
        def capture():
            window=engine.rootObjects()[0]
            image=app.primaryScreen().grabWindow(window.winId())
            if image.isNull() or not image.save(screenshot_path):
                print("WARNING: screenshot unavailable on this Qt platform", flush=True)
        QTimer.singleShot(300, capture)
    raise SystemExit(app.exec())


if __name__=="__main__":
    main()
