"""The main HUD window."""

from __future__ import annotations

import html

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextBlockFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..core.assistant import Assistant, Event, State
from ..lang import HE, detect_language, is_rtl, ui_text
from .reactor import ArcReactor

STATE_KEY = {
    State.IDLE: "state_idle",
    State.LISTENING: "state_listening",
    State.THINKING: "state_thinking",
    State.SPEAKING: "state_speaking",
    State.OFFLINE: "state_offline",
}


def stylesheet(accent: str) -> str:
    return f"""
    QMainWindow, QWidget {{ background-color: #05080f; color: #cfefff; }}
    QLabel#title {{ color: {accent}; letter-spacing: 10px; font-size: 26px; font-weight: 600; }}
    QLabel#state {{ color: {accent}; font-size: 14px; }}
    QTextBrowser {{
        background-color: rgba(10, 20, 32, 210);
        border: 1px solid rgba(51, 214, 255, 70);
        border-radius: 10px;
        padding: 10px;
        font-size: 15px;
    }}
    QLineEdit {{
        background-color: rgba(10, 20, 32, 210);
        border: 1px solid rgba(51, 214, 255, 110);
        border-radius: 18px;
        padding: 10px 16px;
        color: #e6faff;
        font-size: 15px;
    }}
    QCheckBox {{ color: {accent}; font-size: 13px; }}
    """


class HudWindow(QMainWindow):
    event_received = pyqtSignal(object)

    def __init__(self, assistant: Assistant, speak: bool = True):
        super().__init__()
        self.assistant = assistant
        self.speak = speak
        self.language = assistant.language
        accent = assistant.config.get("ui.accent", "#33d6ff")

        self.setWindowTitle("J.A.R.V.I.S.")
        self.resize(760, 720)
        self.setStyleSheet(stylesheet(accent))
        if assistant.config.get("ui.always_on_top", False):
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowOpacity(float(assistant.config.get("ui.opacity", 0.97)))

        title = QLabel("J.A.R.V.I.S.")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.reactor = ArcReactor(accent)
        self.state_label = QLabel(ui_text("state_idle", self.language))
        self.state_label.setObjectName("state")
        self._set_state_font(self.language)
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.log = QTextBrowser()
        self.log.setOpenExternalLinks(True)
        self.log.setFont(QFont("Segoe UI", 11))

        self.input = QLineEdit()
        self.input.setPlaceholderText(ui_text("input_placeholder", self.language))
        self.input.returnPressed.connect(self._submit)

        self.mic_toggle = QCheckBox(ui_text("mic_on", self.language))
        self.mic_toggle.setChecked(assistant.voice_enabled)
        self.mic_toggle.toggled.connect(self._toggle_mic)

        controls = QHBoxLayout()
        controls.addWidget(self.input, 1)
        controls.addWidget(self.mic_toggle)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.reactor, 2)
        layout.addWidget(self.state_label)
        layout.addWidget(self.log, 3)
        layout.addLayout(controls)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.event_received.connect(self._on_event)
        assistant.listener = self.event_received.emit

    # -- UI events -----------------------------------------------------
    def _set_state_font(self, language: str) -> None:
        """Wide tracking looks great on Latin capitals but breaks Hebrew words."""
        font = self.state_label.font()
        spacing = 100.0 if language == HE else 130.0
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, spacing)
        self.state_label.setFont(font)

    def _submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        language = detect_language(text, default=self.language)
        self._retranslate(language)
        self.assistant.handle_text_async(text, language, speak=self.speak)

    def _toggle_mic(self, checked: bool) -> None:
        self.assistant.voice_enabled = checked
        self.mic_toggle.setText(ui_text("mic_on" if checked else "mic_off", self.language))

    def _retranslate(self, language: str) -> None:
        if language == self.language:
            return
        self.language = language
        self.input.setPlaceholderText(ui_text("input_placeholder", language))
        self.input.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if is_rtl(language) else Qt.LayoutDirection.LeftToRight
        )
        self.mic_toggle.setText(ui_text("mic_on" if self.mic_toggle.isChecked() else "mic_off", language))
        self._set_state_font(language)
        self.state_label.setText(ui_text(STATE_KEY.get(self.assistant.state, "state_idle"), language))

    def _on_event(self, event: Event) -> None:
        if event.kind == "state" and event.state is not None:
            self.reactor.set_state(event.state)
            self.state_label.setText(ui_text(STATE_KEY.get(event.state, "state_idle"), self.language))
            return
        if not event.text:
            return
        self._retranslate(event.language)
        accent = self.assistant.config.get("ui.accent", "#33d6ff")
        if event.kind == "user":
            speaker, color = ui_text("you", event.language), "#9fb8c8"
        else:
            speaker, color = "JARVIS", accent

        # Each line carries its own direction so Hebrew and English can be mixed freely.
        rtl = event.language == HE
        block = QTextBlockFormat()
        block.setLayoutDirection(Qt.LayoutDirection.RightToLeft if rtl else Qt.LayoutDirection.LeftToRight)
        block.setAlignment(Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft)
        block.setBottomMargin(6)

        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if not self.log.document().isEmpty():
            cursor.insertBlock(block)
        else:
            cursor.setBlockFormat(block)
        cursor.insertHtml(
            f'<span style="color:{color}; font-weight:600;">{html.escape(speaker)}:</span> '
            f'<span style="color:#dff6ff;">{html.escape(event.text)}</span>'
        )
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.assistant.stop()
        super().closeEvent(event)


def run_hud(assistant: Assistant, voice: bool = True, speak: bool = True) -> int:
    app = QApplication.instance() or QApplication([])
    assistant.voice_enabled = voice
    window = HudWindow(assistant, speak=speak)
    window.show()
    assistant.start(greet=speak)
    return app.exec()
