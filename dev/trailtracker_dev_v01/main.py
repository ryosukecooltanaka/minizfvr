"""

minizfvr tail tracker development version 01

2025/09/22 Ryosuke Tanaka

I decided to write two completely separate apps for tail tracking and stimulus presentation, and make the tail tracker
talk to the stimulus generator through a named pipe. By running two separate python interpreters I do not need to worry
about managing multiple processes which feels complicated, and also this design would allow much wider flexibility in
terms of what kind of programs to be used for the stimulus generation. Here I will first focus on completing the tail
tracking app.

2025/09/23
I figured that probably separating frame acquisition into separate processes is still a good idea
given time constraints and time stamping accuracy.

"""

import numpy as np
import sys
import multiprocessing as mp
from multiprocessing import shared_memory
from queue import Empty
import time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QLabel
)

from utils import decode_array_to_frame
from camera import SelectCameraByName
from panels import CameraPanel, AnglePanel, ControlPanel
from tracker import TrackerObject
from parameters import TailTrackerParams


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
        self.camera_panel = CameraPanel(**self.parameters.__dict__)
        self.angle_panel = AnglePanel()
        self.control_panel = ControlPanel()
        self.message_strip = QLabel()
        self.arrange_widgets()

        # Select camera / create a camera object
        self.camera = SelectCameraByName(self.parameters.camera_type, **self.parameters.__dict__)
        # Create a tracking object
        self.tracker = TrackerObject(self.parameters.__dict__)

        ## Prepare shared_memory (camera image, current segment position, angle history)
        # This is faster than Queue, which requires pickling etc.  Because the main GUI only needs
        # a fraction of data, throwing every data into a queue is wasteful in terms of CPU
        # Because the camera initialization does not happen until the child process is kick-started, we don't know the exact
        # amount of memory we need here. I guess 1000 x 1000 px uint8 (1MB) should be fine?
        self.raw_frame_memory = shared_memory.SharedMemory(create=True, name='raw_frame_memory', size=1000000)
        self.processed_frame_memory = shared_memory.SharedMemory(create=True, name='processed_frame_memory', size=1000000)
        # max 10 segments x {x, y} x float64 (8 bytes) = 160 bytes
        self.segment_memory = shared_memory.SharedMemory(create=True, name='segment_memory', size=160)
        # angle trace visualization - length is decided by angle_trace_length parameter (x 8 byte per data point)
        # we also store timestamps into the same array (= 2x the buffer size)
        self.angle_memory = shared_memory.SharedMemory(create=True, name='angle_memory', size=16*self.parameters.angle_trace_length)

        ## create numpy arrays that refers to the memory we allocated
        # because the size of the image can change dynamically, we keep this as 1d array and reshape when we show them
        self.current_raw_frame = np.ndarray((1000000,), dtype=np.uint8, buffer=self.raw_frame_memory.buf)
        self.current_processed_frame = np.ndarray((1000000,), dtype=np.uint8, buffer=self.processed_frame_memory.buf)
        self.current_segments = np.ndarray((2, 10), dtype=np.float64, buffer=self.segment_memory.buf)
        self.angle_history = np.ndarray((2, self.parameters.angle_trace_length), dtype=np.float64, buffer=self.angle_memory.buf)
        self.angle_history[:] = 0 # initialize

        # Create Queues
        self.timestamp_queue = mp.Queue(maxsize=10) # pass timestamps
        self.param_queue = mp.Queue(maxsize=10) # passing parameters to the tracking process
        # send the initial parameter, because the tracking process needs a parameter for initialization
        self.param_queue.put(self.parameters.__dict__)

        # Delegate frame acquisition to a child process
        # By calling mp.Process, we create a child process and send a copy of the self.camera there.
        # The camera object will be Pickled to be copied, and there are certain things that cannot be pickled.
        # For this reason, we call the camera initialization in the child process, at the beginning of the
        # continuous acquisition process.
        self.acquisition_process = mp.Process(target=self.camera.continuously_acquire_frames, args=(self.timestamp_queue,), name='acquisition process')
        self.tracking_process = mp.Process(target=self.tracker.continuously_track_tail, args=(self.timestamp_queue, self.param_queue,), name='tracking process')

        # Daemons are auto-killed by parents (= safer with accidents) but can't spawn child processes themselves (which is fine)
        self.acquisition_process.daemon = True
        self.tracking_process.daemon = True

        # Setup callback functions for the control panel GUI
        self.connect_control_callbacks()

        # Timers to update GUI
        self.gui_timer = QTimer()
        self.gui_timer.setInterval(50)  # millisecond
        self.gui_timer.timeout.connect(self.update_data_panels)  # define callback

        self.acquisition_process.start()
        self.tracking_process.start()
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
        self.camera_panel.tail_standard.sigRegionChangeFinished.connect(self.update_parameters)
        self.control_panel.show_raw_checkbox.stateChanged.connect(self.update_parameters)
        self.control_panel.color_invert_checkbox.stateChanged.connect(self.update_parameters)
        self.control_panel.image_scale_box.editingFinished.connect(self.update_parameters)
        self.control_panel.filter_size_slider.sliderReleased.connect(self.update_parameters)
        self.control_panel.clip_threshold_slider.sliderReleased.connect(self.update_parameters)

    """
    Methods called continuously during the run
    """

    def update_data_panels(self):
        """
        Update Camera and Angle Panels
        This method should be called at like 20 Hz tops
        """

        # reconstitute frame from the shared 1d array (casting because the array is uint8)
        if self.parameters.show_raw:
            frame_array = self.current_raw_frame
        else:
            frame_array = self.current_processed_frame

        # if the frame_array is empty (in which case we do not have the size encoded at the end)
        # skip the image update
        if (frame_array[-1]>0) or (frame_array[-2]>0):
            self.camera_panel.set_image(decode_array_to_frame(frame_array))

        # Adjust factor for tracked tail visualization
        if self.parameters.show_raw:
            factor = 1.0 / self.parameters.image_scale
        else:
            factor = 1.0

        # camera panel tracked tail line update
        self.camera_panel.update_tracked_tail(self.current_segments[:, :self.parameters.n_segments+1], factor=factor)

        # angle panel update
        sort_ind = np.argsort(self.angle_history[1, :])
        self.angle_panel.set_data(self.angle_history[1,sort_ind]-np.max(self.angle_history[1,:]),
                                  self.angle_history[0, sort_ind]) # todo somehow make this smarter

        # show frame rate
        if any(self.angle_history[1, :]>0):
            valid_timestamps = self.angle_history[1, :][self.angle_history[1, :]>0]
            self.message_strip.setText('Median frame rate = {:0.2f} Hz'.format(1 / np.median(np.diff(valid_timestamps))))

    def update_parameters(self):
        """
        Called upon any user action on the ControlPanel or movements of the tail standard.
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
        if new_iscale!=self.parameters.image_scale and not self.parameters.show_raw: # if we changed the scale
            self.camera_panel.rescale_tail_standard(new_iscale / self.parameters.image_scale)

        # Insert the new values to the parameter object
        self.parameters.show_raw = new_sr
        self.parameters.color_invert = new_inv
        self.parameters.image_scale = new_iscale
        self.parameters.filter_size = int(new_fsize) # I think sliders return float?
        self.parameters.clip_threshold = int(new_cthresh)

        # also log tail standard position into parameter object, so we can easily pass them to the tracking process
        factor = 1.0
        if self.parameters.show_raw:
            factor = self.parameters.image_scale
        base, tip = self.camera_panel.get_base_tip_position(factor)
        self.parameters.base_x, self.parameters.base_y = base
        self.parameters.tip_x, self.parameters.tip_y = tip

        # force new values on GUI (relevant for lineedits)
        self.control_panel.set_current_value(self.parameters)

        # flag level readjustment
        self.camera_panel.level_adjust_flag = True

        # Send parameter to the child process running the tracker through the queue
        self.param_queue.put(self.parameters.__dict__)

    """
    Methods called once at the end
    """
    def closeEvent(self, event):
        """
        This will be called when the main window is closed.
        Release resources for graceful exit.
        """
        self.parameters.save_config_into_json() # save current config to the file
        self.camera.exit_acquisition_event.set() # ping the child process, exit acquisition while loop
        self.tracker.exit_acquisition_event.set()
        time.sleep(0.01) # Just to make sure that we see the end of acquisition loop before killing the process...
        self.acquisition_process.kill() # kill the child process
        self.tracking_process.kill()
        self.gui_timer.stop()

        # close and unlink shared memories
        for attr in dir(self):
            if type(getattr(self, attr)) == shared_memory.SharedMemory:
                print('closing shared memory',attr)
                getattr(self, attr).close()
                getattr(self, attr).unlink()



"""
Instantiate the application
"""

if __name__ == '__main__':
    # Initialize multiprocessing context -- this relates to the interpreter itself I think
    mp.set_start_method('spawn')
    # Prepare the PyQt Application
    app = QApplication([])
    # Instantiate the main GUI window
    win = MiniZFTT()
    # show the window
    win.show()
    # start the application (exit the interpreter once the app closes)
    sys.exit(app.exec_())