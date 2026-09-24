from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from estimate_app.database.connection import connect, initialise
from estimate_app.database.projects import ProjectRepository
from estimate_app.interface.main_window import MainWindow


def run() -> int:
    connection = connect()
    initialise(connection)
    application = QApplication(sys.argv)
    window = MainWindow(ProjectRepository(connection))
    window.show()
    result = application.exec()
    connection.close()
    return result


if __name__ == "__main__":
    raise SystemExit(run())
