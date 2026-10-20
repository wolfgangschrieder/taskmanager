"""Theme generation for APEX. No third-party fonts required."""
PALETTES = {
    "Графит": ("#141920", "#202936", "#2d3949", "#899bb0"),
    "Тёмно-синий": ("#101924", "#1b2b3d", "#2b4159", "#81b6f0"),
    "Уголь": ("#151515", "#242424", "#363636", "#a9adb4"),
    "Светлая": ("#f3f5f8", "#ffffff", "#d5dce5", "#3977ae"),
}
ACCENTS = {
    "Синий": "#5c96d8", "Бирюзовый": "#4aafa9",
    "Фиолетовый": "#a18ae1", "Зелёный": "#6eb98d",
    "Янтарный": "#d9a15d", "Розовый": "#d685aa",
}
FONTS = ["Segoe UI", "Inter", "Arial", "Calibri", "Verdana", "Tahoma"]


def make_style(theme="Тёмно-синий", accent="Синий", font="Segoe UI", size=13):
    bg, surface, border, muted = PALETTES.get(theme, PALETTES["Тёмно-синий"])
    primary = ACCENTS.get(accent, ACCENTS["Синий"])
    light = theme == "Светлая"
    fg = "#202c3c" if light else "#edf3fb"
    secondary = "#54657a" if light else "#b3c2d3"
    selected = "#dceafa" if light else "#304b67"
    return f"""
    QMainWindow, QWidget, QDialog {{
        background: {bg}; color: {fg};
        font-family: '{font}'; font-size: {int(size)}px;
    }}
    QTabWidget::pane {{ border: 0; }}
    QTabBar::tab {{
        padding: 12px 22px; background: {surface};
        color: {secondary}; border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{ color: {fg}; border-bottom: 2px solid {primary}; }}
    QTabBar::tab:hover {{ background: {selected}; }}
    QLineEdit, QTextEdit, QListWidget, QComboBox, QDateTimeEdit, QSpinBox {{
        background: {surface}; border: 1px solid {border};
        border-radius: 9px; padding: 8px; color: {fg};
        selection-background-color: {primary};
    }}
    QLineEdit:focus, QTextEdit:focus, QListWidget:focus {{
        border: 1px solid {primary};
    }}
    QListWidget::item {{ padding: 12px; margin: 3px 1px; border-radius: 8px; }}
    QListWidget::item:hover {{ background: {selected}; }}
    QListWidget::item:selected {{ background: {selected}; border: 1px solid {primary}; }}
    QPushButton {{
        background: {surface}; color: {fg}; border: 1px solid {border};
        border-radius: 9px; padding: 9px 14px; font-weight: 500;
    }}
    QPushButton:hover {{ border: 1px solid {primary}; background: {selected}; }}
    QPushButton:pressed {{ background: {border}; }}
    QPushButton:disabled {{ color: {muted}; }}
    QComboBox::drop-down {{ border: none; width: 23px; }}
    QToolTip {{ background: {surface}; color: {fg}; border: 1px solid {primary}; padding: 6px; }}
    QStatusBar {{ color: {muted}; }}
    """
STYLE = make_style()
