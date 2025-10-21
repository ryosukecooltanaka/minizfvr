import numpy as np
import sys
import time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
)

from parameters import StimParamObject
from stim_window import StimulusWindow
from panels import StimulusControlPanel
from communication import Receiver

class StimulusApp:
    """
    In each script specifying the experiment, we import this app object, and hand a stimulus generator object
    The constructor of this object will kickstart the GUI
    """
    def __init__(self, stimulus_generator, is_panorama=False):
        app = QApplication([])
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

        # Call the parental (QMainWindow) constructor
        super().__init__()
        self.setWindowTitle('Stimulus Control')
        self.setGeometry(100, 100, 200, 400)

        # Stimulus generator object
        # This should have a 'update' method, which takes timestamp, tail info, calibration parameters as inputs
        # and return bitmap (ndarray) as an output. Otherwise it can be anything
        self.stimulus_generator = stimulus_generator

        # Create a parameter object & load config
        self.param = StimParamObject(self) # this is a hybrid of a dataclass and QObject -- it can emit signals
        self.param.load_config_from_json()
        self.param.is_panorama = is_panorama

        # state flags and timestamps
        self.stimulus_running = False
        self.t0 = 0

        ### Create Widgets ###
        # create a stimulus window, pass null parent, and parameter reference
        self.stimulus_window = StimulusWindow(None, param=self.param, corner=stim_window_corner)
        if maximize_stim_window:
            self.stimulus_window.showMaximized()
        else:
            self.stimulus_window.show()

        # prepare UI panels
        self.ui = StimulusControlPanel(self.param) # pass reference to parameters
        self.setCentralWidget(self.ui)

        ### Connect Signals to Callbacks ###
        # make sure the stimulus window paint area is updated appropriately as we change parameters
        self.param.paramChanged.connect(self.stimulus_window.repaint)

        # Start / stop stimulus as we click buttons
        self.ui.start_button.clicked.connect(self.toggle_run_state)
        self.ui.reset_button.clicked.connect(self.reset_stimulus)

        # Toggle calibration frame depending on the calibration panel state
        self.ui.calibration_panel.panelOpened.connect(lambda: self.stimulus_window.toggle_calibration_frame(True))
        self.ui.calibration_panel.panelClosed.connect(lambda: self.stimulus_window.toggle_calibration_frame(False))

        # receiver
        self.receiver = Receiver()
        self.receiver.open_connection() # unless a listener is already open, this fails -- in which case, click the connect button
        self.ui.connect_button.clicked.connect(self.receiver.open_connection)

        # Timed stimulus update
        self.timer = QTimer()
        self.timer.setInterval(1000 // 60) # aim 60 Hz
        self.timer.timeout.connect(self.stimulus_update)
        self.timer.start()

    def toggle_run_state(self):
        if not self.stimulus_running:
            self.stimulus_running = True
            self.t0 = time.time()
            self.ui.start_button.setText('Stop')
        else:
            self.stimulus_running = False
            self.ui.start_button.setText('Start')

    def reset_stimulus(self):
        self.stimulus_window.show()

    def stimulus_update(self):
        """
        Called every timer update
        """

        vigor = 0
        if self.receiver.conn is not None:
            data = self.receiver.read_data() # list of (tail angle, timestamp) tuples
            if data is not None:
                vigor = np.std([x[0] for x in data])



        if self.stimulus_running:
            t = time.time() - self.t0

            # give the time stamp to the stimulus generator object, get the frame bitmap
            if not self.param.is_panorama:
                stim_frame = self.stimulus_generator.update(
                    t=t,
                    paint_area_mm=(self.param.w/self.param.px_per_mm, self.param.h/self.param.px_per_mm),
                    vigor=vigor
                )
            else:
                # when we are working on a panoramic setup, the desired scale of stimuli should be
                # determined by the geometry of the physical setup itself. Such that, the stimulus
                # generator should be OK remaining agnostic about
                stim_frame = self.stimulus_generator.update(t=t)

            # if the shape of the bitmap has changed, we call parameter refresh, in case if we need to change the rect
            if (self.param.bitmap_h, self.param.bitmap_w) != stim_frame.shape[:2]: # can be 3d!
                self.param.bitmap_h, self.param.bitmap_w = stim_frame.shape[:2]
                self.ui.calibration_panel.refresh_param()

            # pass the frame bitmap to the StimulusWindow, and paint
            self.stimulus_window.receive_and_paint_new_frame(stim_frame)

    def closeEvent(self, event):
        self.stimulus_window.close()
        self.receiver.close()
        self.param.save_config_into_json()