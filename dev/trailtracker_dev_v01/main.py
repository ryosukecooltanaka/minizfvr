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
import sys
from camera import SelectCameraByName
from panels import CameraPanel, AnglePanel, ControlPanel
from utils import center_of_mass_based_tracking, preprocess_image
from parameters import TailTrackerParams
import os
import json
from time import time_ns as time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QLabel
)


class MiniZFTT(QMainWindow):
    """
    Main tail tracker GUI window.
    Displays fish image, tail trace, and other controls.
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

        # Load config from file, as it is used for initialization
        self.parameters = TailTrackerParams()
        self.parameters.load_config_from_json()

        # Create other widgets & arrange them
        self.camera_panel = CameraPanel()
        self.angle_panel = AnglePanel()
        self.control_panel = ControlPanel()
        self.message_strip = QLabel()
        self.arrange_widgets()

        # initialize camera
        self.camera = SelectCameraByName(self.parameters.camera_type,
                                         video_path=self.parameters.dummy_video_path)

        # Prepare attributes to store loaded images & the results of the tail tracking etc.
        self.current_frame = None
        self.processed_frame = None
        self.angle_buffer = np.full(1000, np.nan) # size should be specified by config etc.
        self.timestamp_buffer = np.full(1000, np.nan)
        self.buffer_counter = 0
        self.current_segment_position = [] # only for the visualization purpose
        self.dt = 0

        # Setup callback functions for the control panel GUI
        self.connect_control_callbacks()

        # Define timers
        self.fetch_timer = QTimer()
        self.fetch_timer.setInterval(1)  # millisecond
        self.fetch_timer.timeout.connect(self.fetch_and_track_tail)  # define callback

        self.gui_timer = QTimer()
        self.gui_timer.setInterval(100)  # millisecond
        self.gui_timer.timeout.connect(self.update_data_panels)  # define callback

        self.fetch_timer.start()
        self.gui_timer.start()

    def arrange_widgets(self):
        """
        Separate out cosmetics out of the constructor for readability
        Arrange widgets into a single container in the main window
        """
        # set window title and size
        self.setWindowTitle("minizftt_dev v01")  # window title
        self.setGeometry(50, 50, 400, 600)  # default window position and size (x, y, w, h)

        # Insert initial values from config into control panel GUI by passing the parameter object
        self.control_panel.set_current_value(self.parameters)

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
        layout.addWidget(self.message_strip)

        # Adjust height ratios
        layout.setStretch(0, 30)
        layout.setStretch(1, 9)
        layout.setStretch(2, 3)
        layout.setStretch(3, 1)

        container.setLayout(layout)

    def connect_control_callbacks(self):
        self.control_panel.show_raw_checkbox.stateChanged.connect(self.update_parameters)
        self.control_panel.color_invert_checkbox.stateChanged.connect(self.update_parameters)
        self.control_panel.image_scale_box.editingFinished.connect(self.update_parameters)
        self.control_panel.filter_size_slider.sliderReleased.connect(self.update_parameters)
        self.control_panel.clip_threshold_slider.sliderReleased.connect(self.update_parameters)

    """
    Methods called continuously during the run
    """
    def fetch_and_track_tail(self):
        """
        Read frame from the camera, perform the tracking algorithm on the frame,
        log the tail angle, pass it to the pipe
        This method should be called above camera frequency
        """

        fetched_image, timestamp = self.camera.fetch_image()
        if fetched_image is None: # image not ready
            return

        # If image was actually acquired, do all the following processing
        self.current_frame = fetched_image
        current_angle = self.track_tail()

        self.angle_buffer[self.buffer_counter] = current_angle
        self.timestamp_buffer[self.buffer_counter] = timestamp
        self.buffer_counter = (self.buffer_counter+1)%1000


    def track_tail(self):
        """
        Pass parameters (manually drawn resting tail coordinates, image binzalization range etc.) to tail tracking
        functions. Tail tracking functions could be pre-compiled for the accerelation purpose, I think.
        """
        # get the "resting tail" information from the CameraPanel (considering scaling, if we are viewing raw)
        if self.parameters.show_raw:
            factor = self.parameters.image_scale
        else:
            factor = 1.0
        base, tip = self.camera_panel.get_base_tip_position(factor=factor)
        self.processed_frame = preprocess_image(self.current_frame, **self.parameters.__dict__)
        self.current_segment_position, angles = center_of_mass_based_tracking(self.processed_frame, base, tip, 7, 15)
        return angles[-1]-angles[0]

    def update_data_panels(self):
        """
        Show whatever the latest frame and tail trace
        This method should be called at like 20 Hz tops
        """
        # camera panel image update
        if self.parameters.show_raw:
            self.camera_panel.set_image(self.current_frame)
            factor = 1.0 / self.parameters.image_scale
        else:
            self.camera_panel.set_image(self.processed_frame)
            factor = 1.0

        # camera panel tracked tail line update
        self.camera_panel.update_tracked_tail(self.current_segment_position, factor=factor)

        # angle panel update
        self.angle_panel.set_data(np.roll(np.arange(1000,0,-1), self.buffer_counter), self.angle_buffer) # somehow make this smarter

        # message strip update
        last_dt = self.timestamp_buffer[(self.buffer_counter-1)%1000] - self.timestamp_buffer[(self.buffer_counter-2)%1000]
        self.message_strip.setText('Frame capture frequency: {:0.2f} Hz'.format(1 / last_dt))

    def update_parameters(self):
        """
        Called upon any user action on the control panel
        Read values from the GUI widgets, put them into the parameter (if valid), and put the new value into the GUI
        Also rescale tail standard ROI, if we toggle show_raw or rescale image
        """

        # Read the current content of the GUI widgets
        new_sr, new_inv, new_iscale, new_fsize, new_cthresh = self.control_panel.return_current_value()

        # Before overwriting the old parameters, check if we need to adjust the tail ROI and do so
        if new_sr and not self.parameters.show_raw: # if we switched from processed to raw
            self.camera_panel.rescale_tail_standard(1 / self.parameters.image_scale)
        if not new_sr and self.parameters.show_raw: # if we switched from raw to processed
            self.camera_panel.rescale_tail_standard(self.parameters.image_scale)
        if new_iscale is not None and new_iscale!=self.parameters.image_scale and not self.parameters.show_raw:
            self.camera_panel.rescale_tail_standard(new_iscale / self.parameters.image_scale)

        # Insert the new values to the parameter object
        self.parameters.show_raw = new_sr
        self.parameters.color_invert = new_inv
        if new_iscale is not None:
            self.parameters.image_scale = new_iscale
        self.parameters.filter_size = int(new_fsize) # I think sliders return float?
        self.parameters.clip_threshold = int(new_cthresh)

        # force new values on GUI (relevant for lineedits)
        self.control_panel.set_current_value(self.parameters)

        # flag level readjustment
        self.camera_panel.level_adjust_flag = True


    """
    Methods called once at the end
    """
    def closeEvent(self, event):
        """
        This will be called when the main window is closed.
        Release resources for graceful exit.
        """
        self.parameters.save_config_into_json()
        self.fetch_timer.stop()
        self.gui_timer.stop()
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