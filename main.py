#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сортировка файлов по дате создания/изменения.
Перемещает файлы в папки с названием даты (ГГГГ_ММ_ДД или ДД_ММ_ГГГГ).
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Путь к плагинам Qt при запуске из exe (PyInstaller)
if getattr(sys, "frozen", False):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for sub in ("PySide6/plugins/platforms", "PySide6/plugins", "platforms"):
        plugin_path = os.path.join(base, sub)
        if os.path.isdir(plugin_path):
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path
            break

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


def get_size_folder_name(size_bytes: int) -> str:
    """Возвращает имя подпапки по размеру: «1 КБ», «10 МБ», «1 ГБ» и т.д."""
    if size_bytes < 1024:
        return "< 1 КБ"
    for divisor, name in [(1024**3, "ГБ"), (1024**2, "МБ"), (1024, "КБ")]:
        if size_bytes >= divisor:
            n = size_bytes / divisor
            if n >= 100:
                bucket = int(n // 100) * 100
            elif n >= 10:
                bucket = int(n // 10) * 10
            elif n >= 1:
                bucket = 1
            else:
                bucket = 1
            return f"{int(bucket)} {name}"
    return "< 1 КБ"


def _unique_dest_path(dest_dir: Path, stem: str, suffix: str) -> Path:
    """Возвращает путь к файлу без конфликта; при дубликатах добавляет _001, _002, …
    Гарантирует, что возвращаемый путь не существует (никакой файл не будет перезаписан).
    """
    candidate = dest_dir / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate
    n = 1
    while True:
        candidate = dest_dir / f"{stem}_{n:03d}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def _same_path(p1: Path, p2: Path) -> bool:
    """Проверяет, ссылаются ли пути на один и тот же файл."""
    try:
        return p1.resolve() == p2.resolve()
    except (OSError, RuntimeError):
        return False


def remove_empty_dirs(root: Path) -> int:
    """Удаляет пустые папки внутри root (саму root не трогает). Возвращает количество удалённых."""
    removed = 0
    while True:
        dirs = [p for p in root.rglob("*") if p.is_dir()]
        dirs.sort(key=lambda p: len(p.parts), reverse=True)
        removed_any = False
        for d in dirs:
            try:
                if not any(d.iterdir()):
                    d.rmdir()
                    removed += 1
                    removed_any = True
            except OSError:
                pass
        if not removed_any:
            break
    return removed


class Worker(QThread):
    """Поток для перемещения файлов без блокировки UI."""
    progress = Signal(int, int)  # current, total
    log = Signal(str)
    finished_success = Signal(str)
    finished_error = Signal(str)

    def __init__(
        self,
        root: Path,
        files: list[Path],
        folder_format: str,
        sort_by_extension: bool = False,
        sort_by_size: bool = False,
        delete_empty_dirs: bool = False,
    ):
        super().__init__()
        self.root = root
        self.files = files
        self.folder_format = folder_format  # "YYYY_MM_DD" or "DD_MM_YYYY"
        self.sort_by_extension = sort_by_extension
        self.sort_by_size = sort_by_size
        self.delete_empty_dirs = delete_empty_dirs

    def run(self):
        try:
            total = len(self.files)
            moved = 0
            skipped = 0
            errors = []

            for i, file_path in enumerate(self.files):
                self.progress.emit(i + 1, total)

                try:
                    # Источник должен существовать; при сомнении — пропуск, файл не трогаем
                    if not file_path.exists():
                        self.log.emit(f"Пропущен (файл не найден): {file_path.name}")
                        skipped += 1
                        continue

                    dt = get_file_date(file_path, use_creation=True)
                    if self.folder_format == "YYYY_MM_DD":
                        folder_name = dt.strftime("%Y_%m_%d")
                    else:  # DD_MM_YYYY
                        folder_name = dt.strftime("%d_%m_%Y")

                    dest_dir = self.root / folder_name

                    if self.sort_by_extension:
                        ext = (file_path.suffix or "").upper().lstrip(".")
                        ext = ext if ext else "без расширения"
                        dest_dir = dest_dir / ext

                    if self.sort_by_size:
                        size_bytes = file_path.stat().st_size
                        size_label = get_size_folder_name(size_bytes)
                        dest_dir = dest_dir / size_label

                    dest_dir.mkdir(parents=True, exist_ok=True)

                    stem, suf = file_path.stem, file_path.suffix
                    dest_file = _unique_dest_path(dest_dir, stem, suf)

                    # Файл уже в нужном месте — не двигаем, ничего не удаляем
                    if _same_path(file_path, dest_file):
                        self.log.emit(f"Пропущен (уже на месте): {file_path.name}")
                        skipped += 1
                        continue

                    # Перед переносом убеждаемся, что цель свободна
                    # (никогда не перезаписываем существующие файлы)
                    skip_this = False
                    for _ in range(1000):
                        if not dest_file.exists():
                            break
                        if _same_path(file_path, dest_file):
                            self.log.emit(f"Пропущен (уже на месте): {file_path.name}")
                            skipped += 1
                            skip_this = True
                            break
                        dest_file = _unique_dest_path(dest_dir, stem, suf)
                    else:
                        self.log.emit(
                            f"Пропущен (не удалось подобрать свободное имя): {file_path.name}"
                        )
                        skipped += 1
                        skip_this = True

                    if skip_this:
                        continue

                    if _same_path(file_path, dest_file):
                        self.log.emit(f"Пропущен (уже на месте): {file_path.name}")
                        skipped += 1
                        continue

                    try:
                        rel_log = str(dest_file.relative_to(self.root))
                    except ValueError:
                        rel_log = f"{folder_name}/{dest_file.name}"

                    # Только перемещение; удаление не выполняется — move переименовывает
                    shutil.move(str(file_path), str(dest_file))
                    moved += 1
                    self.log.emit(f"Перемещён: {file_path.name} → {rel_log}")
                except Exception as e:
                    errors.append(f"{file_path.name}: {e}")
                    self.log.emit(f"Ошибка (файл оставлен на месте): {file_path.name} — {e}")

            report = f"Готово. Перемещено: {moved} из {total}."
            if skipped:
                report += f" Пропущено: {skipped}."
            if errors:
                report += f" Ошибок: {len(errors)} (файлы не удалены)."
            if self.delete_empty_dirs:
                n_removed = remove_empty_dirs(self.root)
                if n_removed:
                    report += f" Удалено пустых папок: {n_removed}."
                    self.log.emit(f"Удалено пустых папок: {n_removed}")
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

        # --- Сортировка внутри папки с датой ---
        grp_inner = QGroupBox("Сортировка внутри папки с датой")
        inner_layout = QVBoxLayout(grp_inner)
        self.check_by_extension = QCheckBox("По расширению файлов (JPG, PNG, …)")
        self.check_by_extension.setChecked(False)
        inner_layout.addWidget(self.check_by_extension)
        self.check_by_size = QCheckBox("По размеру файлов (1 МБ, 10 МБ, 1 ГБ, …)")
        self.check_by_size.setChecked(False)
        inner_layout.addWidget(self.check_by_size)
        layout.addWidget(grp_inner)

        # --- После перемещения ---
        self.check_delete_empty = QCheckBox("Удалить пустые папки")
        self.check_delete_empty.setChecked(True)
        self.check_delete_empty.setToolTip("Удалить папки, из которых были перемещены все файлы")
        layout.addWidget(self.check_delete_empty)

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

        n = len(files)
        msg = (
            f"Будет обработано файлов: {n}.\n\n"
            "Файлы только перемещаются в папки по датам, ни один файл не удаляется. "
            "При совпадении имён добавляется суффикс _001, _002 и т.д. "
            "Существующие файлы в папках назначения не перезаписываются.\n\n"
            "Продолжить?"
        )
        r = QMessageBox.question(
            self,
            "Подтверждение",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return

        self.report.clear()
        self.report.append("Запуск перемещения…")
        self.progress.setValue(0)
        self.btn_move.setEnabled(False)
        self.btn_choose.setEnabled(False)
        self.check_subfolders.setEnabled(False)
        self.check_by_extension.setEnabled(False)
        self.check_by_size.setEnabled(False)
        self.check_delete_empty.setEnabled(False)

        sort_ext = self.check_by_extension.isChecked()
        sort_size = self.check_by_size.isChecked()
        delete_empty = self.check_delete_empty.isChecked()
        self.worker = Worker(
            self.root_path,
            files,
            folder_format,
            sort_by_extension=sort_ext,
            sort_by_size=sort_size,
            delete_empty_dirs=delete_empty,
        )
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
        self.check_by_extension.setEnabled(True)
        self.check_by_size.setEnabled(True)
        self.check_delete_empty.setEnabled(True)
        self._recount_files()
        QMessageBox.information(self, "Готово", msg)

    def _on_error(self, err: str):
        self.report.append(f"Ошибка: {err}")
        self.btn_move.setEnabled(True)
        self.btn_choose.setEnabled(True)
        self.check_subfolders.setEnabled(True)
        self.check_by_extension.setEnabled(True)
        self.check_by_size.setEnabled(True)
        self.check_delete_empty.setEnabled(True)
        QMessageBox.critical(self, "Ошибка", err)


def main():
    app = QApplication([])
    app.setApplicationName("Сортировка файлов по дате (beta)")
    w = MainWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
