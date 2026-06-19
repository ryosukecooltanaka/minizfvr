import numpy as np
import multiprocessing as mp
import cv2
from multiprocessing import shared_memory
from multiprocessing.connection import Listener
from queue import Empty
from ..utils import encode_frame_to_array, decode_array_to_frame
from .fsutils import detect_fish



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
        listener = Listener(('localhost', self.param['localhost_port']))

        # Initially there is no connection -- this will be used to update the connect button in the GUI
        self.connection_lost_event.set()

        # placeholder for the background image
        bg_image = None
        bg_update_flag = False
        fish_mask = None

        # For dt calculation
        timestamp = 0
        last_timestamp = -1

        # index of the tracked frames
        ii: np.int32 = 0

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
                dt = timestamp - last_timestamp 

                # Get the content of the frame queue (from the camera process)
                frame = decode_array_to_frame(self.shared_arrays['current_raw_frame']) 

                # If this is the very first frame, store that as a background
                if bg_image is None:
                    bg_image = np.zeros(frame.shape, dtype=np.uint8)
                    bg_image = bg_image + frame
                    fish_mask = np.zeros(bg_image.shape)

                # do the preprocessing - now the returned values are 1d arrays!
                fish_x, fish_y, angle, processed_frame, frect = detect_fish(frame, bg_image, 
                                            image_scale=self.param['image_scale'],
                                            dilate_size=self.param['dilate_size'],
                                            color_invert=self.param['color_invert'],
                                            body_threshold=self.param['body_threshold'],
                                            real_fish_px_range=(self.param['min_area_mm2']/self.param['mm_per_px']**2, 
                                                                self.param['max_area_mm2']/self.param['mm_per_px']**2),
                                            n_fish_to_track=self.param['n_fish_to_track'])
                
                if ii > 1:
                    # We don't really want to be solving correspondence problems
                    # so we just assume some fish is swimming and raise background update flag
                    bg_update_flag = True

                if bg_update_flag:
                    # to avoid "baking in" fish into the background, only select non-fish area for
                    # background update
                    fish_mask *= 0.0
                    for k in range(len(frect[0])):
                        fish_mask[frect[1][k]:(frect[1][k]+frect[3][k]), frect[0][k]:(frect[0][k]+frect[2][k])] = 1.0
                    bg_image = ((fish_mask + (1-self.param['bg_alpha'])*(1.0-fish_mask)) * bg_image +
                            self.param['bg_alpha'] * (1.0-fish_mask) * frame).astype(np.uint8)

                # Disabling communication for the multi-tracking version
                # self.send_results_through_pipe(timestamp, fish_x, fish_y, angle) 

                # write results into the shared memory array so the main process can see it
                # note that this function mutate the content of the input array
                if self.param['show_bg']:
                    encode_frame_to_array(bg_image, self.shared_arrays['current_processed_frame'])
                else:
                    encode_frame_to_array(processed_frame, self.shared_arrays['current_processed_frame'])

                n_fish_tracked = len(fish_x)
                for k in range(self.param['n_fish_to_track']):
                    if k < n_fish_tracked:
                        self.shared_arrays['tracking_history'][0, ii% self.param['trace_length']] = fish_x[k]
                        self.shared_arrays['tracking_history'][1, ii% self.param['trace_length']] = fish_y[k]
                        self.shared_arrays['tracking_history'][2, ii% self.param['trace_length']] = (angle[k] + np.pi) % (np.pi * 2.0) - np.pi
                    else:
                        self.shared_arrays['tracking_history'][:, ii% self.param['trace_length']] = np.nan
                    self.shared_arrays['timestamp_buffer'][ii% self.param['trace_length']] = timestamp
                    self.shared_arrays['index_buffer'][ii% self.param['trace_length']] = ii
                    ii += 1
                last_timestamp = timestamp

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

        # specify memory names, size, and type so I can establish access to them concisely using dict comprehension

        shared_memory_names = (
            'raw_frame_memory',
            'processed_frame_memory',
            'tracking_memory',
            'timestamp_memory',
            'index_memory'
        )

        # The sizes of ndarrays are hard-coded without referencing the memory size, because memory size cannot be
        # an arbitrary number and can be different from what we specified in the parent process
        shared_memory_shape_type_pairs = (
            ((1000000,), np.uint8),
            ((1000000,), np.uint8),
            ((3, self.param['trace_length']), np.float64),
            ((self.param['trace_length'],), np.float64),
            ((self.param['trace_length'],), np.int32)
        )

        array_names = (
            'current_raw_frame',
            'current_processed_frame',
            'tracking_history',
            'timestamp_buffer',
            'index_buffer'
        )

        self.shared_memories = {sm_name: shared_memory.SharedMemory(name=sm_name) for sm_name in shared_memory_names}
        self.shared_arrays = {ar_name: np.ndarray(smst[0], dtype=smst[1], buffer=self.shared_memories[sm_name].buf) 
                              for ar_name, smst, sm_name in zip(array_names, shared_memory_shape_type_pairs, shared_memory_names)}


    def send_results_through_pipe(self, t, x, y, theta):
        """
        Send tracking results to whatever stimulus presentation program through the named Pipe
        Not called in this feature branch
        """

        if self.conn is not None:
            try:
                self.conn.send((t, x, y, theta))
            except ConnectionError:
                print('[Tracker] Connection to the stimulus program is lost!', flush=True)
                self.conn = None
                self.connection_lost_event.set()


