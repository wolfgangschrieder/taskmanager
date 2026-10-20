"""Quiet, compact dark UI with accessible contrast."""
STYLE = """
QMainWindow, QWidget, QDialog {
    background: #121923;
    color: #eaf0fa;
    font-family: 'Segoe UI';
    font-size: 13px;
}
QTabWidget::pane { border: 0; }
QTabBar::tab {
    padding: 13px 25px;
    background: #182433;
    color: #aebfd3;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    background: #243a55;
    color: #ffffff;
    border-bottom: 2px solid #81b6ff;
}
QTabBar::tab:hover { background: #2b405b; }
QLineEdit, QTextEdit, QListWidget, QComboBox, QDateTimeEdit {
    background: #202c3c;
    border: 1px solid #35475e;
    border-radius: 9px;
    padding: 8px;
    color: #f1f6fd;
    selection-background-color: #426fa4;
}
QLineEdit:focus, QTextEdit:focus, QListWidget:focus {
    border: 1px solid #78b4f5;
}
QListWidget::item {
    padding: 12px;
    border-radius: 7px;
    margin: 2px 1px;
}
QListWidget::item:hover { background: #2c3d52; }
QListWidget::item:selected { background: #355777; }
QPushButton {
    background: #315d91;
    color: #ffffff;
    border: 1px solid #416d9d;
    border-radius: 8px;
    padding: 9px 13px;
    font-weight: 500;
}
QPushButton:hover { background: #4074ad; }
QPushButton:pressed { background: #25496e; }
QPushButton:disabled { color: #8697ac; background: #263344; }
QComboBox::drop-down { border: none; width: 22px; }
QToolTip {
    background: #28394e;
    color: #ffffff;
    border: 1px solid #57799f;
    padding: 5px;
}
"""
