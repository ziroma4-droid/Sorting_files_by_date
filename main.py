#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сортировка файлов по дате создания/изменения.
Перемещает файлы в папки с названием даты (ГГГГ_ММ_ДД или ДД_ММ_ГГГГ).
"""

import shutil
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QCheckBox,
    QComboBox,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont


def get_file_date(file_path: Path, use_creation: bool = True) -> datetime:
    """Возвращает дату создания или изменения файла."""
    stat = file_path.stat()
    if use_creation and hasattr(stat, "st_birthtime"):
        try:
            return datetime.fromtimestamp(stat.st_birthtime)
        except (ValueError, OSError, AttributeError):
            pass
    return datetime.fromtimestamp(stat.st_mtime)


def collect_files(root: Path, include_subfolders: bool) -> list[Path]:
    """Собирает список файлов в папке (и опционально в подпапках)."""
    files = []
    if include_subfolders:
        for p in root.rglob("*"):
            if p.is_file():
                files.append(p)
    else:
        for p in root.iterdir():
            if p.is_file():
                files.append(p)
    return files


class Worker(QThread):
    """Поток для перемещения файлов без блокировки UI."""
    progress = Signal(int, int)  # current, total
    log = Signal(str)
    finished_success = Signal(str)
    finished_error = Signal(str)

    def __init__(self, root: Path, files: list[Path], folder_format: str):
        super().__init__()
        self.root = root
        self.files = files
        self.folder_format = folder_format  # "YYYY_MM_DD" or "DD_MM_YYYY"

    def run(self):
        try:
            total = len(self.files)
            moved = 0
            errors = []

            for i, file_path in enumerate(self.files):
                self.progress.emit(i + 1, total)

                try:
                    dt = get_file_date(file_path, use_creation=True)
                    if self.folder_format == "YYYY_MM_DD":
                        folder_name = dt.strftime("%Y_%m_%d")
                    else:  # DD_MM_YYYY
                        folder_name = dt.strftime("%d_%m_%Y")

                    dest_dir = self.root / folder_name
                    dest_dir.mkdir(parents=True, exist_ok=True)

                    dest_file = dest_dir / file_path.name
                    # если имя совпадает — добавляем суффикс
                    n = 1
                    while dest_file.exists():
                        stem = file_path.stem
                        suf = file_path.suffix
                        dest_file = dest_dir / f"{stem}_{n}{suf}"
                        n += 1

                    shutil.move(str(file_path), str(dest_file))
                    moved += 1
                    self.log.emit(f"Перемещён: {file_path.name} → {folder_name}/")
                except Exception as e:
                    errors.append(f"{file_path.name}: {e}")
                    self.log.emit(f"Ошибка {file_path.name}: {e}")

            report = f"Готово. Перемещено: {moved} из {total}."
            if errors:
                report += f" Ошибок: {len(errors)}."
            self.finished_success.emit(report)
        except Exception as e:
            self.finished_error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Сортировка файлов по дате")
        self.setMinimumWidth(520)
        self.setMinimumHeight(420)

        self.root_path: Path | None = None
        self.files_count = 0
        self.worker: Worker | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)

        # --- Выбор папки ---
        grp_folder = QGroupBox("Папка")
        grp_layout = QVBoxLayout(grp_folder)

        row = QHBoxLayout()
        self.btn_choose = QPushButton("Выбрать папку…")
        self.btn_choose.clicked.connect(self.choose_folder)
        row.addWidget(self.btn_choose)
        grp_layout.addLayout(row)

        self.label_path = QLabel("Папка не выбрана")
        self.label_path.setWordWrap(True)
        self.label_path.setStyleSheet("color: #666;")
        grp_layout.addWidget(self.label_path)

        self.label_count = QLabel("")
        self.label_count.setStyleSheet("font-weight: bold; color: #1976d2;")
        grp_layout.addWidget(self.label_count)

        self.check_subfolders = QCheckBox("Включая подпапки")
        self.check_subfolders.setChecked(False)
        self.check_subfolders.stateChanged.connect(self._recount_files)
        grp_layout.addWidget(self.check_subfolders)

        layout.addWidget(grp_folder)

        # --- Формат папки ---
        grp_format = QGroupBox("Формат имени папки")
        fmt_layout = QVBoxLayout(grp_format)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["ГГГГ_ММ_ДД (например 2025_01_27)", "ДД_ММ_ГГГГ (например 27_01_2025)"])
        fmt_layout.addWidget(self.combo_format)
        layout.addWidget(grp_format)

        # --- Переместить ---
        self.btn_move = QPushButton("Переместить файлы")
        self.btn_move.clicked.connect(self.start_move)
        self.btn_move.setEnabled(False)
        layout.addWidget(self.btn_move)

        # --- Прогресс ---
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        # --- Отчёт ---
        report_label = QLabel("Отчёт о выполнении:")
        layout.addWidget(report_label)
        self.report = QTextEdit()
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(140)
        self.report.setFont(QFont("Consolas", 9))
        layout.addWidget(self.report)

        layout.addStretch()
        self._recount_files()

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if path:
            self.root_path = Path(path)
            self.label_path.setText(str(self.root_path))
            self._recount_files()
            self.btn_move.setEnabled(self.files_count > 0)

    def _recount_files(self):
        if self.root_path is None or not self.root_path.is_dir():
            self.files_count = 0
            self.label_count.setText("")
            return
        include_sub = self.check_subfolders.isChecked()
        files = collect_files(self.root_path, include_sub)
        self.files_count = len(files)
        self.label_count.setText(f"Найдено файлов: {self.files_count}")
        self.btn_move.setEnabled(self.files_count > 0)

    def start_move(self):
        if not self.root_path or self.files_count == 0:
            return
        include_sub = self.check_subfolders.isChecked()
        files = collect_files(self.root_path, include_sub)
        fmt_index = self.combo_format.currentIndex()
        folder_format = "YYYY_MM_DD" if fmt_index == 0 else "DD_MM_YYYY"

        self.report.clear()
        self.report.append("Запуск перемещения…")
        self.progress.setValue(0)
        self.btn_move.setEnabled(False)
        self.btn_choose.setEnabled(False)
        self.check_subfolders.setEnabled(False)

        self.worker = Worker(self.root_path, files, folder_format)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._on_log)
        self.worker.finished_success.connect(self._on_finished)
        self.worker.finished_error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, current: int, total: int):
        if total > 0:
            self.progress.setValue(int(100 * current / total))

    def _on_log(self, text: str):
        self.report.append(text)

    def _on_finished(self, msg: str):
        self.progress.setValue(100)
        self.report.append("")
        self.report.append(msg)
        self.btn_move.setEnabled(True)
        self.btn_choose.setEnabled(True)
        self.check_subfolders.setEnabled(True)
        self._recount_files()
        QMessageBox.information(self, "Готово", msg)

    def _on_error(self, err: str):
        self.report.append(f"Ошибка: {err}")
        self.btn_move.setEnabled(True)
        self.btn_choose.setEnabled(True)
        self.check_subfolders.setEnabled(True)
        QMessageBox.critical(self, "Ошибка", err)


def main():
    app = QApplication([])
    app.setApplicationName("Сортировка файлов по дате")
    w = MainWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
