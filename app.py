import sys, sqlite3, json
from board_widgets import TaskList
from theme import make_style, PALETTES, ACCENTS, FONTS
from datetime import date
from PySide6.QtWidgets import QMenu, QStyle
from pathlib import Path
from datetime import datetime, timedelta, time
from PySide6.QtGui import QKeySequence, QShortcut, QColor, QBrush, QPainter, QPen, QFontMetrics
from PySide6.QtCore import Qt, QTimer, QDateTime, QSize, QRectF
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QPushButton,QLabel,QListWidget,QListWidgetItem,QLineEdit,QTextEdit,QInputDialog,QMessageBox,QSplitter,QTabWidget,QDateTimeEdit,QDialog,QDialogButtonBox,QFormLayout,QComboBox,QCheckBox,QSystemTrayIcon,QStyle,QColorDialog,QGroupBox,QScrollArea,QSpinBox,QFrame,QSizePolicy,QStyledItemDelegate,QStyleOptionViewItem)

ROOT=Path.home()/'.apex_task_control'; ROOT.mkdir(exist_ok=True)
DB=ROOT/'apex.db'
SETTINGS_FILE=ROOT/'settings.json'
def load_settings():
    try:
        data=json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError):return {}
def save_settings(data):
    SETTINGS_FILE.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
BACKUPS=ROOT/'backups'; BACKUPS.mkdir(exist_ok=True)
first_run=not DB.exists()
con=sqlite3.connect(DB)
con.row_factory=sqlite3.Row
con.execute('PRAGMA busy_timeout=5000')
con.executescript('''CREATE TABLE IF NOT EXISTS boards(id INTEGER PRIMARY KEY,name TEXT NOT NULL);CREATE TABLE IF NOT EXISTS lanes(id INTEGER PRIMARY KEY,board_id INTEGER NOT NULL,name TEXT NOT NULL,position INTEGER DEFAULT 0);CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,lane_id INTEGER NOT NULL,title TEXT NOT NULL,body TEXT DEFAULT '',checklist TEXT DEFAULT '[]',due TEXT,reminded INTEGER DEFAULT 0,position INTEGER DEFAULT 0);CREATE TABLE IF NOT EXISTS folders(id INTEGER PRIMARY KEY,name TEXT NOT NULL);CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY,folder_id INTEGER NOT NULL,title TEXT NOT NULL,body TEXT DEFAULT '',pinned INTEGER DEFAULT 0);''')
# Additive migration: existing local data remains intact.
for table in ('tasks','notes','folders','boards','lanes'):
    cols={row['name'] for row in con.execute(f'PRAGMA table_info({table})')}
    if 'color' not in cols:
        con.execute(f"ALTER TABLE {table} ADD COLUMN color TEXT DEFAULT ''")
# Schema migration for existing installations (no data deletion).
lane_columns={row['name'] for row in con.execute('PRAGMA table_info(lanes)')}
if 'timer_enabled' not in lane_columns:
    con.execute('ALTER TABLE lanes ADD COLUMN timer_enabled INTEGER NOT NULL DEFAULT 1')
for table in ('lanes','tasks'):
    cols={r['name'] for r in con.execute(f'PRAGMA table_info({table})')}
    for col,definition in [('bg_color',"TEXT DEFAULT ''"),('text_color',"TEXT DEFAULT ''")]:
        if col not in cols:
            con.execute(f'ALTER TABLE {table} ADD COLUMN {col} {definition}')
lane_cols={r['name'] for r in con.execute('PRAGMA table_info(lanes)')}
if 'width' not in lane_cols:
    con.execute('ALTER TABLE lanes ADD COLUMN width INTEGER DEFAULT 320')
if first_run and not con.execute('SELECT 1 FROM boards').fetchone():
    con.execute('INSERT INTO boards(name) VALUES(?)',('Работа',)); bid=con.execute('SELECT last_insert_rowid()').fetchone()[0]
    for i,n in enumerate(['Входящие','В работе','Ожидание','Готово']):con.execute('INSERT INTO lanes(board_id,name,position) VALUES(?,?,?)',(bid,n,i))
if first_run and not con.execute('SELECT 1 FROM folders').fetchone():con.execute('INSERT INTO folders(name) VALUES(?)',('Общие заметки',))
con.commit()
# Consistent snapshot; never copy an open SQLite file directly.
backup_path=BACKUPS/('apex-'+date.today().isoformat()+'.db')
if not backup_path.exists():
    try:
        with sqlite3.connect(backup_path) as backup:
            con.backup(backup)
    except sqlite3.Error:
        backup_path.unlink(missing_ok=True)
