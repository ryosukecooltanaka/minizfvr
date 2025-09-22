"""

minizfvr tail tracker development version 01

2025/09/22 Ryosuke Tanaka

I decided to write two completely separate apps for tail tracking and stimulus presentation, and make the tail tracker
talk to the stimulus generator through a named pipe. By running two separate python interpreters I do not need to worry
about managing multiple processes which feels complicated, and also this design would allow much wider flexibility in
terms of what kind of programs to be used for the stimulus generation. Here I will first focus on completing the tail
tracking app.

"""

import numpy as np
import pyqtgraph as pg
import sys
from camera import SelectCameraByName
from panels import CameraPanel, AnglePanel, ControlPanel
from utils import center_of_mass_based_tracking, preprocess_image

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QPushButton,
    QCheckBox,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QLabel,
    QSizePolicy,
    QInputDialog
)


class MiniZFTT(QMainWindow):
    """
    Main tail tracker GUI window.
    Displays fish image, tail trace, and other controls.
    """

    def __init__(self):
        """
        The main window constructor. Called once at the beginning.
        """

        # Call the parental (QMainWindow) constructor
        super().__init__()

        # Create other widgets & arrange them
        self.camera_panel = CameraPanel()
        self.angle_panel = AnglePanel()
        self.control_panel = ControlPanel()
        self.arrange_widgets()

        # initialize camera
        self.camera = SelectCameraByName('dummy', video_path='./tail_movie.mp4')

        # Prepare attributes to store loaded images & the results of the tail tracking
        self.current_frame = None
        self.processed_frame = None
        self.angle_buffer = np.full(1000, np.nan) # size should be specified by config etc.
        self.timestamp_buffer = np.full(1000, np.nan)
        self.buffer_counter = 0
        self.current_segment_position = [] # only for the visualization purpose

        # store miscellaneous parameters that might be loaded from a json config file and
        # can be controlled through the GUI as a dict
        self.parameters = dict()
        self.load_config()

        # Define timer for GUI
        self.timer = QTimer()
        self.timer.setInterval(50)  # millisecond
        self.timer.timeout.connect(self.update_gui)  # define callback
        self.timer.start()


    def arrange_widgets(self):
        """
        Separate out cosmetics out of the constructor for readability
        Arrange widgets into a single container in the main window
        """
        # set window title and size
        self.setWindowTitle("minizftt_dev v01")  # window title
        self.setGeometry(50, 50, 400, 600)  # default window position and size (x, y, w, h)

        # The main window needs to have a single, central widget (which is just a empty container).
        # Widgets like buttons will be arranged inside the container later.
        container = QWidget()
        self.setCentralWidget(container)

        # Create vertical box layout. From top, we will show camera image, tail plot, and controls
        # Control box will require layouts of its own, but let's worry about that later
        layout = QVBoxLayout()
        layout.addWidget(self.camera_panel)
        layout.addWidget(self.angle_panel)
        layout.addWidget(self.control_panel)

        # Adjust height ratios
        layout.setStretch(0, 10)
        layout.setStretch(1, 3)
        layout.setStretch(2, 3)

        container.setLayout(layout)

    def fetch_and_track_tail(self):
        """
        Read frame from the camera, perform the tracking algorithm on the frame,
        log the tail angle, pass it to the pipe
        This method should be called above camera frequency
        """
        self.current_frame, timestamp = self.camera.fetch_image()
        current_angle = self.track_tail()

        self.angle_buffer[self.buffer_counter] = current_angle
        self.timestamp_buffer[self.buffer_counter] = timestamp
        self.buffer_counter = (self.buffer_counter+1)%1000

    def track_tail(self):
        """
        Pass parameters (manually drawn resting tail coordinates, image binzalization range etc.) to tail tracking
        functions. Tail tracking functions could be pre-compiled for the accerelation purpose, I think.
        """
        # get the "resting tail" information from the CameraPanel
        base, tip = self.camera_panel.get_base_tip_position()
        self.processed_frame = preprocess_image(self.current_frame, **self.parameters)
        segments, angles = center_of_mass_based_tracking(self.processed_frame, base, tip, 7, 15)
        self.camera_panel.update_tracked_tail(segments)
        return angles[-1]-angles[0]

    def update_gui(self):
        """
        Show whatever the latest frame and tail trace
        This method should be called at like 20 Hz tops
        """
        self.fetch_and_track_tail()
        self.camera_panel.set_image(self.processed_frame)
        self.angle_panel.set_data(np.arange(len(self.angle_buffer)), self.angle_buffer)

    def load_config(self):
        self.parameters['image_scale'] = 0.25
        self.parameters['filter_size'] = 5
        self.parameters['color_invert'] = True
        self.parameters['clip_threshold'] = 190

    def closeEvent(self, event):
        """
        This will be called when the main window is closed.
        Release resources for graceful exit.
        """
        self.timer.stop()
        self.camera.close()


"""
Instantiate the application
"""

if __name__ == '__main__':
    # Prepare the PyQt Application
    app = QApplication([])
    # Instantiate the main GUI window
    win = MiniZFTT()
    # show the window
    win.show()
    # start the application (exit the interpreter once the app closes)
    sys.exit(app.exec_())