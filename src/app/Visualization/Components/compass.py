import math
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

# Compass widget draws the compass icon, populates the heading label, and controls the rotation of the compass by redrawing itself in a new position when its rotate_triangle class method is called with updated heading data.
class Compass(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(150, 180)
        self.setStyleSheet("background-color: rgba(240, 240, 240, 0);")
        self.radius = 50
        self.canvas_middle = [self.width() / 2, ((self.height()-30) / 2)]
        self.triangle = QtGui.QPolygonF([
            QtCore.QPointF(self.canvas_middle[0], self.canvas_middle[1] - 30),
            QtCore.QPointF(self.canvas_middle[0] - 20, self.canvas_middle[1] + 25),
            QtCore.QPointF(self.canvas_middle[0], self.canvas_middle[1] + 15),
            QtCore.QPointF(self.canvas_middle[0] + 20, self.canvas_middle[1] + 25)
        ])

        # Store the original vertices to be used as the base for in every rotation calculation (prevents rounding error accumulation)
        self.original_vertices = [self.triangle.at(i) for i in range(self.triangle.size())]

        # heading label
        self.radians_label = QtWidgets.QLabel(self)
        self.radians_label.setAlignment(QtCore.Qt.AlignCenter)
        self.radians_label.setGeometry(0, 150, 150, 20)
        self.radians_label.setText("0.0")

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor("#FFCE00"), 5))
        painter.setBrush(QtGui.QBrush(QtGui.QColor("#FFB300")))
        painter.drawEllipse(25, 25, 100, 100)
        painter.setPen(QtGui.QPen(QtGui.QColor("#333333")))
        painter.setBrush(QtGui.QBrush(QtGui.QColor("#333333")))
        painter.drawPolygon(self.triangle)

    def rotate_triangle(self, radians):
        display = ((radians + math.pi/2) % (2*math.pi)) * (180/math.pi)
        self.radians_label.setText(f"Heading: {display:.2f}\u00B0")
        # Calculate the sine and cosine of the angle
        cosine = np.cos(radians)
        sine = np.sin(radians)
        # Translate vertices to the origin
        translated_vertices = [(p.x() - self.canvas_middle[0], p.y() - self.canvas_middle[1]) for p in self.original_vertices]
        # Rotate vertices about the origin
        rotated_vertices = [(p[0]*cosine + p[1]*sine, p[1]*cosine - p[0]*sine) for p in translated_vertices]
        # Translate vertices back to the original position
        new_vertices = [(p[0] + self.canvas_middle[0], p[1] + self.canvas_middle[1]) for p in rotated_vertices]
        # Update the triangle's vertices and repaint the canvas
        self.triangle = QtGui.QPolygonF([QtCore.QPointF(*p) for p in new_vertices])
        self.update()