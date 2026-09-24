from __future__ import annotations

import sqlite3

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from estimate_app.database.projects import Project, ProjectRepository


class MainWindow(QMainWindow):
    def __init__(self, repository: ProjectRepository) -> None:
        super().__init__()
        self.repository = repository
        self.current_project_id: int | None = None
        self.setWindowTitle("Building Estimate — CPWD DSR 2023")
        self.resize(1000, 620)
        self.setStatusBar(QStatusBar(self))
        self._build_ui()
        self._load_projects()
        self._new_project()

    def _build_ui(self) -> None:
        self.project_list = QListWidget()
        self.project_list.currentItemChanged.connect(self._open_project)

        new_button = QPushButton("New Project")
        new_button.clicked.connect(self._new_project)
        list_layout = QVBoxLayout()
        list_layout.addWidget(QLabel("Projects"))
        list_layout.addWidget(self.project_list)
        list_layout.addWidget(new_button)
        list_panel = QWidget()
        list_panel.setLayout(list_layout)

        self.project_name = QLineEdit()
        self.scheme_id = QLineEdit()
        self.location = QLineEdit()
        self.client_department = QLineEdit()
        self.estimate_date = self._date_edit()
        self.cutoff_date = self._date_edit()

        form = QFormLayout()
        form.addRow("Project / scheme name", self.project_name)
        form.addRow("Scheme ID", self.scheme_id)
        form.addRow("Location", self.location)
        form.addRow("Client / department", self.client_department)
        form.addRow("Estimate date", self.estimate_date)
        form.addRow("Correction-slip cutoff date", self.cutoff_date)
        save_button = QPushButton("Save Project")
        save_button.clicked.connect(self._save_project)
        form.addRow(save_button)

        form_panel = QWidget()
        form_panel.setLayout(form)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(list_panel)
        splitter.addWidget(form_panel)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

    @staticmethod
    def _date_edit() -> QDateEdit:
        field = QDateEdit()
        field.setCalendarPopup(True)
        field.setDisplayFormat("yyyy-MM-dd")
        field.setDate(QDate.currentDate())
        return field

    def _load_projects(self) -> None:
        self.project_list.clear()
        for project in self.repository.list_projects():
            item = QListWidgetItem(project.project_name)
            item.setData(Qt.ItemDataRole.UserRole, project.id)
            self.project_list.addItem(item)

    def _new_project(self) -> None:
        self.current_project_id = None
        for field in (
            self.project_name,
            self.scheme_id,
            self.location,
            self.client_department,
        ):
            field.clear()
        today = QDate.currentDate()
        self.estimate_date.setDate(today)
        self.cutoff_date.setDate(today)
        self.project_list.clearSelection()
        self.statusBar().showMessage("New project")

    def _open_project(self, item: QListWidgetItem | None, _: QListWidgetItem | None) -> None:
        if item is None:
            return
        project_id = item.data(Qt.ItemDataRole.UserRole)
        project = self.repository.get(project_id)
        if project is None:
            return
        self.current_project_id = project.id
        self.project_name.setText(project.project_name)
        self.scheme_id.setText(project.scheme_id)
        self.location.setText(project.location)
        self.client_department.setText(project.client_department)
        self.estimate_date.setDate(QDate.fromString(project.estimate_date, Qt.DateFormat.ISODate))
        self.cutoff_date.setDate(QDate.fromString(project.correction_slip_cutoff_date, Qt.DateFormat.ISODate))

    def _save_project(self) -> None:
        fields = {
            "Project / scheme name": self.project_name.text().strip(),
            "Scheme ID": self.scheme_id.text().strip(),
            "Location": self.location.text().strip(),
            "Client / department": self.client_department.text().strip(),
        }
        missing = [label for label, value in fields.items() if not value]
        if missing:
            QMessageBox.warning(self, "Incomplete project", "Enter: " + ", ".join(missing))
            return
        estimate_date = self.estimate_date.date()
        cutoff_date = self.cutoff_date.date()
        if not estimate_date.isValid() or not cutoff_date.isValid():
            QMessageBox.warning(self, "Invalid dates", "Enter valid project dates.")
            return
        if cutoff_date > estimate_date:
            QMessageBox.warning(
                self,
                "Invalid dates",
                "Correction-slip cutoff date cannot be after the estimate date.",
            )
            return
        try:
            project = self.repository.save(
                Project(
                    id=self.current_project_id,
                    project_name=fields["Project / scheme name"],
                    scheme_id=fields["Scheme ID"],
                    location=fields["Location"],
                    client_department=fields["Client / department"],
                    estimate_date=self._date_value(self.estimate_date),
                    correction_slip_cutoff_date=self._date_value(self.cutoff_date),
                )
            )
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Database error", f"Project could not be saved: {error}")
            return
        self.current_project_id = project.id
        self._load_projects()
        self._select_project(project.id)
        self.statusBar().showMessage("Project saved")

    @staticmethod
    def _date_value(field: QDateEdit) -> str:
        return field.date().toString(Qt.DateFormat.ISODate)

    def _select_project(self, project_id: int | None) -> None:
        for index in range(self.project_list.count()):
            item = self.project_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == project_id:
                self.project_list.setCurrentItem(item)
                return
