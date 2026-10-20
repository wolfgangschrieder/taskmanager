import sys, sqlite3, json
from pathlib import Path
from datetime import datetime, timedelta
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import Qt, QTimer, QDateTime
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QPushButton,QLabel,QListWidget,QListWidgetItem,QLineEdit,QTextEdit,QInputDialog,QMessageBox,QSplitter,QTabWidget,QDateTimeEdit,QDialog,QDialogButtonBox,QFormLayout,QComboBox,QCheckBox,QSystemTrayIcon,QStyle)

ROOT=Path.home()/'.apex_task_control'; ROOT.mkdir(exist_ok=True)
DB=ROOT/'apex.db'
con=sqlite3.connect(DB)
con.row_factory=sqlite3.Row
con.executescript('''CREATE TABLE IF NOT EXISTS boards(id INTEGER PRIMARY KEY,name TEXT NOT NULL);CREATE TABLE IF NOT EXISTS lanes(id INTEGER PRIMARY KEY,board_id INTEGER NOT NULL,name TEXT NOT NULL,position INTEGER DEFAULT 0);CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,lane_id INTEGER NOT NULL,title TEXT NOT NULL,body TEXT DEFAULT '',checklist TEXT DEFAULT '[]',due TEXT,reminded INTEGER DEFAULT 0,position INTEGER DEFAULT 0);CREATE TABLE IF NOT EXISTS folders(id INTEGER PRIMARY KEY,name TEXT NOT NULL);CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY,folder_id INTEGER NOT NULL,title TEXT NOT NULL,body TEXT DEFAULT '',pinned INTEGER DEFAULT 0);''')
if not con.execute('SELECT 1 FROM boards').fetchone():
    con.execute('INSERT INTO boards(name) VALUES(?)',('Работа',)); bid=con.execute('SELECT last_insert_rowid()').fetchone()[0]
    for i,n in enumerate(['Входящие','В работе','Ожидание','Готово']):con.execute('INSERT INTO lanes(board_id,name,position) VALUES(?,?,?)',(bid,n,i))
if not con.execute('SELECT 1 FROM folders').fetchone():con.execute('INSERT INTO folders(name) VALUES(?)',('Общие заметки',))
con.commit()
def rows(q,p=()):return con.execute(q,p).fetchall()
def run(q,p=()):con.execute(q,p);con.commit()
class TaskDialog(QDialog):
    def __init__(self,parent=None,data=None):
        super().__init__(parent);self.setWindowTitle('Карточка задачи');self.resize(540,530)
        form=QFormLayout(self);self.title=QLineEdit(data['title'] if data else '');self.body=QTextEdit(data['body'] if data else '');self.check=QTextEdit('\n'.join(json.loads(data['checklist'] or '[]')) if data else '');self.due_enabled=QCheckBox('Напомнить в указанное время');self.due=QDateTimeEdit();self.due.setCalendarPopup(True);self.due.setDateTime(QDateTime.currentDateTime().addSecs(1800))
        if data and data['due']:
            self.due_enabled.setChecked(True);self.due.setDateTime(QDateTime.fromString(data['due'],Qt.ISODate))
        form.addRow('Название',self.title);form.addRow('Описание / записи',self.body);form.addRow('Чек-лист (пункт на строку)',self.check);form.addRow(self.due_enabled);form.addRow('Когда',self.due)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);form.addRow(buttons)
    def values(self):return (self.title.text().strip(),self.body.toPlainText(),json.dumps([x.strip() for x in self.check.toPlainText().splitlines() if x.strip()],ensure_ascii=False),self.due.dateTime().toPython().isoformat(timespec='minutes') if self.due_enabled.isChecked() else None)
