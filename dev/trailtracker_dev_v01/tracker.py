import numpy as np
import multiprocessing as mp
from multiprocessing import shared_memory
from multiprocessing.connection import Listener
from queue import Empty
from utils import preprocess_image, center_of_mass_based_tracking, encode_frame_to_array, decode_array_to_frame


class TrackerObject():
    """
    This object reads the acquired camera frame from the shared memory, and performs the preprocessing & tracking
    on it, and return the results into other shared memory. In addition, the results of tracking will be sent to
    the stimulus programs through a named pipe. These operations are performed continuously in a while loop in the
    continuously_track_tail() method. The while loop ensures that the acquired frame is immediately processed for
    closed loop with minimal lag. So as not to block the GUI for the while loop, this task will be delegated to
    a child process using the multiprocessing module.
    """

    def __init__(self, param_dict):
        """
        Constructor
        Note that this object will be pickled and copied into a child process. Thus, we cannot hold any complex
        object as an instance attribute.
        """

        # initial parameter will be loaded from an obligate argument
        self.param = param_dict # this will be a parameter dictionary

        # Event() object are boolean flags that can be accessed across processes
        self.exit_acquisition_event = mp.Event()  # this will be set true when the parent exits
        self.attempt_connection_event = mp.Event() # this will be set when we press Connect button in the GUI
        self.connection_lost_event = mp.Event() # We will set this when we lost connection, which will be read by the GUI update method

        # Placeholders for shared memories -- will be initialized in the child process
        self.shared_memories = None
        self.shared_arrays = None

        # A counter for angle history buffer update
        self.ii = 0

        # We will store connection object as an attribute (for the convenience)
        self.conn = None

    def continuously_track_tail(self, timestamp_queue, param_queue):
        """
        Continuously perform tail tracking (run in a child process)
        Receive parameters from param_queue (from the main process, if there is any change)
        Receive timestamp from the camera object through timestamp_queue
        If there is a new timestamp, that means there is a new frame to be processed, so we look into the shared memory
        and perform tail tracking on the frame
        Then, register the tail tracking results into another shared memory, as well as sending it to the stimulus
        program through the named pipe.
        """

        print('[Tracker] Start tracking process', flush=True)

        # initialize shared memory
        self.initialize_shared_memory()

        # Crate the connection (open the port)
        # I am hard-coding this here, as wrapping these things into an object and assigning this
        # as an instance attribute caused weird behaviors
        listener = Listener(('localhost', 6000))

        # Initially there is no connection -- this will be used to update the connect button in the GUI
        self.connection_lost_event.set()

        # Do the tracking continuously
        # We will exit this loop if we receive the flag from the main GUI
        while not self.exit_acquisition_event.is_set():

            # We try to open the connection when we click the connect button
            if self.attempt_connection_event.is_set() and self.conn is None:
                print('[Tracker] Attempting connection! Note there is no timeout for this', flush=True)
                try:
                    self.conn = listener.accept()
                    print('[Tracker] Connection to the stimulus program established', flush=True)
                except ConnectionError:
                    print('[Tracker] listner.accept() failed', flush=True)
                    self.connection_lost_event.set()
            self.attempt_connection_event.clear()


            # Check parameter queue for new parameters
            # We use try/catch as opposed to queue.empty(), because apparently the latter is not reliable
            try:
                self.param = param_queue.get_nowait()
                print('[Tracker] New parameter received from the queue', flush=True)
            except Empty:
                pass

            # If there is any new timestamp in the queue that is not processed, that means that the frame in the
            # shared memory is new. So we do tracking
            try:
                timestamp = timestamp_queue.get_nowait()

                # get the content of the frame queue (from the camera process)
                frame = decode_array_to_frame(self.shared_arrays['current_raw_frame'])

                # do the preprocessing
                processed_frame = preprocess_image(frame, **self.param)

                # do the tracking
                segments, angles = center_of_mass_based_tracking(processed_frame,
                                                                 (self.param['base_x'], self.param['base_y']),
                                                                 (self.param['tip_x'], self.param['tip_y']),
                                                                  self.param['n_segments'],
                                                                  self.param['search_area'])

                d_angle = float(angles[-1]-angles[0])

                # send tracking results to stimulus program through the named pipe
                self.send_angle_through_pipe(timestamp, d_angle)

                # write results into the shared memory array so the main process can see it
                # note that this function mutate the content of the input array
                encode_frame_to_array(processed_frame, self.shared_arrays['current_processed_frame'])
                self.shared_arrays['current_segment'][:, :self.param['n_segments']+1] = segments[:]
                self.shared_arrays['angle_history'][0, self.ii] = d_angle
                self.shared_arrays['angle_history'][1, self.ii] = timestamp
                self.ii = (self.ii + 1) % self.param['angle_trace_length']

            except Empty:
                pass


        print('[Tracker] Exited tracking while loop!', flush=True)
        [self.shared_memories[x].close() for x in self.shared_memories.keys()]
        if self.conn is not None:
            self.conn.close()
        listener.close()

    def initialize_shared_memory(self):
        """
        Create handles for shared memories (referred to by names) as well as numpy arrays that refer to these
        memory addresses.
        Organizing them in a list just because I wanted to have some hiearchy...
        """

        self.shared_memories = dict(
            raw_frame_memory       = shared_memory.SharedMemory(name='raw_frame_memory'),
            processed_frame_memory = shared_memory.SharedMemory(name='processed_frame_memory'),
            segment_memory = shared_memory.SharedMemory(name='segment_memory'),
            angle_memory   = shared_memory.SharedMemory(name='angle_memory')
        )

        # The sizes of ndarrays are hard-coded without referencing the memory size, because memory size cannot be
        # an arbitrary number and can be different from what we specified in the parent process
        self.shared_arrays = dict(
            current_raw_frame        = np.ndarray((1000000,), dtype=np.uint8, buffer=self.shared_memories['raw_frame_memory'].buf),
            current_processed_frame  = np.ndarray((1000000,), dtype=np.uint8, buffer=self.shared_memories['processed_frame_memory'].buf),
            current_segment = np.ndarray((2, 10), dtype=np.float64, buffer=self.shared_memories['segment_memory'].buf),
            angle_history   = np.ndarray((2, self.param['angle_trace_length']), dtype=np.float64, buffer=self.shared_memories['angle_memory'].buf)
        )

    def send_angle_through_pipe(self, timestamp, d_angle):
        """
        Send tracking results to whatever stimulus presentation program through the named Pipe
        """

        if self.conn is not None:
            try:
                self.conn.send((timestamp, d_angle))
            except ConnectionError:
                print('[Tracker] Connection to the stimulus program is lost!', flush=True)
                self.conn = None
                self.connection_lost_event.set()


