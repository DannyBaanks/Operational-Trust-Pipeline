"""Dark theme and color palette for OTP control room UI."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette, QFont
from PySide6.QtWidgets import QApplication


class C:
    """Color constants. Rigid semantics — never repurpose."""
    BG = "#0f1218"
    SURFACE = "#161b22"
    SURFACE_RAISED = "#1c2128"
    BORDER = "#21262d"
    BORDER_LIGHT = "#30363d"
    TEXT = "#e6edf3"
    TEXT_DIM = "#8b949e"
    RED = "#da3633"
    ORANGE = "#f0883e"
    GREEN = "#3fb950"
    GRAY = "#8b949e"
    BLUE = "#58a6ff"
    SELECTION = "#1f3a5f"


FONTS = {
    "mono": "Consolas",
    "sans": "Segoe UI",
}


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(C.BG))
    p.setColor(QPalette.ColorRole.WindowText, QColor(C.TEXT))
    p.setColor(QPalette.ColorRole.Base, QColor(C.SURFACE))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(C.SURFACE_RAISED))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(C.SURFACE))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(C.TEXT))
    p.setColor(QPalette.ColorRole.Text, QColor(C.TEXT))
    p.setColor(QPalette.ColorRole.Button, QColor(C.SURFACE))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(C.TEXT))
    p.setColor(QPalette.ColorRole.BrightText, QColor(C.RED))
    p.setColor(QPalette.ColorRole.Link, QColor(C.BLUE))
    p.setColor(QPalette.ColorRole.Highlight, QColor(C.SELECTION))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(C.TEXT))
    app.setPalette(p)

    font = QFont(FONTS["sans"], 9)
    app.setFont(font)

    app.setStyleSheet(f"""
        QMainWindow {{ background: {C.BG}; }}
        QWidget {{ background: {C.BG}; color: {C.TEXT}; }}
        QTableView {{
            background: {C.SURFACE};
            alternate-background-color: {C.SURFACE_RAISED};
            border: 1px solid {C.BORDER};
            gridline-color: {C.BORDER};
            selection-background-color: {C.SELECTION};
            selection-color: {C.TEXT};
            font-size: 12px;
        }}
        QTableView::item {{ padding: 4px 8px; }}
        QHeaderView::section {{
            background: {C.SURFACE_RAISED};
            color: {C.TEXT_DIM};
            border: none;
            border-bottom: 1px solid {C.BORDER};
            padding: 6px 8px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        QSplitter::handle {{ background: {C.BORDER}; height: 1px; }}
        QFrame#card {{
            background: {C.SURFACE};
            border: 1px solid {C.BORDER};
            border-radius: 4px;
        }}
        QLabel {{ color: {C.TEXT}; }}
        QLabel[dim="true"] {{ color: {C.TEXT_DIM}; }}
        QLabel[heading="true"] {{
            color: {C.TEXT_DIM};
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        QPushButton {{
            background: {C.SURFACE_RAISED};
            color: {C.TEXT};
            border: 1px solid {C.BORDER_LIGHT};
            border-radius: 4px;
            padding: 6px 16px;
            font-size: 12px;
        }}
        QPushButton:hover {{ background: {C.BORDER_LIGHT}; }}
        QPushButton:pressed {{ background: {C.SELECTION}; }}
        QPushButton#primary {{
            background: {C.ORANGE};
            color: #000;
            border: none;
            font-weight: bold;
        }}
        QPushButton#primary:hover {{ background: #ff9a47; }}
        QPushButton#danger {{
            background: {C.RED};
            color: #fff;
            border: none;
        }}
        QLineEdit {{
            background: {C.SURFACE_RAISED};
            color: {C.TEXT};
            border: 1px solid {C.BORDER_LIGHT};
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 12px;
        }}
        QStatusBar {{
            background: {C.SURFACE_RAISED};
            color: {C.TEXT_DIM};
            border-top: 1px solid {C.BORDER};
            font-size: 11px;
        }}
        QMenuBar {{
            background: {C.SURFACE_RAISED};
            color: {C.TEXT};
            border-bottom: 1px solid {C.BORDER};
        }}
        QMenuBar::item:selected {{ background: {C.SELECTION}; }}
        QMenu {{
            background: {C.SURFACE};
            color: {C.TEXT};
            border: 1px solid {C.BORDER_LIGHT};
        }}
        QMenu::item:selected {{ background: {C.SELECTION}; }}
        QDialog {{
            background: {C.BG};
        }}
        QScrollBar:vertical {{
            background: {C.SURFACE};
            width: 8px;
        }}
        QScrollBar::handle:vertical {{
            background: {C.BORDER_LIGHT};
            border-radius: 4px;
            min-height: 20px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    """)
