"""Manager Helper v1.1 desktop workspace bridge."""
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, QTimer, QUrl, QMetaObject
from PySide6.QtGui import QGuiApplication, QDesktopServices
from PySide6.QtQml import QQmlApplicationEngine

ROOT = (Path(tempfile.gettempdir()) / "manager-helper-packaged-smoke" if os.environ.get("MANAGER_HELPER_SMOKE_TEST") == "1" else Path.home() / ".apex_task_control")
ROOT.mkdir(exist_ok=True)
DB = ROOT / "apex.db"
SETTINGS = ROOT / "settings.json"


class Workspace(QObject):
    changed = Signal()
    alarmRaised = Signal(int, str, str)
    reminderRaised = Signal(int, str, str)

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
        self._suppressed_alarms = {}
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
        if "created_at" not in task_cols:
            # Historical creation timestamps were not recorded. Do not fabricate them.
            self.db.execute("ALTER TABLE tasks ADD COLUMN created_at TEXT")
        if "alert15_sent" not in task_cols:
            self.db.execute("ALTER TABLE tasks ADD COLUMN alert15_sent INTEGER DEFAULT 0")
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
        if destination.exists():
            return
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=backup_dir, prefix=".backup-", suffix=".db", delete=False
            ) as handle:
                temporary = Path(handle.name)
            with sqlite3.connect(temporary) as target:
                self.db.backup(target)
                check = target.execute("PRAGMA quick_check").fetchone()
                if not check or check[0] != "ok":
                    raise sqlite3.DatabaseError("Backup integrity check failed")
            # SQLite backup connections are closed before Windows renames the file.
            os.replace(temporary, destination)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except PermissionError:
                    # Antivirus/indexers can briefly hold a completed temp file on Windows.
                    pass

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
    def siblingLanes(self, lane_id):
        return self._query("""
            SELECT sibling.* FROM lanes sibling
            JOIN lanes origin ON origin.board_id=sibling.board_id
            WHERE origin.id=? ORDER BY sibling.position,sibling.id
        """, (lane_id,))

    @Slot(int, result="QVariantList")
    def tasks(self, lane_id):
        return self._query("SELECT * FROM tasks WHERE lane_id=? ORDER BY position,id", (lane_id,))

    @Slot(str, result="QVariantList")
    def allTasks(self, search):
        """Newest first; ID is the reliable creation sequence for legacy rows."""
        search = search.strip()
        if search:
            pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            return self._query("""
                SELECT tasks.*, lanes.name AS lane_name, boards.name AS board_name
                FROM tasks JOIN lanes ON tasks.lane_id=lanes.id
                JOIN boards ON lanes.board_id=boards.id
                WHERE tasks.title LIKE ? ESCAPE '\\'
                   OR tasks.body LIKE ? ESCAPE '\\'
                   OR tasks.telegram_url LIKE ? ESCAPE '\\'
                ORDER BY tasks.id DESC
            """, (pattern, pattern, pattern))
        return self._query("""
            SELECT tasks.*, lanes.name AS lane_name, boards.name AS board_name
            FROM tasks JOIN lanes ON tasks.lane_id=lanes.id
            JOIN boards ON lanes.board_id=boards.id
            ORDER BY tasks.id DESC
        """)

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
        today = datetime.now().date()
        rows = self._query("""
            SELECT tasks.*, lanes.name AS lane_name, boards.name AS board_name
            FROM tasks JOIN lanes ON tasks.lane_id=lanes.id
            JOIN boards ON lanes.board_id=boards.id
            WHERE tasks.due IS NOT NULL
            AND lanes.timer_enabled=1 AND tasks.reminded=0
            ORDER BY REPLACE(tasks.due, ' ', 'T'),tasks.id
        """)
        grouped = []
        previous_day = None
        for task in rows:
            try:
                due = datetime.strptime(task["due"].replace("T", " "), "%Y-%m-%d %H:%M")
            except (ValueError, AttributeError):
                continue
            day = due.date()
            section = ("overdue" if day < today else day.isoformat())
            if section != previous_day:
                if day < today:
                    heading = "Просроченные"
                elif day == today:
                    heading = "Сегодня"
                elif day == today + timedelta(days=1):
                    heading = "Завтра"
                else:
                    heading = day.strftime("%d/%m/%Y")
                grouped.append({"is_header": True, "heading": heading, "due": ""})
                previous_day = section
            task["is_header"] = False
            task["display_time"] = due.strftime("%H:%M")
            task["display_date"] = due.strftime("%d/%m/%Y")
            grouped.append(task)
        return grouped

    @Slot(str, result=bool)
    def validDue(self, raw):
        value=raw.strip()
        if not value:
            return True
        try:
            datetime.strptime(value.replace("T", " "), "%Y-%m-%d %H:%M")
            return True
        except ValueError:
            return False

    @Slot(int, str, str, str, str)
    def saveTask(self, task_id, title, body, due, color):
        title = title.strip()
        if not title or not self.validDue(due):
            return
        if task_id:
            self._write("""UPDATE tasks SET title=?,body=?,due=?,color=?,
                        reminded=CASE WHEN COALESCE(due, '')=COALESCE(?, '') THEN reminded ELSE 0 END, alert15_sent=CASE WHEN COALESCE(due, '')=COALESCE(?, '') THEN alert15_sent ELSE 0 END
                        WHERE id=?""",
                        (title,body,due or None,color,due or None,due or None,task_id))

    @Slot(int, str, str, str, str)
    def addTask(self, lane_id, title, body, due, color):
        if title.strip() and self.validDue(due):
            self._write("""INSERT INTO tasks(lane_id,title,body,due,color,position,created_at)
                        VALUES(?,?,?,?,?,COALESCE((SELECT MAX(position)+1 FROM tasks WHERE lane_id=?),0),?)""",
                        (lane_id,title.strip(),body,due or None,color,lane_id,datetime.now().isoformat(timespec="seconds")))

    @Slot(int, str, str, str, str, str)
    def saveTaskDetails(self, task_id, title, body, due, color, telegram_url):
        if not title.strip() or not self.validDue(due):
            return
        normalized = self._telegram_url(telegram_url)
        if normalized is None:
            return
        self._write("""UPDATE tasks SET title=?,body=?,due=?,color=?,telegram_url=?,
                     reminded=CASE WHEN COALESCE(due, '')=COALESCE(?, '') THEN reminded ELSE 0 END,
                     alert15_sent=CASE WHEN COALESCE(due, '')=COALESCE(?, '') THEN alert15_sent ELSE 0 END
                     WHERE id=?""",
                    (title.strip(), body, due or None, color, normalized, due or None, due or None, task_id))

    @Slot(int, str, str, str, str, str)
    def addTaskDetails(self, lane_id, title, body, due, color, telegram_url):
        if not title.strip() or not self.validDue(due):
            return
        normalized = self._telegram_url(telegram_url)
        if normalized is None:
            return
        self._write("""INSERT INTO tasks(lane_id,title,body,due,color,telegram_url,position,created_at)
                     VALUES(?,?,?,?,?,?,COALESCE((SELECT MAX(position)+1 FROM tasks WHERE lane_id=?),0),?)""",
                    (lane_id, title.strip(), body, due or None, color, normalized, lane_id, datetime.now().isoformat(timespec="seconds")))

    def _telegram_url(self, raw):
        raw = raw.strip()
        if not raw:
            return ""
        url = QUrl.fromUserInput(raw)
        if (url.scheme().lower() == "https" and url.host().lower() in
                ("t.me", "telegram.me", "telegram.dog")) or (url.scheme().lower() == "tg" and url.isValid()):
            return url.toString()
        return None

    @Slot(str, result=bool)
    def validTelegram(self, raw):
        return self._telegram_url(raw) is not None

    @Slot(result=str)
    def defaultTaskDue(self):
        return (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")

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
        """Prefer Telegram Desktop's registered tg:// handler; fall back to HTTPS."""
        normalized = self._telegram_url(raw_url)
        if not normalized:
            return False
        url = QUrl(normalized)
        if url.scheme().lower() == "tg":
            return QDesktopServices.openUrl(url)
        path = url.path().strip("/")
        if path:
            if path.startswith("+") or path.startswith("joinchat/"):
                token = path[1:] if path.startswith("+") else path.split("/", 1)[1]
                deep = QUrl("tg://join?invite=" + token)
            elif path.startswith("c/"):
                parts = path.split("/")
                deep = QUrl("tg://privatepost?channel=" + parts[1] +
                            ("&post=" + parts[2] if len(parts) > 2 else "")) if len(parts) >= 3 else None
            else:
                parts = path.split("/")
                deep = QUrl("tg://resolve?domain=" + parts[0] +
                            ("&post=" + parts[1] if len(parts) > 1 and parts[1].isdigit() else ""))
            if deep is not None and QDesktopServices.openUrl(deep):
                return True
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
        if not name.strip():
            return
        defaults=self.appearance().get("lane_defaults", {})
        bg=defaults.get("background", "#192535")
        fg=defaults.get("foreground", "#ecf2fb")
        accent=defaults.get("accent", "#79b7e8")
        width=max(250,min(720,int(defaults.get("width",320))))
        timer=int(bool(defaults.get("timer",True)))
        self._write("""INSERT INTO lanes(board_id,name,position,bg_color,text_color,color,width,timer_enabled)
            VALUES(?,?,COALESCE((SELECT MAX(position)+1 FROM lanes WHERE board_id=?),0),?,?,?,?,?)""",
            (board_id,name.strip(),board_id,bg,fg,accent,width,timer))

    @Slot(int, result=int)
    def laneTaskCount(self, lane_id):
        row=self.db.execute("SELECT COUNT(*) FROM tasks WHERE lane_id=?", (lane_id,)).fetchone()
        return int(row[0])

    @Slot(int, result=bool)
    def deleteLane(self, lane_id):
        """Delete a column and its tasks only after the UI confirmation."""
        with self.db:
            self.db.execute("DELETE FROM tasks WHERE lane_id=?", (lane_id,))
            cursor=self.db.execute("DELETE FROM lanes WHERE id=?", (lane_id,))
        self.changed.emit()
        return cursor.rowcount > 0

    @Slot(int, result=bool)
    def deleteEmptyLane(self, lane_id):
        """Retained for compatibility with earlier previews."""
        if self.laneTaskCount(lane_id):
            return False
        return self.deleteLane(lane_id)

    @Slot(str)
    def addBoard(self, name):
        if name.strip():
            self._write("INSERT INTO boards(name) VALUES(?)", (name.strip(),))

    @Slot(int, result=int)
    def boardTaskCount(self, board_id):
        row = self.db.execute("""SELECT COUNT(*) FROM tasks
            JOIN lanes ON tasks.lane_id=lanes.id WHERE lanes.board_id=?""",
            (board_id,)).fetchone()
        return int(row[0])

    @Slot(int, result=bool)
    def deleteBoard(self, board_id):
        """Remove the board and its lanes/tasks in one transaction."""
        with self.db:
            self.db.execute("""DELETE FROM tasks WHERE lane_id IN
                (SELECT id FROM lanes WHERE board_id=?)""", (board_id,))
            self.db.execute("DELETE FROM lanes WHERE board_id=?", (board_id,))
            cursor = self.db.execute("DELETE FROM boards WHERE id=?", (board_id,))
        if cursor.rowcount:
            self.changed.emit()
            return True
        return False

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

    @Slot(int, str, str, result=int)
    def addNote(self, folder_id, title, body):
        with self.db:
            cursor=self.db.execute("INSERT INTO notes(folder_id,title,body) VALUES(?,?,?)",
                                   (folder_id,title or "Новая запись",body))
            note_id=cursor.lastrowid
        self.changed.emit()
        return note_id

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

    @Slot(int, int, result=bool)
    def reorderLane(self, source_id, target_id):
        """Move a lane before the target lane, preserving all task records."""
        source=self.db.execute("SELECT board_id FROM lanes WHERE id=?", (source_id,)).fetchone()
        target=self.db.execute("SELECT board_id FROM lanes WHERE id=?", (target_id,)).fetchone()
        if not source or not target or source[0] != target[0] or source_id == target_id:
            return False
        ids=[row[0] for row in self.db.execute(
            "SELECT id FROM lanes WHERE board_id=? ORDER BY position,id", (source[0],))]
        ids.remove(source_id)
        ids.insert(ids.index(target_id), source_id)
        with self.db:
            for pos, lane_id in enumerate(ids):
                self.db.execute("UPDATE lanes SET position=? WHERE id=?", (pos,lane_id))
        self.changed.emit()
        return True

    @Slot(int, int, int, result=bool)
    def dropTask(self, task_id, target_lane_id, before_task_id):
        """Move a task to another column and/or reorder within a column."""
        row=self.db.execute("SELECT lane_id FROM tasks WHERE id=?", (task_id,)).fetchone()
        target=self.db.execute("SELECT board_id FROM lanes WHERE id=?", (target_lane_id,)).fetchone()
        if not row or not target:
            return False
        if before_task_id == task_id:
            return False
        if before_task_id:
            before=self.db.execute("SELECT lane_id FROM tasks WHERE id=?", (before_task_id,)).fetchone()
            if not before or before[0] != target_lane_id or before_task_id == task_id:
                return False
        source_lane_id=row[0]
        with self.db:
            self.db.execute("UPDATE tasks SET lane_id=? WHERE id=?", (target_lane_id,task_id))
            for lane_id in set((source_lane_id,target_lane_id)):
                ids=[r[0] for r in self.db.execute(
                    "SELECT id FROM tasks WHERE lane_id=? ORDER BY position,id", (lane_id,))]
                if lane_id == target_lane_id:
                    ids.remove(task_id)
                    if before_task_id:
                        ids.insert(ids.index(before_task_id),task_id)
                    else:
                        ids.append(task_id)
                for pos, task in enumerate(ids):
                    self.db.execute("UPDATE tasks SET position=? WHERE id=?", (pos,task))
        self.changed.emit()
        return True

    @Slot(int, result=bool)
    def completeTask(self, task_id):
        with self.db:
            result = self.db.execute(
                "UPDATE tasks SET due=NULL,reminded=1,alert15_sent=1 WHERE id=?", (task_id,))
        if result.rowcount:
            self.changed.emit()
        return bool(result.rowcount)

    @Slot(int, result=bool)
    def duplicateTask(self, task_id):
        task = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if task is None:
            return False
        with self.db:
            self.db.execute("""
                INSERT INTO tasks(lane_id,title,body,checklist,due,reminded,position,
                    color,bg_color,text_color,telegram_url,alert15_sent,created_at)
                VALUES(?,?,?,?,?,0,?,?,?,?,?,0,?)
            """, (task["lane_id"], task["title"], task["body"], task["checklist"],
                  task["due"], (self.db.execute(
                      "SELECT COALESCE(MAX(position)+1,0) FROM tasks WHERE lane_id=?",
                      (task["lane_id"],)).fetchone()[0]), task["color"], task["bg_color"],
                  task["text_color"], task["telegram_url"], datetime.now().isoformat(timespec="seconds")))
        self.changed.emit()
        return True

    @Slot(int, int, result=bool)
    def moveTaskToLane(self, task_id, lane_id):
        """Explicit destination selector, including a different board."""
        return self.dropTask(task_id, lane_id, 0)

    @Slot(str, result=bool)
    def isOverdue(self, raw_due):
        if not raw_due:
            return False
        try:
            due = datetime.strptime(raw_due.replace("T", " "), "%Y-%m-%d %H:%M")
            return due < datetime.now()
        except (ValueError, AttributeError):
            return False

    @Slot(int, int)
    def resizeLane(self, lane_id, width):
        self._write("UPDATE lanes SET width=? WHERE id=?",
                    (max(250,min(720,int(width))),lane_id))

    @Slot(result="QVariantMap")
    def appearance(self):
        try:
            data=json.loads(SETTINGS.read_text(encoding="utf-8"))
            return data if isinstance(data,dict) else {}
        except (OSError,ValueError):
            return {}

    def _save_settings(self, settings):
        """Atomically replace settings so an interrupted write cannot truncate them."""
        payload = json.dumps(settings, ensure_ascii=False, indent=2)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=SETTINGS.parent,
                prefix=".settings-", suffix=".tmp", delete=False
            ) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, SETTINGS)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @Slot(str, str)
    def saveAppearance(self, background, accent):
        settings=self.appearance()
        settings.update(background=background,accent=accent)
        self._save_settings(settings)
        self.changed.emit()

    @Slot(str, str, str, int, bool)
    def saveLaneDefaults(self, background, foreground, accent, width, timer):
        import re
        colors=(background,foreground,accent)
        if not all(re.fullmatch(r"#[0-9a-fA-F]{6}", value or "") for value in colors):
            return
        settings=self.appearance()
        settings["lane_defaults"]={
            "background":background,"foreground":foreground,"accent":accent,
            "width":max(250,min(720,int(width))),"timer":bool(timer)
        }
        self._save_settings(settings)
        self.changed.emit()

    @Slot()
    def check_alarms(self):
        if self._pending_alarm is not None:
            return
        now = datetime.now()
        now_iso = now.isoformat(timespec="minutes")
        pre_iso = (now + timedelta(minutes=15)).isoformat(timespec="minutes")
        # Due alarms take precedence over advance reminders.
        due = self._query("""
            SELECT tasks.* FROM tasks JOIN lanes ON tasks.lane_id=lanes.id
            WHERE tasks.due IS NOT NULL AND REPLACE(tasks.due,' ','T')<=?
            AND tasks.reminded=0 AND lanes.timer_enabled=1
            ORDER BY REPLACE(tasks.due,' ','T'),tasks.id LIMIT 100
        """, (now_iso,))
        for task in due:
            if self._suppressed_alarms.get(task["id"], datetime.min) > now:
                continue
            self._pending_alarm = task["id"]
            self.alarmRaised.emit(task["id"], task["title"], task["due"])
            return
        upcoming = self._query("""
            SELECT tasks.* FROM tasks JOIN lanes ON tasks.lane_id=lanes.id
            WHERE tasks.due IS NOT NULL
            AND REPLACE(tasks.due,' ','T')>? AND REPLACE(tasks.due,' ','T')<=?
            AND tasks.reminded=0 AND tasks.alert15_sent=0 AND lanes.timer_enabled=1
            ORDER BY REPLACE(tasks.due,' ','T'),tasks.id LIMIT 1
        """, (now_iso, pre_iso))
        if upcoming:
            task = upcoming[0]
            self._write("UPDATE tasks SET alert15_sent=1 WHERE id=?", (task["id"],))
            self._pending_alarm = task["id"]
            self.reminderRaised.emit(task["id"], task["title"], task["due"])

    @Slot(int, str)
    def resolveAlarm(self, task_id, action):
        if task_id != self._pending_alarm:
            return
        if action == "done":
            self.completeTask(task_id)
        elif action == "snooze":
            due = (datetime.now() + timedelta(minutes=15)).isoformat(timespec="minutes")
            self._write("UPDATE tasks SET due=?,reminded=0,alert15_sent=1 WHERE id=?",
                        (due, task_id))
        elif action == "open":
            self._suppressed_alarms[task_id] = datetime.now() + timedelta(minutes=5)
        self._pending_alarm = None
        if action != "open":
            QTimer.singleShot(1000, self.check_alarms)


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
    if os.environ.get("MANAGER_HELPER_SMOKE_TEST") == "1":
        # Verify QtCore, QtQml, QML plugins and UI initialization in the packaged EXE.
        QTimer.singleShot(1000, app.quit)
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
