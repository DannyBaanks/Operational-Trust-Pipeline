"""OTP GUI — control room interface for the Operational Trust Pipeline."""
from __future__ import annotations

__version__ = "0.1.0"


def main() -> None:
    """Launch the OTP GUI. Requires PySide6."""
    import sys
    from PySide6.QtWidgets import QApplication
    from .styles import apply_dark_theme
    from .main_window import MainWindow

    app = QApplication(sys.argv)
    apply_dark_theme(app)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())
