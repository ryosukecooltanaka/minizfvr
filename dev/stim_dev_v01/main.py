"""
Stimulus presentation app

Ideas:

minimum control window  +
secondary stimulus window

listen to the tracker through a named pipe

calibration

Timed stimulus update using the timer (or while loop in multiprocessing -- if we want to optimize for regular frame rate?)

Hold a moderngl context object

Options to
- create a single "floor" object
- create a panoramic cylinder (or a sphere)
- full 3d world

Render options
- panoramic windows
- single window (for bottom projection)

In the end everything is rendered as a bitmap
(is this somehow slower, if we are for example just doing gratings etc.? Not sure)

Update function can update the world itself, or just texture

Do we want protocol > stimulus kind of hierachy?


"""
import numpy as np
import sys
import time

from PyQt5.QtCore import QTimer, QRect, QPoint
from PyQt5.QtGui import QPainter, QBrush, QPen, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QLabel
)

class StimulusApp:
    """
    In each script specifying the experiment, we import this app object
    Not sure if this is the most straightforward way of doing it, but should work
    """
    def __init__(self):
        app = QApplication([])
        # Instantiate the main GUI window
        win = StimulusControlWindow()
        # show the window
        win.show()
        # start the application (exit the interpreter once the app closes)
        sys.exit(app.exec_())


class StimulusControlWindow(QMainWindow):
    """
    Things to implement
    - start/stop push button
    - check box / line edit to specify if/where to save things
    - push button to establish connection with the tail tracker
    - rect specification and calibration


    - potentially some plots for debugging purpose? (optional)
    - parameters -- probably no need to dynamically update this?
    """

    """
    Constructor & Things that are run only once at the beginning
    """
    def __init__(self):
        """
        The main window constructor. Called once at the beginning.
        """

        # Call the parental (QMainWindow) constructor
        super().__init__()
        self.setWindowTitle('Stimulus Control')
        self.setGeometry(100, 100, 400, 200)

        # create a stimulus window
        self.stimulus_window = StimulusWindow()
        self.stimulus_window.show()

        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.stimulus_window.repaint)
        self.timer.start()


class StimulusWindow(QWidget):
    """
    The second window on which we present stimuli to be viewed by the animals
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Stimulus Window')
        self.setGeometry(500, 500, 500, 500)
        self.setStyleSheet("background-color: black;")

        # todo: get rid of the title bar and implement sneaky minimize/maximize buttons (lower priority)
        # https://www.pythonguis.com/tutorials/custom-title-bar-pyqt6/
        # self.setWindowFlags(Qt.WindowType.FramelessWindowHint)


    def paintEvent(self, event):
        """
        This is what is called if there is any need for repaint - paint event is emitted when the window is resized
        and update() or repaint() method of a QWidget is called.
        QPainter can only be used within painEvent() method of QWidget.
        """
        qp = QPainter()
        qp.begin(self)
        qp.setBrush(QColor(*np.random.randint(0,255,3).astype(int)))
        qp.drawRect(QRect(np.random.randint(0, 300), np.random.randint(0, 300), 50, 50))
        qp.end()


if __name__ == "__main__":
    StimulusApp()