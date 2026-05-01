"""

free swimming fish tracking app

Started on 2026/04/21 Ryosuke Tanaka

Copied from minizftt

Overall multiprocessing architecture is the same as minizftt:
- Main app manages GUI, spawn child processes taking care of frame acquisition, tracking and communciation.
- The Camera object (a child process) continuously fetch frames from the camera at whatever frequency the hardware is running.
  The acquired frame is written into a pre-allocated shared memory, and the acquisition event is signaled through an Event object
- The Tracker object (another child process) runs the tracking algorithm on the image in the shared memory.
  The tracking results would be put into another shared memory visible from the main process for the sake of visualization,
  as well as being sent to a named pipe (for stimulus programs to use them).
- Passing of parameters from the main GUI to the child processes (mainly the Tracker) will be done through a Queue

"""

import numpy as np
import sys
import multiprocessing as mp
from multiprocessing import shared_memory
from pathlib import Path
import time

from PyQt5.QtCore import QTimer, QSize
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QLabel
)
from PyQt5.QtGui import QIcon

import qdarkstyle

from ..utils import decode_array_to_frame, set_icon, messageLabel
from minizfvr.minizftt.camera import SelectCameraByName
from .panels import CameraPanel, ControlPanel
from .tracker import TrackerObject
from .parameters import FSParamObject
from .saver import Saver

# TO DO: Make the parameter QObject and combine things through signals