def rows(q,p=()):return con.execute(q,p).fetchall()
def run(q,p=()):con.execute(q,p);con.commit()
class TaskDialog(QDialog):
    def __init__(self,parent=None,data=None):
        super().__init__(parent);self.setWindowTitle('Карточка задачи');self.resize(540,530)
        form=QFormLayout(self);self.title=QLineEdit(data['title'] if data else '');self.body=QTextEdit(data['body'] if data else '');self.check=QTextEdit('\n'.join(json.loads(data['checklist'] or '[]')) if data else '');self.due_enabled=QCheckBox('Напомнить в указанное время');self.due=QDateTimeEdit();self.due.setCalendarPopup(True);self.due.setDateTime(QDateTime.currentDateTime().addSecs(7200));self.due_enabled.setChecked(True)
        if data and data['due']:
            self.due_enabled.setChecked(True);self.due.setDateTime(QDateTime.fromString(data['due'],Qt.ISODate))
        self.color=QComboBox()
        for label,code in [('Без цвета',''),('Розовый','#ed93bd'),('Голубой','#8ac9e8'),('Мятный','#80cbb2'),('Жёлтый','#e6cf83'),('Сиреневый','#b5a0e6'),('Персиковый','#eda989')]:
            self.color.addItem(label,code)
            if code:self.color.setItemData(self.color.count()-1,QBrush(QColor(code)),Qt.ItemDataRole.ForegroundRole)
        if data:
            idx=self.color.findData(data['color'] or '')
            if idx>=0:self.color.setCurrentIndex(idx)
        form.addRow('Цвет',self.color)
        form.addRow('Название',self.title);form.addRow('Описание / записи',self.body);form.addRow('Чек-лист (пункт на строку)',self.check);form.addRow(self.due_enabled);form.addRow('Когда',self.due)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);form.addRow(buttons)
    def values(self):return (self.title.text().strip(),self.body.toPlainText(),json.dumps([x.strip() for x in self.check.toPlainText().splitlines() if x.strip()],ensure_ascii=False),self.due.dateTime().toPython().isoformat(timespec='minutes') if self.due_enabled.isChecked() else None)
    def selected_color(self):return self.color.currentData()