class App(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('APEX // TASK CONTROL');self.resize(1300,800)
        self.tabs=QTabWidget();self.setCentralWidget(self.tabs)
        self.boards=QWidget();self.notes=QWidget();self.control=QWidget();self.tabs.addTab(self.boards,'▦  Доски');self.tabs.addTab(self.notes,'✎  Блокнот');self.tabs.addTab(self.control,'◷  Контроль')
        self.setup_boards();self.setup_notes();self.setup_control();self.tabs.currentChanged.connect(lambda _:self.refresh_all())
        self.tray=QSystemTrayIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation),self);self.tray.setToolTip('APEX TASK CONTROL');self.tray.show()
        self.note_dirty=False
        self.note_title.textChanged.connect(self.mark_note_dirty)
        self.note_body.textChanged.connect(self.mark_note_dirty)
        self.note_save_timer=QTimer(self);self.note_save_timer.setSingleShot(True);self.note_save_timer.setInterval(800);self.note_save_timer.timeout.connect(self.save_note)
        self.quick_shortcut=QShortcut(QKeySequence('Ctrl+N'),self);self.quick_shortcut.activated.connect(self.quick_add)
        self.timer=QTimer(self);self.timer.timeout.connect(self.check_due);self.timer.start(15000);self.check_due()
        self.setStyleSheet('QMainWindow,QWidget{background:#121923;color:#e9eff9;font-size:13px} QLineEdit,QTextEdit,QListWidget,QComboBox,QDateTimeEdit{background:#202b3a;border:1px solid #344458;border-radius:6px;padding:7px;color:#f4f7ff} QPushButton{background:#315d91;border:0;border-radius:6px;padding:9px 13px;color:white} QPushButton:hover{background:#4075b4} QTabBar::tab{padding:12px 24px;background:#1c2938;color:#d8e5f7} QTabBar::tab:selected{background:#315d91} QListWidget::item{padding:9px} QListWidget::item:selected{background:#355476}')
    def setup_boards(self):
        lay=QVBoxLayout(self.boards);top=QHBoxLayout();self.board_pick=QComboBox();self.board_pick.currentIndexChanged.connect(self.refresh_board);top.addWidget(QLabel('Доска:'));top.addWidget(self.board_pick);addboard=QPushButton('+ Доска');addboard.clicked.connect(self.add_board);top.addWidget(addboard);addlane=QPushButton('+ Колонка');addlane.clicked.connect(self.add_lane);top.addWidget(addlane);top.addStretch();lay.addLayout(top)
        self.lanes=QHBoxLayout();lay.addLayout(self.lanes,1);self.refresh_boards()
    def refresh_boards(self):
        selected=self.board_pick.currentData();self.board_pick.blockSignals(True);self.board_pick.clear()
        for b in rows('SELECT * FROM boards ORDER BY id'):self.board_pick.addItem(b['name'],b['id'])
        idx=self.board_pick.findData(selected)
        if idx>=0:self.board_pick.setCurrentIndex(idx)
        self.board_pick.blockSignals(False);self.refresh_board()
    def clear_layout(self,layout):
        while layout.count():
            item=layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
            elif item.layout():self.clear_layout(item.layout)
    def refresh_board(self,*_):
        if not hasattr(self,'lanes'):return
        self.clear_layout(self.lanes);bid=self.board_pick.currentData()
        if bid is None:return
        for lane in rows('SELECT * FROM lanes WHERE board_id=? ORDER BY position,id',(bid,)):
            panel=QWidget();v=QVBoxLayout(panel);v.addWidget(QLabel('●  '+lane['name']))
            lst=QListWidget();lst.setMinimumWidth(210);lst.setDragEnabled(True);lst.setAcceptDrops(False)
            for task in rows('SELECT * FROM tasks WHERE lane_id=? ORDER BY position,id',(lane['id'],)):
                item=QListWidgetItem(task['title']+('   ⏰' if task['due'] else ''));item.setData(Qt.UserRole,task['id']);lst.addItem(item)
            lst.itemDoubleClicked.connect(lambda item:self.edit_task(item.data(Qt.UserRole)));v.addWidget(lst,1)
            add=QPushButton('+ Карточка');add.clicked.connect(lambda _,lid=lane['id']:self.add_task(lid));v.addWidget(add)
            move=QPushButton('Переместить выбранную →');move.clicked.connect(lambda _,l=lst,lid=lane['id']:self.move_task(l,lid));v.addWidget(move)
            self.lanes.addWidget(panel,1)
    def add_board(self):
        name,ok=QInputDialog.getText(self,'Новая доска','Название:')
        if ok and name.strip():run('INSERT INTO boards(name) VALUES(?)',(name.strip(),));self.refresh_boards()
    def add_lane(self):
        name,ok=QInputDialog.getText(self,'Новая колонка','Название:')
        if ok and name.strip() and self.board_pick.currentData():run('INSERT INTO lanes(board_id,name,position) VALUES(?,?,?)',(self.board_pick.currentData(),name.strip(),len(rows('SELECT id FROM lanes WHERE board_id=?',(self.board_pick.currentData(),)))));self.refresh_board()
    def add_task(self,lid):
        d=TaskDialog(self)
        if d.exec() and d.title.text().strip():run('INSERT INTO tasks(lane_id,title,body,checklist,due) VALUES(?,?,?,?,?)',(lid,*d.values()));self.refresh_board()
    def edit_task(self,tid):
        task=rows('SELECT * FROM tasks WHERE id=?',(tid,))[0];d=TaskDialog(self,task)
        if d.exec() and d.title.text().strip():run('UPDATE tasks SET title=?,body=?,checklist=?,due=?,reminded=0 WHERE id=?',(*d.values(),tid));self.refresh_all()
    def move_task(self,lst,lid):
        item=lst.currentItem()
        if not item:return
        lanes=rows('SELECT * FROM lanes WHERE board_id=? ORDER BY position,id',(self.board_pick.currentData(),));names=[l['name'] for l in lanes];name,ok=QInputDialog.getItem(self,'Переместить карточку','В колонку:',names,0,False)
        if ok:run('UPDATE tasks SET lane_id=? WHERE id=?',(lanes[names.index(name)]['id'],item.data(Qt.UserRole)));self.refresh_board()
    def setup_notes(self):
        h=QHBoxLayout(self.notes);left=QVBoxLayout();self.folder_list=QListWidget();self.folder_list.currentItemChanged.connect(lambda *_:self.refresh_notes());left.addWidget(QLabel('Папки'));left.addWidget(self.folder_list);b=QPushButton('+ Папка');b.clicked.connect(self.add_folder);left.addWidget(b);h.addLayout(left,1)
        middle=QVBoxLayout();middle.addWidget(QLabel('Записи'));self.note_list=QListWidget();self.note_list.currentItemChanged.connect(lambda *_:self.open_note());middle.addWidget(self.note_list);b=QPushButton('+ Запись');b.clicked.connect(self.add_note);middle.addWidget(b);h.addLayout(middle,2)
        right=QVBoxLayout();self.note_title=QLineEdit();self.note_title.setPlaceholderText('Заголовок');self.note_body=QTextEdit();right.addWidget(self.note_title);right.addWidget(self.note_body);b=QPushButton('Сохранить запись');b.clicked.connect(self.save_note);right.addWidget(b);h.addLayout(right,4);self.refresh_folders()
    def refresh_folders(self):
        current=self.folder_list.currentItem().data(Qt.UserRole) if self.folder_list.currentItem() else None;self.folder_list.clear()
        for f in rows('SELECT * FROM folders ORDER BY id'):
            item=QListWidgetItem(f['name']);item.setData(Qt.UserRole,f['id']);self.folder_list.addItem(item)
            if f['id']==current:self.folder_list.setCurrentItem(item)
        if not self.folder_list.currentItem() and self.folder_list.count():self.folder_list.setCurrentRow(0)
    def add_folder(self):
        name,ok=QInputDialog.getText(self,'Новая папка','Название:')
        if ok and name.strip():run('INSERT INTO folders(name) VALUES(?)',(name.strip(),));self.refresh_folders()
    def refresh_notes(self):
        self.flush_note();selected=self.note_list.currentItem().data(Qt.UserRole) if self.note_list.currentItem() else None
        self.note_list.blockSignals(True);self.note_list.clear();f=self.folder_list.currentItem()
        if f:
            for n in rows('SELECT * FROM notes WHERE folder_id=? ORDER BY pinned DESC,id DESC',(f.data(Qt.UserRole),)):
                item=QListWidgetItem(('★ ' if n['pinned'] else '')+n['title']);item.setData(Qt.UserRole,n['id']);self.note_list.addItem(item)
                if n['id']==selected:self.note_list.setCurrentItem(item)
        self.note_list.blockSignals(False)
        if self.note_list.currentItem() is None:
            self.open_note()
    def mark_note_dirty(self):
        if getattr(self,'note_loading',False):return
        self.note_dirty=True
        if hasattr(self,'note_save_timer'):self.note_save_timer.start()
    def flush_note(self):
        if getattr(self,'note_dirty',False):
            self.note_save_timer.stop()
            self.save_note()
    def open_note(self):
        self.note_loading=True
        item=self.note_list.currentItem()
        if not item:self.note_title.clear();self.note_body.clear();self.note_loading=False;self.note_dirty=False;return
        n=rows('SELECT * FROM notes WHERE id=?',(item.data(Qt.UserRole),))[0];self.note_title.setText(n['title']);self.note_body.setPlainText(n['body']);self.note_loading=False;self.note_dirty=False
    def add_note(self):
        f=self.folder_list.currentItem()
        if not f:return
        run('INSERT INTO notes(folder_id,title) VALUES(?,?)',(f.data(Qt.UserRole),'Новая запись'));self.refresh_notes();self.note_list.setCurrentRow(0);self.note_title.setFocus()
    def save_note(self):
        if getattr(self,'note_loading',False):return
        item=self.note_list.currentItem()
        if item:run('UPDATE notes SET title=?,body=? WHERE id=?',(self.note_title.text().strip() or 'Без названия',self.note_body.toPlainText(),item.data(Qt.UserRole)));self.note_dirty=False;self.refresh_notes()
    def setup_control(self):
        v=QVBoxLayout(self.control);v.addWidget(QLabel('Задачи с напоминаниями'));self.due_list=QListWidget();self.due_list.itemDoubleClicked.connect(lambda item:self.edit_task(item.data(Qt.UserRole)));v.addWidget(self.due_list);b=QPushButton('Обновить');b.clicked.connect(self.refresh_control);v.addWidget(b);self.refresh_control()
    def refresh_control(self):
        self.due_list.clear()
        for t in rows('SELECT * FROM tasks WHERE due IS NOT NULL ORDER BY due'):
            item=QListWidgetItem(f"{t['due'].replace('T',' ')}  |  {t['title']}");item.setData(Qt.UserRole,t['id']);self.due_list.addItem(item)
    def refresh_all(self):self.refresh_board();self.refresh_control()
    def check_due(self):
        now=datetime.now().isoformat(timespec='minutes')
        for t in rows('SELECT * FROM tasks WHERE due IS NOT NULL AND due<=? AND reminded=0',(now,)):
            self.tray.showMessage('APEX: пора проверить задачу',t['title'],QSystemTrayIcon.Information,12000)
            run('UPDATE tasks SET reminded=1 WHERE id=?',(t['id'],))
    def quick_add(self):
        self.tabs.setCurrentWidget(self.boards)
        bid=self.board_pick.currentData()
        lane=rows('SELECT id FROM lanes WHERE board_id=? ORDER BY position,id LIMIT 1',(bid,))
        if not lane:
            QMessageBox.information(self,'APEX','Сначала добавьте колонку.');return
        self.add_task(lane[0]['id'])
    def closeEvent(self,event):
        self.flush_note()
        con.commit()
        super().closeEvent(event)
if __name__=='__main__':
    app=QApplication(sys.argv);w=App();w.showMaximized();sys.exit(app.exec())
