# Visualization-PyQt is the main function of the visualization layer
# Passes values from config to the main PyQt gui window

import sys
import signal
import json
from PyQt5.QtWidgets import (QApplication)
from app.Visualization.Components.plotter_gui import PlotterGUI


def sigint_handler(signal, frame):
    print("SIGINT received, terminating application...")
    gui.exit_program()

if __name__ == '__main__':

    try:
        signal.signal(signal.SIGINT, sigint_handler)
        #  --- Get config parameters ---
        with open('config.json') as config_file:
            config = json.load(config_file)

        settings = config.get("visualization_PyQt.py")
        app = QApplication(sys.argv)
        gui = PlotterGUI(settings)
        QApplication.instance().moveToThread(QApplication.instance().thread())
        gui.show()
        sys.exit(app.exec_())

    except (Exception) as e:
        print(e)