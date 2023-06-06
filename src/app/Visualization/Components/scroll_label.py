from collections import deque
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QVBoxLayout, QWidget, QScrollArea)

# Creates the scrolling list of live coordinates for display in the gui
class ScrollLabel(QScrollArea):
    def __init__(self, settings):
        QScrollArea.__init__(self)
        self.setWidgetResizable(True)
        self.content = QWidget(self)
        self.setWidget(self.content)

        # Set list length equal to coordinate deques
        self.lines = deque(maxlen=settings["queue_length"])

        # Main layout
        self.layout = QVBoxLayout(self.content)

        # Set main style
        self.setStyleSheet("background-color: rgba(255, 255, 255, 255); border: 1px solid #d3d3d3; border-top: none;")
        self.scroll_bar = self.verticalScrollBar()        
        
        # Create label
        self.label = QtWidgets.QLabel(self.content)

        # Set label layout
        self.label.setStyleSheet("background-color: rgba(255, 255, 255, 255); border: none; padding: 5px;")

        # Set text alignment
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # Make label multi-line
        self.label.setWordWrap(True)

        # Add label to layout
        self.layout.addWidget(self.label)

        # Set scrollbar styles
        self.scroll_bar.setStyleSheet("""
            QScrollBar:vertical {
                background-color: rgba(255, 255, 255, 255);
                width: 10px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: lightgray;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical {
                height: 0px;
                subcontrol-position: bottom;
                subcontrol-origin: margin;
            }
            QScrollBar::sub-line:vertical {
                height: 0px;
                subcontrol-position: top;
                subcontrol-origin: margin;
            }
        """)

    # Update the text in the scroll box
    def setText(self, text):
        self.lines.append(text)
        self.label.setText('\n'.join(self.lines))
        scroll_bar = self.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())  