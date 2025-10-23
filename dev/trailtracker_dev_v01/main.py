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

import qdarkstyle

from utils import decode_array_to_frame
from camera import SelectCameraByName
from panels import CameraPanel, AnglePanel, ControlPanel
from tracker import TrackerObject
from parameters import TrackerParamObject

# TO DO: Make the parameter QObject and combine things through signals

class MiniZFTT(QMainWindow):
    """
    Main tail tracker GUI window class.
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

        # Prepare the parameter object, and load config
        # Note that the parameter object inherits QObject and can emit signals
        self.param = TrackerParamObject()
        self.param.load_config_from_json()

        # Create other widgets & arrange them onto the main window
        self.camera_panel = CameraPanel(**self.param.__dict__)
        self.angle_panel = AnglePanel()
        self.control_panel = ControlPanel()
        self.message_strip = QLabel()
        self.arrange_widgets()

        ## Select camera / create a camera object
        # The camera object runs in a separate child process, and continuously read camera frames in a while loop,
        # and put the camera frame into the shared memory, which can be accessed from other processes.
        self.camera = SelectCameraByName(self.param.camera_type, **self.param.__dict__)

        ## Create a tracker object
        # The tracker object runs in a separate child process, and continuously run the tracking algorithm on the
        # acquired camera frame that is copied into the shared memory. Then the tracker object will send back the
        # tail angle history back to the main window through a shared memory so it can be plotted on the main GUI.
        # In addition, the tracker object will send the tail angle with associated time stamp to whatever stimulus
        # program through a named pipe using multiprocessing.Listener().
        self.tracker = TrackerObject(self.param.__dict__)

        ## Prepare shared_memory so we can pass around data across processes
        # We use shared memory because it is faster and less CPU-intensive than Queue, which require each process to
        # pickle/unpickle data which becomes more time-consuming as the data gets bigger.

        # Memory for raw and processed image data. Because we do not know the camera frame size until we kick-start
        # the camera process, we just reserve 1MB each for these
        self.raw_frame_memory = shared_memory.SharedMemory(create=True, name='raw_frame_memory', size=1000000)
        self.processed_frame_memory = shared_memory.SharedMemory(create=True, name='processed_frame_memory', size=1000000)

        # Memory for storing the latest tracked segment positions for the sake of visualization.
        # Max 10 segments x {x, y} x float64 (8 bytes) = 160 bytes
        self.segment_memory = shared_memory.SharedMemory(create=True, name='segment_memory', size=160)

        # Memory for the history of the tail angle and associated time stamps.
        # length is decided by angle_trace_length parameter (x 8byte float x 2)
        self.angle_memory = shared_memory.SharedMemory(create=True, name='angle_memory', size=16*self.param.angle_trace_length)

        ## Create numpy arrays that refers to the shared memory we allocated
        # For the raw and processed image frames, we store data as 1d array, because the shape of the frame can
        # dynamically change. We will reshape these 1d array into 2d whenever we need to perform operations on 2d.
        self.current_raw_frame = np.ndarray((1000000,), dtype=np.uint8, buffer=self.raw_frame_memory.buf)
        self.current_processed_frame = np.ndarray((1000000,), dtype=np.uint8, buffer=self.processed_frame_memory.buf)
        self.current_segments = np.ndarray((2, 10), dtype=np.float64, buffer=self.segment_memory.buf)
        self.angle_history = np.ndarray((2, self.param.angle_trace_length), dtype=np.float64, buffer=self.angle_memory.buf)
        self.angle_history[:] = 0 # initialize

        ## Create Queues
        # We still use queues for timestamps and parameters. Everytime the tracking process receives a new timestamp
        # from the camera process through the queue, it redoes the tracking. Without this queue, the tracking process
        # wouldn't know if the shared frame memory was updated or not.
        self.timestamp_queue = mp.Queue(maxsize=10) # pass timestamps
        self.param_queue = mp.Queue(maxsize=10) # passing parameters to the tracking process

        # Send the initial parameter, because the tracking process needs a parameter for initialization
        self.param_queue.put(self.param.__dict__)

        ## Delegate frame acquisition to a child process
        # By calling mp.Process, we create a child process and send a copy of the camera/tracker objects there.
        # These objects will be Pickled to be copied, and there are certain things that cannot be pickled (e.g.,
        # things with non-python backend, file handles etc.). or this reason, we call the camera initialization
        # in the child process, at the beginning of the continuous acquisition process (rather than in the constructor).
        # In the child process, methods specified as 'targets' will run -- both of which run continuously with a while
        # loop.
        self.acquisition_process = mp.Process(target=self.camera.continuously_acquire_frames, args=(self.timestamp_queue,), name='acquisition process')
        self.tracking_process = mp.Process(target=self.tracker.continuously_track_tail, args=(self.timestamp_queue, self.param_queue,), name='tracking process')

        # Set child processes to be Daemons. If you don't do this, when the main process crashes, the child processes
        # does not shut down like zombies
        self.acquisition_process.daemon = True
        self.tracking_process.daemon = True

        # Setup callback functions for the control panel GUI.
        self.connect_control_callbacks()

        # Timers to update GUI
        self.gui_timer = QTimer()
        self.gui_timer.setInterval(50)  # millisecond
        self.gui_timer.timeout.connect(self.update_data_panels)  # define callback

        # kick-start child processes and the GUI timer
        self.acquisition_process.start()
        self.tracking_process.start()
        self.gui_timer.start()

    def arrange_widgets(self):
        """
        Separate out cosmetics out of the constructor for readability
        Arrange panels into a single container in the main window
        """
        # set window title and size
        self.setWindowTitle("minizftt_dev v01")  # window title
        self.setGeometry(50, 50, 400, 600)  # default window position and size (x, y, w, h)

        # Insert initial values from config into control panel GUI by passing the parameter object
        self.control_panel.refresh_gui(self.param)

        # The main window needs to have a single, central widget (which is just an empty container).
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
        ## If anything is changed in the camera panel or the control panel, refresh parameters
        self.camera_panel.tail_standard.sigRegionChangeFinished.connect(self.refresh_param)
        self.control_panel.show_raw_checkbox.stateChanged.connect(self.refresh_param)
        self.control_panel.color_invert_checkbox.stateChanged.connect(self.refresh_param)
        self.control_panel.image_scale_box.editingFinished.connect(self.refresh_param)
        self.control_panel.filter_size_slider.sliderReleased.connect(self.refresh_param)
        self.control_panel.clip_threshold_slider.sliderReleased.connect(self.refresh_param)

        ## If the parameter is changed, updated the control panel GUI
        # the paramChanged signal has a float argument for the tail rescaling factor (signified as f here)
        self.param.paramChanged.connect(lambda f, p=self.param : self.control_panel.refresh_gui(p))
        self.param.paramChanged.connect(lambda f  : self.camera_panel.refresh_gui(f))

        # Connect button callback
        self.control_panel.connect_button.clicked.connect(self.tracker.attempt_connection_event.set)
        self.control_panel.connect_button.clicked.connect(lambda: self.control_panel.connect_button.force_state(True))
    """
    Methods called continuously during the run
    """

    def update_data_panels(self):
        """
        Update Camera and Angle Panels (and also some stuff in the control panel)
        This method will be called at like 20 Hz tops as the timer callback
        """

        ## Reconstitute frame to show
        # Frames are stored in memory block shared between processes as 1d array. We need to select either raw or
        # processed data, and then reconstruct them into 2d array from 1d (we do this 1d trick, because we don't
        # know the shape of the frames beforehand when we set up child processes. The size of the frames are encoded
        # at the end of the 1d arrays.
        if self.param.show_raw:
            frame_array = self.current_raw_frame
        else:
            frame_array = self.current_processed_frame
        # If the frame_array is empty (in which case we do not have the size encoded at the end) skip the image update
        if (frame_array[-1]>0) or (frame_array[-2]>0):
            self.camera_panel.set_image(decode_array_to_frame(frame_array))

        # Tracked tail segment positions are in the pixel coordinate of the processed (potentially resized) images.
        # If we are showing the raw frame, we need to account for the resizing factor.
        if self.param.show_raw:
            factor = 1.0 / self.param.image_scale
        else:
            factor = 1.0

        ## Camera panel tracked tail line update
        # We need slicing because we are preparing a bit longer shared array for segment position, just in case if
        # we wanted to update #segments dynamically)
        self.camera_panel.update_tracked_tail(self.current_segments[:, :self.param.n_segments+1], factor=factor)

        ## Angle history plot update
        if any(self.angle_history[1, :] > 0):
            # Roll the array so that the timestamp is monotonically increasing -- otherwise there will be weird
            # line connecting the head and tail
            head_index = np.argmax(self.angle_history[1, :])
            latest_t = self.angle_history[1, head_index]
            rolled_data = np.roll(self.angle_history[:, self.angle_history[1,:]>0], -head_index-1, axis=1)
            self.angle_panel.set_data(rolled_data[1, :]-latest_t, rolled_data[0, :])

            # Indicate frame rate (average for 100 frames, because if we do this every frame it is to jitterly to read)
            if rolled_data.shape[1] > 101:
                frame_rate = 100/(latest_t - rolled_data[1, -101])
                self.message_strip.setText('Median frame rate = {:0.2f} Hz'.format(frame_rate))

        ## Control panel -- connect button update
        if self.tracker.connection_lost_event.is_set():
            self.tracker.connection_lost_event.clear()
            self.control_panel.connect_button.force_state(False)

    def refresh_param(self):
        """
        Called upon any user action on the ControlPanel or movements of the tail standard.
        Read values from the GUI widgets, put them into the parameter (if valid), and emit paramChanged signal.
        The actual GUI refresh would be triggered by this signal (here I am trying to avoid directly calling
        gui update methods from here but making them go through signals, for the sake of modularity).
        """

        # Read the current content of the GUI widgets
        new_sr, new_inv, new_iscale, new_fsize, new_cthresh = self.control_panel.return_current_value()

        # Before overwriting the old parameters, check if we need to adjust the tail ROI
        # Because the segment position from the tracking algorithms are in the coordinate of the preprocessed
        # (potentially resized) images, we need to adjust their scales every time we switch between showing raw vs.
        # processed images or changing the resizing factor. We pass this tail_rescale_factor through the paramChanged
        # signal argument to the camera_panel gui_refresh method.
        tail_rescale_factor = 1.0
        if new_sr and not self.param.show_raw: # if we switched from processed to raw
            tail_rescale_factor = 1.0 / self.param.image_scale
        if not new_sr and self.param.show_raw: # if we switched from raw to processed
            tail_rescale_factor = self.param.image_scale
        if new_iscale!=self.param.image_scale and not self.param.show_raw: # if we changed the scale
            tail_rescale_factor = new_iscale / self.param.image_scale

        # In the param object, we keep the tail standard positions in the rescaled image pixel coordinate
        # We need to update these, if (a) the tail standard was moved from the GUI, (b) image scale was changed

        # account for image scale change
        tail_param_scale_factor = new_iscale / self.param.image_scale
        # account for raw image visualization
        if self.param.show_raw:
            tail_param_scale_factor *= self.param.image_scale

        base, tip = self.camera_panel.get_base_tip_position(tail_param_scale_factor)
        self.param.base_x, self.param.base_y = base
        self.param.tip_x, self.param.tip_y = tip

        # Insert the new values to the parameter object
        self.param.show_raw = new_sr
        self.param.color_invert = new_inv
        self.param.image_scale = new_iscale
        self.param.filter_size = int(new_fsize) # I think sliders return float?
        self.param.clip_threshold = int(new_cthresh)

        # Emit parameter change signal (will trigger GUI update)
        self.param.paramChanged.emit(tail_rescale_factor)

        # Send parameter to the child process running the tracker through the queue
        self.param_queue.put(self.param.__dict__)


    """
    Methods called once at the end
    """
    def closeEvent(self, event):
        """
        This will be called when the main window is closed.
        Release resources for graceful exit.
        """
        self.param.save_config_into_json() # save current config to the file
        self.camera.exit_acquisition_event.set() # ping the child process, exit acquisition while loop
        self.tracker.exit_acquisition_event.set()
        time.sleep(0.01) # Just to make sure that we see the end of acquisition loop before killing the process...
        self.acquisition_process.kill() # kill the child process
        self.tracking_process.kill()
        self.gui_timer.stop()

        # close and unlink shared memories
        for attr in dir(self):
            if type(getattr(self, attr)) == shared_memory.SharedMemory:
                print('[MiniZFTT] closing shared memory',attr)
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
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    # Instantiate the main GUI window
    win = MiniZFTT()
    # show the window
    win.show()
    # start the application (exit the interpreter once the app closes)
    sys.exit(app.exec_())