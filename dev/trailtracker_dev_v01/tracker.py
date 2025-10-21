import numpy as np
import multiprocessing as mp
from multiprocessing import shared_memory
from multiprocessing.connection import Listener
from queue import Empty
from time import sleep
from utils import preprocess_image, center_of_mass_based_tracking, encode_frame_to_array, decode_array_to_frame
from communication import Sender

class TrackerObject():
    """
    This object will receive captured frames and processing parameters from a queue,
    perform the tail tracking algorithm, and return the results to a queue.
    We are separating out tail tracking into an object, so we can delegate this
    to a separate process. This is important, because this is the most CPU heavy
    thing we do, and it is important we can do this fast.
    """

    def __init__(self, param_dict):
        self.param = param_dict # this will be a parameter dictionary
        self.exit_acquisition_event = mp.Event()  # this is a flag used to exit while loop, shared across processes
        self.connect_event = mp.Event()

        # placeholder for a dict of shared memory handles -- to be initialized upon the process start
        self.shared_memories = None
        # placeholder for a dict of ndarrays based off of the shared memory content
        self.shared_arrays = None


        # A counter for angle history buffer update
        self.ii = 0
        self.conn = None

    def continuously_track_tail(self, timestamp_queue, param_queue):
        """
        Continuously perform tail tracking (run in a child process)
        Read frames and parameters from the queues
        Put the results in the queue
        """
        print('Start tracking process')

        try:
            self.param = param_queue.get_nowait()
        except Empty:
            print('initial param load failed -- queue empty', flush=True)

        self.initialize_shared_memory()
        listener = Listener(('localhost', 6000))

        while not self.exit_acquisition_event.is_set():

            if self.connect_event.is_set():
                print('Connect event received by the tracker -- attempting to connect', flush=True)
                self.conn = listener.accept()
                self.connect_event.clear()

            # check parameter queue for new parameters -- parameter change happens very infrequently,
            # so I will assume that the param_queue is either empty or has only one entry
            try:
                self.param = param_queue.get_nowait()
                print('new parameter received', flush=True)
            except Empty:
                pass

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
                self.send_angle_through_pipe(d_angle, timestamp)

                # write results into the shared memory array so the main process can see it
                # note that this function mutate the content of the input array
                encode_frame_to_array(processed_frame, self.shared_arrays['current_processed_frame'])
                self.shared_arrays['current_segment'][:, :self.param['n_segments']+1] = segments[:]
                self.shared_arrays['angle_history'][0, self.ii] = d_angle
                self.shared_arrays['angle_history'][1, self.ii] = timestamp
                self.ii = (self.ii + 1) % self.param['angle_trace_length']
            except Empty:
                pass


        print('Exited tracking while loop!', flush=True)
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

    def send_angle_through_pipe(self, d_angle, timestamp):
        """
        Send tracking results to whatever stimulus presentation program through the named Pipe
        """

        if self.conn is not None:
            self.conn.send((d_angle, timestamp))