class MiniZFFS(QMainWindow):
    """
    Main tail minizffs GUI window class.
    Displays fish image, position trace, and other controls.
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
        self.param = FSParamObject()
        self.param.load_config_from_json(self.param.config_path)

        # Create other widgets & arrange them onto the main window
        self.camera_panel = CameraPanel(**self.param.__dict__)
        self.camera_panel.switch_colormap(self.param.show_raw) # set colormap
        self.control_panel = ControlPanel()
        self.message_strip = messageLabel()
        self.arrange_widgets()

        ## Select camera / create a camera object
        # The camera object runs in a separate child process, and continuously read camera frames in a while loop,
        # and put the camera frame into the shared memory, which can be accessed from other processes.
        self.camera = SelectCameraByName(self.param.camera_type, **self.param.__dict__)

        ## Create a Tracker object
        # The Tracker object runs in a separate child process, and continuously run the tracking algorithm on the
        # acquired camera frame that is copied into the shared memory. Then the Tracker object will send back the
        # traced position history back to the main window through a shared memory so it can be plotted on the main GUI.
        # In addition, the Tracker object will send the fish position with associated time stamp to whatever stimulus
        # program through a named pipe using multiprocessing.Listener().
        self.tracker = TrackerObject(self.param.__dict__)

        ## Prepare shared_memory so we can pass around data across processes
        # We use shared memory because it is faster and less CPU-intensive than Queue, which require each process to
        # pickle/unpickle data which becomes more time-consuming as the data gets bigger.

        # Memory for raw and processed image data. Because we do not know the camera frame size until we kick-start
        # the camera process, we just reserve 1MB each for these
        self.raw_frame_memory = shared_memory.SharedMemory(create=True, name='raw_frame_memory', size=1000000)
        self.processed_frame_memory = shared_memory.SharedMemory(create=True, name='processed_frame_memory', size=1000000)

        # Memory for the history of the x, y position / angle and associated time stamps.
        # length is decided by trace_length parameter (x 8byte float x 4)
        self.tracking_memory = shared_memory.SharedMemory(create=True, name='tracking_memory', size=32*self.param.trace_length)
        # For the sake of saving, we need to keep track how manieth sample we have written
        # We use uint32, which would not cause overflow for 4 month with 200 Hz tracking
        self.index_memory = shared_memory.SharedMemory(create=True, name='index_memory', size=4*self.param.trace_length)

        ## Create numpy arrays that refers to the shared memory we allocated
        # For the raw and processed image frames, we store data as 1d array, because the shape of the frame can
        # dynamically change. We will reshape these 1d array into 2d whenever we need to perform operations on 2d.
        self.current_raw_frame = np.ndarray((1000000,), dtype=np.uint8, buffer=self.raw_frame_memory.buf)
        self.current_processed_frame = np.ndarray((1000000,), dtype=np.uint8, buffer=self.processed_frame_memory.buf)
        self.tracking_history = np.ndarray((4, self.param.trace_length), dtype=np.float64, buffer=self.tracking_memory.buf)
        self.tracking_history[:] = 0 # initialize
        self.index_buffer = np.ndarray((self.param.trace_length, ), dtype=np.int32, buffer=self.index_memory.buf)
        self.index_buffer[:] = -1

        ## Create Queues
        # We still use queues for timestamps and parameters. Everytime the tracking process receives a new timestamp
        # from the camera process through the queue, it redoes the tracking. Without this queue, the tracking process
        # wouldn't know if the shared frame memory was updated or not.
        self.timestamp_queue = mp.Queue(maxsize=10) # pass timestamps
        self.param_queue = mp.Queue(maxsize=10) # passing parameters to the tracking process

        # Send the initial parameter, because the tracking process needs a parameter for initialization
        self.param_queue.put(self.param.__dict__)

        ## Delegate frame acquisition to a child process
        # By calling mp.Process, we create a child process and send a copy of the camera/minizftt objects there.
        # These objects will be Pickled to be copied, and there are certain things that cannot be pickled (e.g.,
        # things with non-python backend, file handles etc.). For this reason, we call the camera initialization
        # in the child process, at the beginning of the continuous acquisition process (rather than in the constructor).
        # In the child process, methods specified as 'targets' will run -- both of which run continuously with a while
        # loop.
        self.acquisition_process = mp.Process(target=self.camera.continuously_acquire_frames, args=(self.timestamp_queue,), name='acquisition process')
        self.tracking_process = mp.Process(target=self.tracker.continuously_track_tail, args=(self.timestamp_queue, self.param_queue,), name='tracking process')

        # Set child processes to be Daemons. If you don't do this, when the main process crashes, the child processes
        # does not shut down like zombies
        self.acquisition_process.daemon = True
        self.tracking_process.daemon = True

        ## Prepare a saver object to handle saving
        self.saver = Saver(self.tracking_history, self.index_buffer, self.param)

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
        self.setWindowTitle("minizffs")  # window title
        self.setGeometry(50, 50, 400, 600)  # default window position and size (x, y, w, h)
        set_icon(self)

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
        layout.addWidget(self.control_panel)
        layout.addWidget(self.message_strip)

        # Adjust height ratios
        layout.setStretch(0, 30)
        layout.setStretch(1, 9)
        layout.setStretch(2, 1)

        container.setLayout(layout)

    def connect_control_callbacks(self):
        ## If anything is changed in the camera panel or the control panel, refresh parameters
        events_to_trigger_param_refresh = (
            self.camera_panel.fish_area.sigRegionChangeFinished,
            self.control_panel.show_raw_checkbox.stateChanged,
            self.control_panel.show_bg_checkbox.stateChanged,
            self.control_panel.color_invert_checkbox.stateChanged,
            self.control_panel.image_scale_box.editingFinished,
            self.control_panel.dilate_size_box.editingFinished,
            self.control_panel.body_threshold_box.editingFinished,
            self.control_panel.save_duration_box.editingFinished
        )
        for ettpr in events_to_trigger_param_refresh:
            ettpr.connect(self.refresh_param)

        # Show the processed image with pseudocolor
        self.control_panel.show_raw_checkbox.stateChanged.connect(lambda f : self.camera_panel.switch_colormap(f))

        ## If the parameter is changed, updated the control panel GUI
        # the paramChanged signal has a float argument for the tail rescaling factor (signified as f here)
        self.param.paramChanged.connect(lambda f, p=self.param : self.control_panel.refresh_gui(p))
        self.param.paramChanged.connect(lambda f  : self.camera_panel.refresh_gui(f))

        # save panel callback
        self.control_panel.save_button.clicked.connect(self.control_panel.save_button.switch_state)
        self.control_panel.save_button.clicked.connect(lambda: self.saver.toggle_save_state(self.control_panel.save_button.activated))

        # Connect button callback
        self.control_panel.connect_button.clicked.connect(self.tracker.attempt_connection_event.set)
        self.control_panel.connect_button.clicked.connect(lambda: self.control_panel.connect_button.force_state(True))

    """
    Methods called continuously during the run
    """

    def update_data_panels(self):
        """
        Update Camera and Trace Panels (and also some stuff in the control panel)
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
        if not self.param.show_raw:
            factor = self.param.image_scale
        else:
            factor = 1.0

        if any(self.tracking_history[1, :] > 0):
            # find the index of the latest data
            head_index = np.argmax(self.tracking_history[-1, :])

            # Roll the array so that the timestamp is monotonically increasing -- otherwise there will be weird
            # line connecting the head and tail
            latest_t = self.tracking_history[-1, head_index]
            rolled_data = np.roll(self.tracking_history[:, self.tracking_history[-1,:]>0], -head_index-1, axis=1)

            # Indicate frame rate (average for 100 frames, because if we do this every frame it is too jitterly to read)
            if rolled_data.shape[1] > 101:
                frame_rate = 100/(latest_t - rolled_data[-1, -101])
                self.message_strip.update_message('Median frame rate = {:0.2f} Hz'.format(frame_rate), 0)

            # plot
            self.camera_panel.update_tracked_fish(rolled_data, factor)

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
        new_sr, new_sb, new_inv, new_iscale, new_dsize, new_bthresh, new_sd = self.control_panel.return_current_value()

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
        # (i.e., the one that can be directly used for tracking, rather htan visualization)
        # We need to update these, if (a) the tail standard was moved from the GUI, (b) image scale was changed

        # account for image scale change
        tail_param_scale_factor = new_iscale / self.param.image_scale
        # account for raw image visualization
        if self.param.show_raw:
            tail_param_scale_factor *= self.param.image_scale

        pos, size = self.camera_panel.get_area_spec(tail_param_scale_factor)
        self.param.roi_x, self.param.roi_y = pos
        self.param.roi_w, self.param.roi_h = size

        # show roi size (always in the raw coordinate)
        self.message_strip.update_message(
            'ROI size (raw) = {0:.0f}/{1:.0f} px'.format(size[0]/self.param.image_scale,size[1]/self.param.image_scale), 1)

        # Also, we want to adapt the search area size to the tail standard length,
        # because when the search area is too big (say, bigger than each segment)
        # the intensity center-of-mass can "go back" on the actual tail

        # Insert the new values to the parameter object
        self.param.show_raw = new_sr
        self.param.show_bg = new_sb
        self.param.color_invert = new_inv
        self.param.image_scale = new_iscale
        self.param.dilate_size = new_dsize
        self.param.body_threshold = new_bthresh
        self.param.save_duration = new_sd

        # Emit parameter change signal (will trigger GUI update)
        self.param.paramChanged.emit(tail_rescale_factor)

        # Send parameter to the child process running the minizftt through the queue
        self.param_queue.put(self.param.__dict__)

    """
    Methods called once at the end
    """
    def closeEvent(self, event):
        """
        This will be called when the main window is closed.
        Release resources for graceful exit.
        """
        self.param.save_config_into_json(self.param.config_path) # save current config to the file
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
    win = MiniZFFS()
    # show the window
    win.show()
    # start the application (exit the interpreter once the app closes)
    sys.exit(app.exec_())