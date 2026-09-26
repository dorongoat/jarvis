"""Animated arc-reactor widget: three rotating rings plus a live audio-ish pulse."""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QWidget

from ..core.assistant import State

STATE_INTENSITY = {
    State.IDLE: 0.45,
    State.LISTENING: 1.0,
    State.THINKING: 0.8,
    State.SPEAKING: 0.95,
    State.OFFLINE: 0.2,
}


class ArcReactor(QWidget):
    def __init__(self, accent: str = "#33d6ff", parent: QWidget | None = None):
        super().__init__(parent)
        self.accent = QColor(accent)
        self.state = State.IDLE
        self._phase = 0.0
        self.setMinimumSize(220, 220)
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(33)

    def set_state(self, state: State) -> None:
        self.state = state
        self.update()

    def _tick(self) -> None:
        speed = 2.2 if self.state in (State.THINKING, State.LISTENING) else 1.0
        self._phase = (self._phase + 0.02 * speed) % (math.pi * 2)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height())
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = side / 2 - 8
        intensity = STATE_INTENSITY.get(self.state, 0.5)
        pulse = 0.5 + 0.5 * math.sin(self._phase * 2)
        color = QColor(self.accent)
        color.setAlphaF(min(1.0, 0.35 + 0.65 * intensity))

        glow = QRadialGradient(center, radius)
        glow.setColorAt(0.0, QColor(self.accent.red(), self.accent.green(), self.accent.blue(),
                                    int(120 * intensity * (0.7 + 0.3 * pulse))))
        glow.setColorAt(0.55, QColor(self.accent.red(), self.accent.green(), self.accent.blue(), 35))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, radius, radius)

        # Rotating dashed rings.
        for index, (scale, span, direction) in enumerate(((0.95, 300, 1), (0.78, 210, -1), (0.6, 140, 1))):
            pen = QPen(color, 2.0 + index * 0.6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            ring = radius * scale
            rect = QRectF(center.x() - ring, center.y() - ring, ring * 2, ring * 2)
            start = int((math.degrees(self._phase) * direction * (1 + index * 0.4)) % 360) * 16
            painter.drawArc(rect, start, span * 16)

        # Segmented core.
        segments = 12
        core = radius * 0.42
        pen = QPen(color, 4)
        painter.setPen(pen)
        for index in range(segments):
            angle = (2 * math.pi * index / segments) + self._phase * 0.5
            inner = QPointF(
                center.x() + math.cos(angle) * core * 0.72,
                center.y() + math.sin(angle) * core * 0.72,
            )
            outer = QPointF(center.x() + math.cos(angle) * core, center.y() + math.sin(angle) * core)
            painter.drawLine(inner, outer)

        center_color = QColor(self.accent)
        center_color.setAlphaF(0.25 + 0.6 * intensity * (0.6 + 0.4 * pulse))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(center_color)
        painter.drawEllipse(center, core * 0.55, core * 0.55)
        painter.end()
