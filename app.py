import sys
from contextlib import nullcontext

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import task_scheduler as ts


class StreamRedirector:
    def __init__(self, text_widget: QTextEdit):
        self.text_widget = text_widget

    def write(self, text: str) -> None:
        if not text:
            return
        self.text_widget.moveCursor(self.text_widget.textCursor().End)
        self.text_widget.insertPlainText(text)
        self.text_widget.ensureCursorVisible()

    def flush(self) -> None:
        pass


class SchedulerApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.scheduler = ts.Scheduler()
        self.task_counter = 0
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("Task Scheduler")
        self.setMinimumSize(600, 700)

        root = QVBoxLayout()
        self.setLayout(root)

        form_group = QGroupBox("Task Parameters")
        self.form = QFormLayout()
        form_group.setLayout(self.form)
        root.addWidget(form_group)

        self.task_type = QComboBox()
        self.task_type.addItems(["DeadlineTask", "PeriodicTask", "OverdueTask"])
        self.task_type.currentTextChanged.connect(self.update_fields)

        self.task_text = QLineEdit()
        self.assignee = QLineEdit()

        self.priority = QSpinBox()
        self.priority.setRange(1, 10)
        self.priority.setValue(5)

        self.duration = QSpinBox()
        self.duration.setRange(1, 1_000_000)
        self.duration.setValue(60)

        self.deadline = QSpinBox()
        self.deadline.setRange(0, 1_000_000)
        self.deadline.setValue(120)

        self.start_time = QSpinBox()
        self.start_time.setRange(0, 1_000_000)
        self.start_time.setValue(0)

        self.period = QSpinBox()
        self.period.setRange(1, 1_000_000)
        self.period.setValue(30)

        self.form.addRow("Task type", self.task_type)
        self.form.addRow("Text", self.task_text)
        self.form.addRow("Assignee", self.assignee)
        self.form.addRow("Priority (1-10)", self.priority)
        self.form.addRow("Duration (sec)", self.duration)
        self.form.addRow("Deadline (sec)", self.deadline)
        self.form.addRow("Start (sec)", self.start_time)
        self.form.addRow("Period (sec)", self.period)

        self.buttons_layout = QHBoxLayout()
        root.addLayout(self.buttons_layout)

        add_button = QPushButton("ADD TASK")
        add_button.clicked.connect(self.add_task)
        self.buttons_layout.addWidget(add_button)

        show_button = QPushButton("SHOW PLAN")
        show_button.clicked.connect(self.show_plan)
        self.buttons_layout.addWidget(show_button)

        run_next_button = QPushButton("RUN NEXT")
        run_next_button.clicked.connect(self.run_next)
        self.buttons_layout.addWidget(run_next_button)

        run_all_button = QPushButton("RUN ALL")
        run_all_button.clicked.connect(self.run_all)
        self.buttons_layout.addWidget(run_all_button)

        root.addWidget(QLabel("Output Console"))

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setLineWrapMode(QTextEdit.NoWrap)
        root.addWidget(self.console, stretch=1)

        self.redirector = StreamRedirector(self.console)
        self.update_fields()

    def _redirect_context(self):
        if hasattr(ts, "ostream_redirect"):
            return ts.ostream_redirect(stdout=True, stderr=True, target=self.redirector)
        return nullcontext()

    def update_fields(self) -> None:
        task_type = self.task_type.currentText()
        self._set_form_row_visible(self.deadline, task_type == "DeadlineTask")
        self._set_form_row_visible(self.start_time, task_type == "PeriodicTask")
        self._set_form_row_visible(self.period, task_type == "PeriodicTask")

    def _set_form_row_visible(self, field_widget, visible: bool) -> None:
        field_widget.setVisible(visible)
        label = self.form.labelForField(field_widget)
        if label is not None:
            label.setVisible(visible)

    def _validate_common_inputs(self) -> tuple[str, str, int, int]:
        text = self.task_text.text().strip()
        assignee = self.assignee.text().strip()
        if not text:
            raise ValueError("Field 'Text' is required")
        if not assignee:
            raise ValueError("Field 'Assignee' is required")
        return text, assignee, self.priority.value(), self.duration.value()

    def add_task(self) -> None:
        try:
            text, assignee, priority, duration = self._validate_common_inputs()
            task_type = self.task_type.currentText()
            task_id = self.task_counter

            if task_type == "DeadlineTask":
                self.scheduler.addDeadlineTask(
                    task_id, text, assignee, priority, duration, self.deadline.value()
                )
            elif task_type == "PeriodicTask":
                self.scheduler.addPeriodicTask(
                    task_id,
                    text,
                    assignee,
                    priority,
                    duration,
                    self.start_time.value(),
                    self.period.value(),
                )
            elif task_type == "OverdueTask":
                self.scheduler.addOverdueTask(task_id, text, assignee, priority, duration)
            else:
                raise ValueError(f"Unknown task type: {task_type}")

            self.task_counter += 1
            self.console.append(f"Task created: ID={task_id}, type={task_type}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _run_with_redirect(self, callback) -> None:
        self.console.clear()
        try:
            with self._redirect_context():
                callback()
        except Exception as exc:
            QMessageBox.critical(self, "Execution error", str(exc))

    def show_plan(self) -> None:
        self._run_with_redirect(self.scheduler.displayPlan)

    def run_next(self) -> None:
        self._run_with_redirect(self.scheduler.executeNext)

    def run_all(self) -> None:
        # For periodic tasks run() may be infinite, so keep a safety step limit.
        self._run_with_redirect(lambda: self.scheduler.run(max_steps=500))


def main() -> int:
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    window = SchedulerApp()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
