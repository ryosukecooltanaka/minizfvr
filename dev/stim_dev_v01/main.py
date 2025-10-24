import numpy as np
import sys
import time
import h5py
import os
from pathlib import Path

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

        ## State flags, handles, and timestamps
        self.stimulus_running = False
        self.save_stim_flag = False
        self.save_tail_flag = False
        self.stim_save_file_handle = None
        self.tail_save_file_handle = None
        self.stim_save_counter = 0
        self.tail_save_counter = 0
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
        self.estimator = Estimator() # todo: pass parameters?

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

        # Update the save state according to the check
        self.ui.save_stim_check.stateChanged.connect(self.toggle_save_state)
        self.ui.save_tail_check.stateChanged.connect(self.toggle_save_state)

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
        Start button callback
        We do not stop the timer so that the stimulus_update method can flush the pipe continuously
        """
        if not self.stimulus_running:
            # Things to do when we start stimuli
            # todo: delegate saving to a separate object once I figure out how
            if self.save_stim_flag or self.save_stim_flag:
                # Create a directory with the current timestamp as its name
                start_time_str = time.strftime('%y%m%d%H%M%S')
                save_path = Path(self.param.save_path) / start_time_str
                if not save_path.exists():
                    os.mkdir(save_path)

                # Prepare tail save file
                if self.save_tail_flag:
                    if not self.receiver.connected:
                        print('Tail saving requested but it is not connected to tracker -- aborting acquisition')
                        return

                    # we expect this to be at 200 Hz
                    expected_frame_count = int(self.stimulus_generator.duration * 300)
                    self.tail_save_file_handle = h5py.File(save_path / 'tail_log.h5', 'w')
                    self.tail_save_file_handle.create_dataset('t', (expected_frame_count,), maxshape=(None,),
                                                              dtype=float)
                    self.tail_save_file_handle.create_dataset('tail_angle', (expected_frame_count,),
                                                              maxshape=(None,), dtype=float)
                    self.tail_save_counter = 0

                # Prepare stimulus save file
                if self.save_stim_flag:
                    # We need to specify the size of the dataset
                    # Our actual frame rate would be slightly higher than 60 Hz due to rounding
                    expected_frame_count = int(self.stimulus_generator.duration * 62.5)
                    # open a handle for the file
                    self.stim_save_file_handle = h5py.File(save_path / 'stimulus_log.h5', 'w')
                    # create dataset corresponding to the stimulus dict
                    sdict = self.stimulus_generator.stim_dict
                    self.stim_save_file_handle.create_dataset('t',  (expected_frame_count, ), dtype=float)
                    for key in sdict.keys():
                        self.stim_save_file_handle.create_dataset(key, (expected_frame_count, ), dtype=type(sdict[key]))
                    self.stim_save_counter = 0

        else:
            # Things to do when we stop stimuli
            print('Succesful exit')
            if self.save_tail_flag:
                self.stim_save_file_handle.close()
            if self.save_tail_flag:
                self.tail_save_file_handle.close()

        self.stimulus_running = not self.stimulus_running
        self.ui.start_button.force_state(self.stimulus_running) # update the button
        self.reset_stimulus() # reset timestamp, show the window (if not shown)

    def reset_stimulus(self):
        """
        Reset button callback (do I need this?)
        """
        self.stimulus_window.show()
        self.t0 = time.perf_counter()

    def toggle_save_state(self):
        """
        Save state checkbox callback
        """
        self.save_stim_flag = self.ui.save_stim_check.isChecked()
        self.save_tail_flag = self.ui.save_tail_check.isChecked()

    def stimulus_update(self):
        """
        Called at every timer update
        """

        # If we are connected to the tail tracker, we get the tail angle data / timestamp from the pipe,
        # pass it to the estimator object, and calculate the latest vigor and laterality information
        if self.receiver.connected:
            data = self.receiver.read_data() # list of (tail angle, timestamp) tuples
            if data is not None:
                for this_data in data:
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

            # In case the size of the bitmap is different from what is in the parameter (which would be
            # usually only the case during the first frame, we insert new bitmap sizes into the parameter.
            # This will only affect what is being shown if we are forcing the equal ratio and the aspect
            # ratio of the bitmap changes. I assume this is a very rare event.
            if (self.param.bitmap_h, self.param.bitmap_w) != stim_frame.shape[:2]: # can be 3d!
                self.param.bitmap_h, self.param.bitmap_w = stim_frame.shape[:2]
                self.ui.calibration_panel.refresh_param()

            # saving
            try:
                if self.save_tail_flag:
                    if data is not None:
                        for this_data in data:
                            self.tail_save_file_handle['t'][self.tail_save_counter] = this_data[0]
                            self.tail_save_file_handle['tail_angle'][self.tail_save_counter] = this_data[1]
                            self.tail_save_counter += 1

                if self.save_stim_flag:
                    self.stim_save_file_handle['t'][self.stim_save_counter] = t_now
                    for key in self.stimulus_generator.stim_dict.keys():
                        self.stim_save_file_handle[key][self.stim_save_counter] = self.stimulus_generator.stim_dict[key]
                    self.stim_save_counter += 1
            except (IndexError, KeyError) as e:
                print('Issue with writing')

            # pass the frame bitmap to the StimulusWindow, and paint
            self.stimulus_window.receive_and_paint_new_frame(stim_frame)

    def closeEvent(self, event):
        self.stimulus_window.close()
        self.receiver.close()
        self.param.save_config_into_json()