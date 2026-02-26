from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtCore import (
    Qt, 
    QPropertyAnimation, 
    pyqtProperty, 
    QRectF, 
    QSize
)
from PyQt6.QtGui import QPainter, QColor


class Switch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(50, 26)

        self._offset = 3
        self._radius = 10
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(180)

        self._bg_off = QColor("#bdc3c7")
        self._bg_on = QColor("#2ecc71")
        self._circle_color = QColor("white")

        self.toggled.connect(self.start_transition)
        self.setTristate(False)
        self.setText("")

    # Taille recommandée
    def sizeHint(self):
        return QSize(50, 26)

    # Animation
    def start_transition(self, checked):
        self._animation.stop()

        start = self._offset
        end = self.width() - self._radius*2 - 3 if checked else 3

        self._animation.setStartValue(start)
        self._animation.setEndValue(end)
        self._animation.start()

    # Dessin
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        if self.isChecked():
            painter.setBrush(self._bg_on)
        else:
            painter.setBrush(self._bg_off)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            0, 0,
            self.width(),
            self.height(),
            self.height() / 2,
            self.height() / 2
        )

        # Cercle
        painter.setBrush(self._circle_color)
        painter.drawEllipse(
            QRectF(
                self._offset,
                (self.height() - self._radius*2)/2,
                self._radius*2,
                self._radius*2
            )
        )

    # Property animable
    def get_offset(self):
        return self._offset
    

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self.isChecked())
        super().mouseReleaseEvent(event)

    def set_offset(self, value):
        self._offset = value
        self.update()

    offset = pyqtProperty(float, get_offset, set_offset)