import json
import os
import paho.mqtt.publish as publish
from paho.mqtt.client import MQTTv5
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QLabel, QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget)
from app.lib.message_handler import Handler
from app.Visualization.Components.graph import Graph
from app.Visualization.Components.scroll_label import ScrollLabel
from app.Visualization.Components.compass import Compass

# PlotterGUI creates the main PyQt GUI window, controls the general layout and any nested layouts within the GUI, receives data from the message broker, and uses said data to animate the embedded PyQtgraph
class PlotterGUI(QWidget):
    def __init__(self, settings):
        super().__init__()

        self.settings = settings
        self.showFullScreen()
        
        # Customize window title
        self.setWindowTitle(settings["gui_title"])

        # Customize window icon
        icon_path = "./app/Visualization/Assets/Virginia_Commonwealth_University_Logo.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))

        self.counter = 0
        self.last_heading = 0
        self.heading = 0
        self.closeEvent = self.on_close

        # Create sidebar frame
        self.side_bar = QFrame()
        self.side_bar.setStyleSheet("margin: 0")

        # Create scrolling textbox and header
        self.scroll_header = QtWidgets.QLabel()
        self.scroll_header.setStyleSheet("border: 2px solid #d3d3d3; padding: 5px 15px;")
        self.scroll_header.setText('x (cm),   y (cm)')
        self.scroll = ScrollLabel(settings)

        # Reset button widget
        self.reset_button = QPushButton("Reset", self)
        self.reset_button.clicked.connect(self.reset)
        self.reset_button.setStyleSheet("""
            QPushButton {
                background-color: lightgray;
                border: none;
                padding: 6px;
            }            
            QPushButton:hover {
                background-color: gray;
            }
        """)

        # Create graph
        self.graph = Graph(settings)

        # Create compass
        self.compass = Compass()

        # Create a container for the compass (used for centering)
        self.compass_layout = QHBoxLayout()
        self.compass_layout.addStretch()
        self.compass_layout.addWidget(self.compass)
        self.compass_layout.addStretch()

        # Add & scale VCU logo
        self.image_label = QLabel()
        self.image_label.setStyleSheet("padding-bottom: 10px;")
        logo_path = "./app/Visualization/Assets/bm_CollegeOfEngin_RF_st_4c.png"
        if os.path.exists(logo_path):
            self.setWindowIcon(QtGui.QIcon(logo_path))
            image = QtGui.QPixmap(logo_path)
            scaled_image = image.scaledToWidth(240, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_image)

        # Make a layout for the textbox, compass, reset button, ...
        self.sidebar_layout = QVBoxLayout()        
        self.sidebar_layout.setSpacing(0)
        self.sidebar_layout.addWidget(self.image_label)
        self.sidebar_layout.addWidget(self.scroll_header)
        self.sidebar_layout.addWidget(self.scroll)
        self.sidebar_layout.addLayout(self.compass_layout)
        self.sidebar_layout.addWidget(self.reset_button)
        self.sidebar_layout.setAlignment(Qt.AlignVCenter)
        self.side_bar.setLayout(self.sidebar_layout)

        # Add frame to main layout
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.graph)
        self.layout.addWidget(self.side_bar)

        # Set position and size of text frame and textbox
        self.frame_width = 275
        self.side_bar.setMaximumWidth(self.frame_width)
        self.side_bar.setMinimumWidth(self.frame_width)

        # Set up MQTT client
        self.handler = Handler(client_id='gui', topic_sub=settings["topic_sub"], host=settings["broker_host"], port=settings["port"], qos=0)
        self.handler.client.message_callback_add(settings["topic_sub"], self.on_message)
        self.handler.connect()
        self.handler.client.loop_start()

        # Timer to periodically update the line on the graph
        self.timer = QTimer(self)        
        self.timer.timeout.connect(self.update_line)
        self.timer.start(settings["draw_line_frequency"])

    # Updates the visualization by calling graph & compass functions, redrawing the line with most recent coords and rotating the compass accordingly
    def update_line(self):
        self.graph.update_line()
        self.compass.rotate_triangle(self.heading)

    # Appends the deques and updates the heading variable with streaming data from the message broker
    def on_message(self, client, userdata, msg):
        # Sample_data_mod is used to determine the sample rate -- how often data is processed by the visualization.
        if self.counter % self.settings["sample_data_mod"] == 0:
            data = json.loads(msg.payload)
            if "x_loc" in data and "y_loc" in data:
                x = data["x_loc"] / 10
                y = data["y_loc"] / 10
                if x is not None and y is not None:
                    # Add x and y to deque
                    self.graph.add_point(x, y)
                    self.scroll.setText("{:.4f},   {:.4f}".format(x, y))
            self.heading = data["heading"]
        self.counter += 1

    # Configure keystrokes
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.exit_program()
        if event.key() == Qt.Key_Backspace:
            self.reset()
            
    # On close of window
    def on_close(self, event):
        self.exit_program()

    # Disconnect from the message broker and shutdown the GUI process
    def exit_program(self):
        self.handler.client.disconnect()
        self.handler.client.loop_stop()
        self.close()

    # Upon a press of the reset button, "reset" is set to true in the payload, signalling all client processes to reset their to their initial values (for use when asset is manually returned to its physical origin point)
    def reset(self):
        publish.single(
            topic=self.settings["topic_pub"],
            payload=json.dumps({"reset": True}),
            hostname=self.settings["broker_host"],
            qos=1,
            protocol=MQTTv5
            )
        self.scroll.lines.clear()
        self.graph.x_queue.clear()
        self.graph.y_queue.clear()