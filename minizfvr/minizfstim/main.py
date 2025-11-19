import sys
import time
from pathlib import Path

from PyQt5.QtCore import QTimer, QSize
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
)
from PyQt5.QtGui import QIcon

import qdarkstyle

from .parameters import StimParamObject
from .stim_window import StimulusWindow
from .panels import StimulusControlPanel
from ..communication import Receiver, wait_trigger_from_sidewinder
from .estimator import Estimator
from .saver import Saver
from ..utils import set_icon

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
    - push button to establish connection with the tail minizftt
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
        self.move(350, 50)
        self.setFixedSize(300, 300)
        self.setWindowTitle('minizfstim')
        set_icon(self)

        ## State flags, handles, and timestamps
        self.stimulus_running = False
        self.ii = 0 # count frames from the parent, just for convenience
        self.t0 = 0
        self.t0_tail = None # save the first tail timestamp

        ## Stimulus generator object
        # This should have a 'update' method, which takes timestamp, tail info, calibration parameters as inputs
        # and return bitmap (ndarray) as an output. Otherwise, it can be anything
        self.stimulus_generator = stimulus_generator

        ## Create a parameter object & load config
        self.param = StimParamObject(self) # this is a hybrid of a dataclass and QObject -- it can emit signals
        self.param.load_config_from_json(self.param.config_path)
        self.param.is_panorama = is_panorama # this param should be dictated by each stimulus generator

        ## Prepare a receiver object that listens to the tail tracking data & attempt the connection
        self.receiver = Receiver(self.param.localhost_port)

        ## Create an estimator object that comuputes swim bouts given tail angle traces
        self.estimator = Estimator() # todo: pass parameters?

        ## Create a saver object that handles data saving
        self.saver = Saver(buffer_size=self.param.save_buffer_size)

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

        ## Create and start the timer for timed GUI updates
        self.timer = QTimer()
        self.timer.setInterval(1000 // self.param.frame_rate) # aim 60 Hz
        self.timer.start()

        ## Connect signals to callbacks
        self.connect_callbacks()

        ## Attempt connection to the pipe
        # This needs to happen after defining callbacks, otherwise the signal emitted by the receiver will go unheard
        self.receiver.open_connection()

    def connect_callbacks(self):
        """
        Connect various signals to callbacks
        Only run once from the constractor
        Separated out as a method for the sake of readability
        """

        # When parameter is changed, we immediately repaint stimuli,
        # which is especially important for adjusting the paint area interactively
        self.param.paramChanged.connect(self.stimulus_window.adjust_canvas)

        # When we click the start button, start / stop stimulus
        self.ui.start_button.clicked.connect(self.toggle_run_state)

        # When we click the reset button, reset stimuli
        self.ui.reset_button.clicked.connect(self.reset_stimulus)

        # When we click save checkboxes, update the save state flags in the saver (also pass the new state)
        self.ui.save_tail_check.stateChanged.connect(lambda cs, is_tail=False: self.saver.toggle_states(cs, is_tail))
        self.ui.save_stim_check.stateChanged.connect(lambda cs, is_tail=True: self.saver.toggle_states(cs, is_tail))

        # When stimulus is supposed to end, it emits a signal. We then stop the stimulus.
        self.stimulus_generator.durationPassed.connect(self.toggle_run_state)

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
        Start button callback.
        Primarily it just switches saving flag on/off.
        """
        if not self.stimulus_running: # start

            # prepare saving files (if necessary)
            self.saver.initialize(
                self.param,
                self.stimulus_generator
            )

            # save stimulus metadata
            self.stimulus_generator.save_metadata(self.saver.run_path / 'stim_metadata.json')

            if self.ui.trigger_check.isChecked():
                # Wait for trigger
                # TODO: Make this customizable from the config file, according to whatever microscope expects
                if not wait_trigger_from_sidewinder(duration=self.stimulus_generator.duration, port=self.param.tcp_port):
                    return

            print('Starting stimulus')
        else: # stop
            self.saver.finalize()
            print('Stopping stimulus')

        # toggle (things we can do agnostic which way)
        self.stimulus_running = not self.stimulus_running
        self.ui.start_button.force_state(self.stimulus_running) # update the button
        self.reset_stimulus() # reset timestamp, show the window (if not shown)

    def reset_stimulus(self):
        """
        Reset button callback (do I need this?)
        """
        self.stimulus_window.show()
        self.t0 = time.perf_counter()
        self.t0_tail = None

    def stimulus_update(self):
        """
        Called at every timer update
        """

        # timestamp to monitor the computational time for stimulus update
        t_this_loop_start = time.perf_counter()

        # If we are connected to the tail minizftt, we get the tail angle data / timestamp from the pipe,
        # pass it to the estimator object, and calculate the latest vigor and bias information.
        # We do this continuously regardless of whether the stimuli are running, so we do not accumulate
        # data in the pipe.
        if self.receiver.connected:
            data = self.receiver.read_data() # list of (time, angle) tuples
            if data is not None:
                for this_data in data:
                    if self.t0_tail is None:
                        self.t0_tail = this_data[0] # we want to keep the first tail time stamp
                    self.estimator.register_new_data(*this_data)
        else:
            data = None

        if self.stimulus_running:

            t_now = time.perf_counter() - self.t0

            # update the swim estimate -- this needs to happen at the same rate as the stimulus (rather than with the
            # tail data entry). This is because bout bias is detected as delta-like point event, and if we calcualte
            # this at 200Hz the stimulus can miss it
            self.estimator.update_swim_estimate()

            # give the time stamp to the stimulus generator object, get the frame bitmap
            stim_frame = self.stimulus_generator.update(
                t=t_now,
                paint_area_mm=(self.param.w/self.param.px_per_mm, self.param.h/self.param.px_per_mm),
                vigor=self.estimator.vigor,
                bias=self.estimator.bias
            )

            # In case the size of the bitmap is different from what is in the parameter (which would be
            # usually only the case during the first frame, we insert new bitmap sizes into the parameter.
            # This will only affect what is being shown if we are forcing the equal ratio and the aspect
            # ratio of the bitmap changes. I assume this is a very rare event.
            current_bitmap_shape = stim_frame[0].shape[:2]
            if (self.param.bitmap_h, self.param.bitmap_w) != current_bitmap_shape: # can be 3d!
                self.param.bitmap_h, self.param.bitmap_w = current_bitmap_shape
                self.ui.calibration_panel.refresh_param()

            ## saving - we check stimulus_running again, because stimulus_generator can stop the stimulus and
            # close the file
            if self.stimulus_running:
                if self.saver.save_tail_flag:
                    if data is not None:
                        for this_data in data:
                            self.saver.save_tail_data(this_data[0]-self.t0_tail, this_data[1])
                if self.saver.save_stim_flag:
                    self.saver.save_stim_data(t_now, self.stimulus_generator)

            # pass the frame bitmap to the StimulusWindow, and paint
            self.stimulus_window.receive_and_paint_new_frame(stim_frame)

            # show how much time it takes to do the single stimulus update
            if self.ii % 50 == 0:
                self.ui.message_line.setText('Duty {0:0.0%} / {1} Hz - done in {2:0.0f} s'.format(
                    (time.perf_counter() - t_this_loop_start) / self.timer.interval() * 1000,
                    self.param.frame_rate,
                    self.stimulus_generator.duration - t_now
                ))
                self.ii = 0
            self.ii += 1

    def closeEvent(self, event):
        self.stimulus_generator.close()
        self.stimulus_window.close()
        self.receiver.close()
        self.param.save_config_into_json(self.param.config_path)