class CardDelegate(QStyledItemDelegate):
    """Paints each task directly: no nested widget geometry or clipping."""
    def __init__(self, parent=None, accent='#5c96d8', light=False, card_bg=None):
        super().__init__(parent)
        self.accent=accent
        self.light=light
        self.card_bg=card_bg

    def sizeHint(self, option, index):
        title=str(index.data(Qt.ItemDataRole.DisplayRole) or '')
        width=max(170,option.rect.width()-32)
        metrics=QFontMetrics(option.font)
        lines=max(1,metrics.boundingRect(0,0,width-28,1000,Qt.TextFlag.TextWordWrap,title).height()//max(1,metrics.lineSpacing())+1)
        return QSize(width,58)

    def paint(self,painter,option,index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=option.rect.adjusted(3,4,-3,-4)
        selected=bool(option.state & QStyle.StateFlag.State_Selected)
        surface=index.data(Qt.ItemDataRole.UserRole+3) or (self.card_bg if hasattr(self,'card_bg') and self.card_bg else ('#ffffff' if self.light else '#253447'))
        border=self.accent if selected else ('#d7e0eb' if self.light else '#3b4c60')
        painter.setPen(QPen(QColor(border),2 if selected else 1))
        painter.setBrush(QColor(surface))
        painter.drawRoundedRect(QRectF(rect),11,11)
        color=index.data(Qt.ItemDataRole.UserRole+1) or self.accent
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(rect.left()+1,rect.top()+7,4,rect.height()-14),2,2)
        fg=index.data(Qt.ItemDataRole.UserRole+4) or ('#253449' if self.light else '#f1f5fb')
        muted='#66788c' if self.light else '#afc1d4'
        title=str(index.data(Qt.ItemDataRole.DisplayRole) or '')
        painter.setPen(QColor(fg))
        font=option.font
        font.setBold(True)
        painter.setFont(font)
        meta=str(index.data(Qt.ItemDataRole.UserRole+2) or '')
        right_width=130 if meta else 0
        title_width=max(50,rect.width()-38-right_width)
        metrics=QFontMetrics(font)
        title=metrics.elidedText(title,Qt.TextElideMode.ElideRight,title_width)
        painter.drawText(rect.left()+17,rect.top(),title_width,rect.height(),
                         Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,title)
        if meta:
            painter.setPen(QColor(fg if index.data(Qt.ItemDataRole.UserRole+4) else muted))
            font.setBold(False)
            font.setPointSizeF(max(8,font.pointSizeF()-1))
            painter.setFont(font)
            painter.drawText(rect.right()-right_width-9,rect.top(),right_width,rect.height(),
                             Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,meta)
        painter.restore()

class App(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('APEX // TASK CONTROL');self.resize(1300,800)
        self.settings=load_settings()
        self.tabs=QTabWidget();self.setCentralWidget(self.tabs)
        self.boards=QWidget();self.notes=QWidget();self.control=QWidget();self.tabs.addTab(self.boards,'▦  Доски');self.tabs.addTab(self.notes,'✎  Блокнот');self.tabs.addTab(self.control,'◷  Расписание')
        self.setup_boards();self.setup_notes();self.setup_control();self.tabs.currentChanged.connect(lambda _:self.refresh_all())
        self.tray=QSystemTrayIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation),self);self.tray.setToolTip('APEX TASK CONTROL');self.tray.show()
        self.note_dirty=False
        self.active_note_id=None
        self.note_title.textChanged.connect(self.mark_note_dirty)
        self.note_body.textChanged.connect(self.mark_note_dirty)
        self.note_save_timer=QTimer(self);self.note_save_timer.setSingleShot(True);self.note_save_timer.setInterval(800);self.note_save_timer.timeout.connect(self.save_note)
        self.quick_shortcut=QShortcut(QKeySequence('Ctrl+N'),self);self.quick_shortcut.activated.connect(self.quick_add)
        self.timer=QTimer(self);self.timer.timeout.connect(self.check_due);self.timer.start(15000);self.check_due()
        self.schedule_timer=QTimer(self);self.schedule_timer.timeout.connect(self.refresh_control);self.schedule_timer.start(30000)
        self.apply_theme()
        self.statusBar().showMessage('Готово • данные сохраняются локально')
    def apply_theme(self):
        settings=self.settings
        self.setStyleSheet(make_style(
            settings.get('theme','Тёмно-синий'),
            settings.get('accent','Синий'),
            settings.get('font','Segoe UI'),
            settings.get('font_size',13),settings.get('background') or None))
        self.refresh_board()

    def show_settings(self):
        dialog=QDialog(self)
        dialog.setWindowTitle('APEX — оформление')
        dialog.resize(420,260)
        form=QFormLayout(dialog)
        theme=QComboBox();theme.addItems(list(PALETTES))
        accent=QComboBox();accent.addItems(list(ACCENTS))
        font=QComboBox();font.addItems(FONTS)
        size=QSpinBox();size.setRange(11,19);size.setSuffix(' px')
        for widget,key,default in [(theme,'theme','Тёмно-синий'),(accent,'accent','Синий'),(font,'font','Segoe UI')]:
            value=self.settings.get(key,default)
            idx=widget.findText(value)
            if idx>=0:widget.setCurrentIndex(idx)
        size.setValue(self.settings.get('font_size',13))
        form.addRow('Тема интерфейса',theme)
        form.addRow('Акцент',accent)
        form.addRow('Шрифт',font)
        form.addRow('Размер текста',size)
        selected_colors={'background':self.settings.get('background',''),'card_bg':self.settings.get('card_bg','')}
        background_button=QPushButton('Выбрать цвет…')
        card_button=QPushButton('Выбрать цвет…')
        def pick_color(key,default):
            color=QColorDialog.getColor(QColor(selected_colors[key] or default),dialog,'Цвет оформления')
            if color.isValid():selected_colors[key]=color.name()
        background_button.clicked.connect(lambda:pick_color('background','#101924'))
        card_button.clicked.connect(lambda:pick_color('card_bg','#253447'))
        form.addRow('Фон приложения',background_button)
        form.addRow('Фон карточек',card_button)
        reset=QPushButton('Сбросить индивидуальные цвета')
        reset.clicked.connect(lambda:selected_colors.update({'background':'','card_bg':''}))
        form.addRow(reset)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.settings={'theme':theme.currentText(),'accent':accent.currentText(),
                'font':font.currentText(),'font_size':size.value(),**selected_colors}
            save_settings(self.settings)
            self.apply_theme()

    def setup_boards(self):
        lay=QVBoxLayout(self.boards);top=QHBoxLayout();self.board_pick=QComboBox();self.board_pick.setMinimumWidth(200);self.board_pick.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);self.board_pick.setMinimumContentsLength(20);self.board_pick.currentIndexChanged.connect(self.refresh_board);top.addWidget(QLabel('Доска:'));top.addWidget(self.board_pick);addboard=QPushButton('+ Доска');addboard.clicked.connect(self.add_board);top.addWidget(addboard);addlane=QPushButton('+ Колонка');addlane.clicked.connect(self.add_lane);top.addWidget(addlane)
        options=QPushButton('⋯ Доска');options.clicked.connect(self.board_menu);top.addWidget(options)
        top.addStretch();settings=QPushButton('Настройки вида');settings.clicked.connect(self.show_settings);top.addWidget(settings);lay.addLayout(top)
        self.lanes=QHBoxLayout();self.lanes.setSpacing(14);self.lanes.setAlignment(Qt.AlignmentFlag.AlignLeft);lay.addLayout(self.lanes,1);self.refresh_boards()
    def refresh_boards(self):
        selected=self.board_pick.currentData();self.board_pick.blockSignals(True);self.board_pick.clear()
        for b in rows('SELECT * FROM boards ORDER BY id'):self.board_pick.addItem(b['name'],b['id'])
        idx=self.board_pick.findData(selected)
        if idx>=0:self.board_pick.setCurrentIndex(idx)
        self.board_pick.blockSignals(False)
        self.board_pick.view().setMinimumWidth(max(260,self.board_pick.sizeHint().width()))
        self.refresh_board()
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
            panel=QFrame()
            panel.setObjectName('lanePanel')
            panel.setFixedWidth(max(240,min(720,lane['width'] or 320)))
            if lane['bg_color']:
                panel.setStyleSheet('QFrame#lanePanel {background:'+lane['bg_color']+';border-radius:12px;}')
            v=QVBoxLayout(panel)
            v.setContentsMargins(12,12,12,12)
            v.setSpacing(10)
            tasks=rows('SELECT * FROM tasks WHERE lane_id=? ORDER BY position,id',(lane['id'],))
            header=QPushButton(('●  ' if lane['timer_enabled'] else '○  ')+lane['name']+'   '+str(len(tasks))+'   ···')
            header.setObjectName('laneHeader')
            header.setToolTip('Настройки колонки и контроль таймеров')
            header.clicked.connect(lambda _,lid=lane['id']:self.lane_menu(lid))
            if lane['text_color']:
                header.setStyleSheet('QPushButton#laneHeader {color:'+lane['text_color']+';}')
            v.addWidget(header)
            lst=TaskList(lane['id'])
            lst.setObjectName('kanbanList')
            lst.setMinimumWidth(210)
            lst.setSpacing(9)
            lst.moved.connect(self.drop_task)
            light=self.settings.get('theme')=='Светлая' if hasattr(self,'settings') else False
            accent=ACCENTS.get(self.settings.get('accent','Синий'),'#5c96d8') if hasattr(self,'settings') else '#5c96d8'
            lst.setItemDelegate(CardDelegate(lst,accent,light,self.settings.get('card_bg')))
            for task in tasks:
                item=QListWidgetItem(task['title'])
                item.setData(Qt.UserRole,task['id'])
                item.setData(Qt.UserRole+1,task['color'] or accent)
                deadline=''
                if task['due']:
                    try:
                        due=datetime.fromisoformat(task['due'])
                        deadline=('ПРОСРОЧЕНО ' if due<datetime.now() else '')+due.strftime('%d.%m %H:%M')
                    except ValueError:pass
                item.setData(Qt.UserRole+2,deadline)
                item.setData(Qt.UserRole+3,task['bg_color'] or '')
                item.setData(Qt.UserRole+4,task['text_color'] or '')
                lst.addItem(item)
            lst.itemDoubleClicked.connect(lambda item:self.edit_task(item.data(Qt.UserRole)))
            lst.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            lst.customContextMenuRequested.connect(lambda point,l=lst:self.task_menu(l,point))
            v.addWidget(lst,1)
            add=QPushButton('+ Новая задача')
            add.setObjectName('addTaskButton')
            add.clicked.connect(lambda _,lid=lane['id']:self.add_task(lid))
            v.addWidget(add)
            self.lanes.addWidget(panel,0)

    def drop_task(self, task_id, lane_id, index):
        # Rebuild positions atomically; the source and destination may coincide.
        task=con.execute('SELECT lane_id FROM tasks WHERE id=?',(task_id,)).fetchone()
        if not task:return
        source=task['lane_id']
        ids=[r['id'] for r in rows('SELECT id FROM tasks WHERE lane_id=? AND id!=? ORDER BY position,id',(lane_id,task_id))]
        ids.insert(max(0,min(index,len(ids))),task_id)
        try:
            with con:
                con.execute('UPDATE tasks SET lane_id=? WHERE id=?',(lane_id,task_id))
                for pos,tid in enumerate(ids):
                    con.execute('UPDATE tasks SET position=? WHERE id=?',(pos,tid))
                if source!=lane_id:
                    for pos,r in enumerate(rows('SELECT id FROM tasks WHERE lane_id=? ORDER BY position,id',(source,))):
                        con.execute('UPDATE tasks SET position=? WHERE id=?',(pos,r['id']))
        except sqlite3.Error as error:
            QMessageBox.warning(self,'Ошибка перемещения',str(error))
        self.refresh_board()

    def task_menu(self, lst, point):
        item=lst.itemAt(point)
        if not item:return
        task_id=item.data(Qt.ItemDataRole.UserRole)
        menu=QMenu(lst)
        edit=menu.addAction('Открыть карточку')
        delete=menu.addAction('Удалить карточку…')
        action=menu.exec(lst.mapToGlobal(point))
        if action==edit:self.edit_task(task_id)
        elif action==delete:
            if QMessageBox.question(self,'Удалить карточку?','Это действие нельзя отменить. Продолжить?')==QMessageBox.StandardButton.Yes:
                run('DELETE FROM tasks WHERE id=?',(task_id,));self.refresh_all()

    def ask_color(self, current=''):
        color=QColorDialog.getColor(QColor(current or '#8ac9e8'),self,'Выбрать цвет')
        return color.name() if color.isValid() else None
    def confirm_delete(self, what, count=0):
        return QMessageBox.question(self,'Подтвердить удаление',
            f'Удалить {what}? Связанных записей: {count}. Отменить действие нельзя.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes
    def board_menu(self):
        bid=self.board_pick.currentData()
        if bid is None:return
        menu=QMenu(self);rename=menu.addAction('Переименовать');color=menu.addAction('Выбрать цвет');delete=menu.addAction('Удалить доску…')
        action=menu.exec(self.cursor().pos())
        if action==rename:
            old=rows('SELECT name FROM boards WHERE id=?',(bid,))[0]['name']
            name,ok=QInputDialog.getText(self,'Название доски','Название:',text=old)
            if ok and name.strip():run('UPDATE boards SET name=? WHERE id=?',(name.strip(),bid));self.refresh_boards()
        elif action==color:
            old=rows('SELECT color FROM boards WHERE id=?',(bid,))[0]['color']
            value=self.ask_color(old)
            if value:run('UPDATE boards SET color=? WHERE id=?',(value,bid))
        elif action==delete:
            count=rows('SELECT COUNT(*) AS n FROM tasks JOIN lanes ON tasks.lane_id=lanes.id WHERE lanes.board_id=?',(bid,))[0]['n']
            if self.confirm_delete('доску и все её карточки',count):
                with con:
                    con.execute('DELETE FROM tasks WHERE lane_id IN (SELECT id FROM lanes WHERE board_id=?)',(bid,))
                    con.execute('DELETE FROM lanes WHERE board_id=?',(bid,))
                    con.execute('DELETE FROM boards WHERE id=?',(bid,))
                self.refresh_boards()
    def lane_menu(self,lid):
        lane=rows('SELECT * FROM lanes WHERE id=?',(lid,))
        if not lane:return
        lane=lane[0];menu=QMenu(self);rename=menu.addAction('Переименовать');color=menu.addAction('Выбрать цвет');toggle=menu.addAction('Выключить контроль таймеров' if lane['timer_enabled'] else 'Включить контроль таймеров');delete=menu.addAction('Удалить колонку…')
        action=menu.exec(self.cursor().pos())
        if action==rename:
            name,ok=QInputDialog.getText(self,'Название колонки','Название:',text=lane['name'])
            if ok and name.strip():run('UPDATE lanes SET name=? WHERE id=?',(name.strip(),lid));self.refresh_board()
        elif action==color:
            value=self.ask_color(lane['color'])
            if value:run('UPDATE lanes SET color=? WHERE id=?',(value,lid));self.refresh_board()
        elif action==toggle:
            run('UPDATE lanes SET timer_enabled=? WHERE id=?',(0 if lane['timer_enabled'] else 1,lid))
            self.refresh_all()
        elif action==delete:
            count=rows('SELECT COUNT(*) AS n FROM tasks WHERE lane_id=?',(lid,))[0]['n']
            if self.confirm_delete('колонку и все её карточки',count):
                with con:
                    con.execute('DELETE FROM tasks WHERE lane_id=?',(lid,))
                    con.execute('DELETE FROM lanes WHERE id=?',(lid,))
                self.refresh_board()
    def add_board(self):
        name,ok=QInputDialog.getText(self,'Новая доска','Название:')
        if ok and name.strip():run('INSERT INTO boards(name) VALUES(?)',(name.strip(),));self.refresh_boards()
    def add_lane(self):
        name,ok=QInputDialog.getText(self,'Новая колонка','Название:')
        if ok and name.strip() and self.board_pick.currentData():run('INSERT INTO lanes(board_id,name,position) VALUES(?,?,?)',(self.board_pick.currentData(),name.strip(),len(rows('SELECT id FROM lanes WHERE board_id=?',(self.board_pick.currentData(),)))));self.refresh_board()
    def add_task(self,lid):
        d=TaskDialog(self)
        if d.exec() and d.title.text().strip():run('INSERT INTO tasks(lane_id,title,body,checklist,due,color) VALUES(?,?,?,?,?,?)',(lid,*d.values(),d.selected_color()));self.refresh_board()
    def edit_task(self,tid):
        task=rows('SELECT * FROM tasks WHERE id=?',(tid,))[0];d=TaskDialog(self,task)
        if d.exec() and d.title.text().strip():run('UPDATE tasks SET title=?,body=?,checklist=?,due=?,color=?,reminded=0 WHERE id=?',(*d.values(),d.selected_color(),tid));self.refresh_all()
    def move_task(self,lst,lid):
        item=lst.currentItem()
        if not item:return
        lanes=rows('SELECT * FROM lanes WHERE board_id=? ORDER BY position,id',(self.board_pick.currentData(),));names=[l['name'] for l in lanes];name,ok=QInputDialog.getItem(self,'Переместить карточку','В колонку:',names,0,False)
        if ok:run('UPDATE tasks SET lane_id=? WHERE id=?',(lanes[names.index(name)]['id'],item.data(Qt.UserRole)));self.refresh_board()
    def setup_notes(self):
        h=QHBoxLayout(self.notes);left=QVBoxLayout();self.folder_list=QListWidget();self.folder_list.currentItemChanged.connect(lambda *_:self.refresh_notes());left.addWidget(QLabel('Папки'));left.addWidget(self.folder_list)
        self.folder_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.folder_list.customContextMenuRequested.connect(lambda point:self.folder_menu(point))
        b=QPushButton('+ Папка');b.clicked.connect(self.add_folder);left.addWidget(b);h.addLayout(left,1)
        middle=QVBoxLayout();middle.addWidget(QLabel('Записи'));self.note_list=QListWidget();self.note_list.currentItemChanged.connect(lambda *_:self.change_note());middle.addWidget(self.note_list)
        self.note_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.note_list.customContextMenuRequested.connect(lambda point:self.note_menu(point))
        b=QPushButton('+ Запись');b.clicked.connect(self.add_note);middle.addWidget(b);h.addLayout(middle,2)
        right=QVBoxLayout();self.note_title=QLineEdit();self.note_title.setPlaceholderText('Заголовок');self.note_body=QTextEdit();right.addWidget(self.note_title);right.addWidget(self.note_body);b=QPushButton('Сохранить запись');b.clicked.connect(self.save_note);right.addWidget(b);h.addLayout(right,4);self.refresh_folders()
    def refresh_folders(self):
        self.flush_note() if hasattr(self,'note_save_timer') else None
        current=self.folder_list.currentItem().data(Qt.UserRole) if self.folder_list.currentItem() else None;self.folder_list.clear()
        for f in rows('SELECT * FROM folders ORDER BY id'):
            item=QListWidgetItem(f['name']);item.setData(Qt.UserRole,f['id']);self.folder_list.addItem(item)
            if f['color']:item.setForeground(QBrush(QColor(f['color'])))
            if f['id']==current:self.folder_list.setCurrentItem(item)
        if not self.folder_list.currentItem() and self.folder_list.count():self.folder_list.setCurrentRow(0)
    def add_folder(self):
        name,ok=QInputDialog.getText(self,'Новая папка','Название:')
        if ok and name.strip():run('INSERT INTO folders(name) VALUES(?)',(name.strip(),));self.refresh_folders()
    def folder_menu(self,point):
        item=self.folder_list.itemAt(point)
        if not item:return
        fid=item.data(Qt.UserRole)
        menu=QMenu(self);rename=menu.addAction('Переименовать папку');color=menu.addAction('Выбрать цвет');delete=menu.addAction('Удалить папку…')
        action=menu.exec(self.folder_list.mapToGlobal(point))
        if action==rename:
            name,ok=QInputDialog.getText(self,'Папка','Новое название:',text=item.text())
            if ok and name.strip():run('UPDATE folders SET name=? WHERE id=?',(name.strip(),fid));self.refresh_folders()
        elif action==color:
            value=self.ask_color(rows('SELECT color FROM folders WHERE id=?',(fid,))[0]['color'])
            if value:run('UPDATE folders SET color=? WHERE id=?',(value,fid));self.refresh_folders()
        elif action==delete:
            count=rows('SELECT COUNT(*) AS n FROM notes WHERE folder_id=?',(fid,))[0]['n']
            if self.confirm_delete('папку и все её записи',count):
                self.flush_note();self.active_note_id=None
                with con:
                    con.execute('DELETE FROM notes WHERE folder_id=?',(fid,))
                    con.execute('DELETE FROM folders WHERE id=?',(fid,))
                self.refresh_folders();self.refresh_notes()
    def note_menu(self,point):
        item=self.note_list.itemAt(point)
        if not item:return
        nid=item.data(Qt.UserRole)
        record=rows('SELECT * FROM notes WHERE id=?',(nid,))[0]
        menu=QMenu(self);rename=menu.addAction('Переименовать');pin=menu.addAction('Открепить' if record['pinned'] else 'Закрепить');color=menu.addAction('Выбрать цвет');delete=menu.addAction('Удалить запись…')
        action=menu.exec(self.note_list.mapToGlobal(point))
        if action==rename:
            name,ok=QInputDialog.getText(self,'Запись','Название:',text=record['title'])
            if ok and name.strip():
                self.flush_note();run('UPDATE notes SET title=? WHERE id=?',(name.strip(),nid));self.refresh_notes()
                if self.active_note_id==nid:self.open_note()
        elif action==pin:
            self.flush_note();run('UPDATE notes SET pinned=? WHERE id=?',(0 if record['pinned'] else 1,nid));self.refresh_notes()
        elif action==color:
            value=self.ask_color(record['color'])
            if value:run('UPDATE notes SET color=? WHERE id=?',(value,nid));self.refresh_notes()
        elif action==delete and self.confirm_delete('запись'):
            self.flush_note();run('DELETE FROM notes WHERE id=?',(nid,))
            if self.active_note_id==nid:self.active_note_id=None
            self.refresh_notes()
    def refresh_notes(self):
        self.flush_note();selected=self.note_list.currentItem().data(Qt.UserRole) if self.note_list.currentItem() else None
        self.note_list.blockSignals(True);self.note_list.clear();f=self.folder_list.currentItem()
        if f:
            for n in rows('SELECT * FROM notes WHERE folder_id=? ORDER BY pinned DESC,id DESC',(f.data(Qt.UserRole),)):
                item=QListWidgetItem(('★ ' if n['pinned'] else '')+n['title']);item.setData(Qt.UserRole,n['id']);self.note_list.addItem(item)
                if n['color']:item.setForeground(QBrush(QColor(n['color'])))
                if n['id']==selected:self.note_list.setCurrentItem(item)
        self.note_list.blockSignals(False)
        self.change_note()
    def change_note(self):
        item=self.note_list.currentItem()
        next_id=item.data(Qt.UserRole) if item else None
        if next_id==getattr(self,'active_note_id',None):return
        self.flush_note()
        self.active_note_id=next_id
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
        if self.active_note_id is None:
            self.note_title.clear();self.note_body.clear()
        else:
            record=rows('SELECT * FROM notes WHERE id=?',(self.active_note_id,))
            if record:
                self.note_title.setText(record[0]['title'])
                self.note_body.setPlainText(record[0]['body'])
        self.note_loading=False
        self.note_dirty=False
    def add_note(self):
        f=self.folder_list.currentItem()
        if not f:return
        run('INSERT INTO notes(folder_id,title) VALUES(?,?)',(f.data(Qt.UserRole),'Новая запись'));self.refresh_notes();self.note_list.setCurrentRow(0);self.note_title.setFocus()
    def save_note(self):
        if getattr(self,'note_loading',False):return
        note_id=getattr(self,'active_note_id',None)
        if note_id is None:return
        run('UPDATE notes SET title=?,body=? WHERE id=?',(self.note_title.text().strip() or 'Без названия',self.note_body.toPlainText(),note_id))
        self.note_dirty=False
        self.refresh_notes()
    def setup_control(self):
        layout=QVBoxLayout(self.control)
        heading=QLabel('РАСПИСАНИЕ  /  БЛИЖАЙШИЕ ДНИ')
        heading.setStyleSheet('font-size:17px;font-weight:600;padding:8px')
        layout.addWidget(heading)
        description=QLabel('Все доски · сегодня и два следующих дня · ближайшие задачи выше')
        description.setStyleSheet('color:#9eafc5;padding-left:8px')
        layout.addWidget(description)
        self.schedule_summary=QLabel()
        layout.addWidget(self.schedule_summary)
        self.schedule_scroll=QScrollArea()
        self.schedule_scroll.setWidgetResizable(True)
        self.schedule_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.schedule_content=QWidget()
        self.schedule_layout=QVBoxLayout(self.schedule_content)
        self.schedule_layout.setSpacing(12)
        self.schedule_scroll.setWidget(self.schedule_content)
        layout.addWidget(self.schedule_scroll)
        refresh=QPushButton('↻ Обновить расписание')
        refresh.clicked.connect(self.refresh_control)
        layout.addWidget(refresh)
        self.refresh_control()

    def refresh_control(self):
        if not hasattr(self,'schedule_layout'):return
        self.clear_layout(self.schedule_layout)
        now=datetime.now()
        end=datetime.combine(now.date()+timedelta(days=3),time.min)
        records=rows("""SELECT tasks.*, lanes.name AS lane_name,
            lanes.timer_enabled, boards.name AS board_name
            FROM tasks JOIN lanes ON lanes.id=tasks.lane_id
            JOIN boards ON boards.id=lanes.board_id
            WHERE tasks.due IS NOT NULL AND lanes.timer_enabled=1
            ORDER BY tasks.due ASC, tasks.id ASC""")
        groups={'Просроченные':[], 'Сегодня':[], 'Завтра':[], 'Послезавтра':[]}
        for task in records:
            try:due=datetime.fromisoformat(task['due'])
            except (ValueError,TypeError):continue
            if due<now:group='Просроченные'
            elif due>=end:continue
            else:
                day=(due.date()-now.date()).days
                group=['Сегодня','Завтра','Послезавтра'][day]
            groups[group].append((task,due))
        total=sum(map(len,groups.values()))
        self.schedule_summary.setText(f'   {total} задач · просрочено: {len(groups["Просроченные"])}')
        self.schedule_summary.setStyleSheet('color:#a7c5e9;padding:8px')
        if total==0:
            empty=QLabel('На ближайшие дни задач с активными таймерами нет ✨')
            empty.setStyleSheet('color:#a5b8cd;padding:28px')
            self.schedule_layout.addWidget(empty)
        for group,items in groups.items():
            if not items:continue
            title=QLabel(group.upper()+f'   ·   {len(items)}')
            title.setStyleSheet('font-weight:600;font-size:14px;color:#a9bed7;padding:8px')
            self.schedule_layout.addWidget(title)
            for task,due in items:
                delta=due-now
                if delta.total_seconds()<0:
                    minutes=int(abs(delta.total_seconds())//60)
                    relative=f'Просрочено на {minutes} мин'
                else:
                    minutes=max(0,int(delta.total_seconds()//60))
                    relative=f'Через {minutes} мин' if minutes<60 else f'Через {minutes//60} ч {minutes%60} мин'
                text=f'  {due:%H:%M}     {task["title"]}\n  {task["board_name"]}  /  {task["lane_name"]}     ·     {relative}'
                button=QPushButton(text)
                button.setMinimumHeight(66)
                button.setToolTip('Нажмите, чтобы открыть карточку')
                button.setStyleSheet('QPushButton{text-align:left;background:#202c3c;border:1px solid #34465c;border-left:4px solid '+(task['color'] or ('#f19b9b' if group=='Просроченные' else '#8ac9e8'))+';border-radius:9px;padding:10px;color:#eef4fb} QPushButton:hover{background:#2d4055}')
                button.clicked.connect(lambda _,tid=task['id']:self.edit_task(tid))
                self.schedule_layout.addWidget(button)
        self.schedule_layout.addStretch(1)

    def refresh_all(self):
        self.refresh_board()
        self.refresh_control()

    def check_due(self):
        now=datetime.now().isoformat(timespec='minutes')
        for t in rows("""SELECT tasks.* FROM tasks
            JOIN lanes ON lanes.id=tasks.lane_id
            WHERE tasks.due IS NOT NULL AND tasks.due<=?
            AND tasks.reminded=0 AND lanes.timer_enabled=1
            ORDER BY tasks.due""",(now,)):
            if self.tray.supportsMessages():
                self.tray.showMessage('APEX: пора проверить задачу',t['title'],QSystemTrayIcon.Information,12000)
            else:
                self.statusBar().showMessage('⏰ '+t['title'],15000)
            run('UPDATE tasks SET reminded=1 WHERE id=?',(t['id'],))
        if self.tabs.currentWidget()==self.control:self.refresh_control()
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
