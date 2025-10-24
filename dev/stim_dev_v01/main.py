import numpy as np
import sys
import time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
)

import qdarkstyle

from parameters import StimParamObject
from stim_window import StimulusWindow
from panels import StimulusControlPanel
from communication import Receiver
from estimator import Estimator

class StimulusApp:
    """
    In each script specifying the experiment, we import this app object, and hand a stimulus generator object
    The constructor of this object will kickstart the GUI
    """
    def __init__(self, stimulus_generator, is_panorama=False):

        app = QApplication([])
        app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

        # check if we have multiple screens
        screens = app.screens()
        if len(screens) > 1: # if we have multiple screens, we show the stimulus window maximized at the last screen
            stim_window_corner = (screens[-1].geometry().left(), screens[-1].geometry().top())
            maximize_stim_window = True
        else: # otherwise we show the screen in the main window without maximization
            stim_window_corner = (400, 100)
            maximize_stim_window = False

        # Instantiate the main GUI window while passing the stimulus generator object
        win = StimulusControlWindow(stimulus_generator, is_panorama, stim_window_corner, maximize_stim_window)
        # show the window
        win.show()
        # start the application (exit the interpreter once the app closes)
        sys.exit(app.exec_())


class StimulusControlWindow(QMainWindow):
    """
    Main GUI window

    Things to implement
    - start/stop push button
    - check box / line edit to specify if/where to save things
    - push button to establish connection with the tail tracker
    - rect specification and calibration


    - potentially some plots for debugging purpose? (optional)
    - parameters -- probably no need to dynamically update this?
    """

    def __init__(self, stimulus_generator, is_panorama, stim_window_corner, maximize_stim_window):
        """
        The main window constructor. Called once at the beginning.
        """

        ## Call the parental (QMainWindow) constructor
        super().__init__()
        self.move(50, 50)
        self.setFixedSize(200, 300)

        ## Important state flags and timestamps
        self.stimulus_running = False
        self.save_flag = False
        self.t0 = 0

        ## Stimulus generator object
        # This should have a 'update' method, which takes timestamp, tail info, calibration parameters as inputs
        # and return bitmap (ndarray) as an output. Otherwise, it can be anything
        self.stimulus_generator = stimulus_generator

        ## Create a parameter object & load config
        self.param = StimParamObject(self) # this is a hybrid of a dataclass and QObject -- it can emit signals
        self.param.load_config_from_json()
        self.param.is_panorama = is_panorama # this param should be dictated by each stimulus generator

        ## Create an estimator object
        self.estimator = Estimator()

        ## Create Widgets
        # create a stimulus window, pass null parent, and parameter reference
        self.stimulus_window = StimulusWindow(None, param=self.param, corner=stim_window_corner)
        if maximize_stim_window:
            self.stimulus_window.showMaximized()
        else:
            self.stimulus_window.show()
        # prepare UI panels and set it on the main window
        self.ui = StimulusControlPanel(self.param) # pass reference to parameters
        self.setCentralWidget(self.ui)

        ## Prepare a receiver object to listen to the tail tracking data & attempt the connection
        self.receiver = Receiver()

        ## Create and start the timer for timed GUI updates
        self.timer = QTimer()
        self.timer.setInterval(1000 // 60) # aim 60 Hz
        self.timer.start()

        ## Connect signals to callbacks
        self.connect_callbacks()

        ## Attempt connection
        self.receiver.open_connection()

    def connect_callbacks(self):
        """
        Connect various signals to callbacks
        Only run once from the constractor
        Separated out as a method for the sake of readability
        """

        # When parameter is changed, we immediately repaint stimuli,
        # which is especially important for adjusting the paint area interactively
        self.param.paramChanged.connect(self.stimulus_window.repaint)

        # Start / stop stimulus as we click the start button
        self.ui.start_button.clicked.connect(self.toggle_run_state)

        # Reset stimulus as we click the reset button
        self.ui.reset_button.clicked.connect(self.reset_stimulus)

        # When you open/close the calibration panel, show/un-show the calibration frame around the paint area
        self.ui.calibration_panel.panelOpenStateChanged.connect(
            lambda x: self.stimulus_window.toggle_calibration_frame(x))

        # If you click the connect button, the receiver will attempt connection
        self.ui.connect_button.clicked.connect(self.receiver.open_connection)
        # If connection state is changed, we update the button
        self.receiver.connectionStateChanged.connect(lambda x: self.ui.connect_button.force_state(x))

        # Schedule regular stimulus update
        self.timer.timeout.connect(self.stimulus_update)

    def toggle_run_state(self):
        """
        Start button callback
        We do not stop the timer so that the stimulus_update method can flush the pipe continuously
        """
        self.stimulus_running = not self.stimulus_running
        self.ui.start_button.force_state(self.stimulus_running)
        self.t0 = time.perf_counter()

    def reset_stimulus(self):
        """
        Reset button callback (do I need this?)
        """
        self.stimulus_window.show()
        self.t0 = time.perf_counter()

    def stimulus_update(self):
        """
        Called at every timer update
        """

        if self.receiver.connected:
            data = self.receiver.read_data() # list of (tail angle, timestamp) tuples
            if data is not None:
                for this_data in data: # I think this is doing FIFO correctly?
                    self.estimator.register_new_data(*this_data)

        if self.stimulus_running:

            t_now = time.perf_counter() - self.t0
            # give the time stamp to the stimulus generator object, get the frame bitmap

            stim_frame = self.stimulus_generator.update(
                t=t_now,
                paint_area_mm=(self.param.w/self.param.px_per_mm, self.param.h/self.param.px_per_mm),
                vigor=self.estimator.vigor,
                laterality=self.estimator.laterality
            )

            # if the shape of the bitmap has changed, we call parameter refresh, in case if we need to change the rect
            if (self.param.bitmap_h, self.param.bitmap_w) != stim_frame.shape[:2]: # can be 3d!
                self.param.bitmap_h, self.param.bitmap_w = stim_frame.shape[:2]
                self.param.paramChanged.emit()

            # pass the frame bitmap to the StimulusWindow, and paint
            self.stimulus_window.receive_and_paint_new_frame(stim_frame)

    def closeEvent(self, event):
        self.stimulus_window.close()
        self.receiver.close()
        self.param.save_config_into_json()