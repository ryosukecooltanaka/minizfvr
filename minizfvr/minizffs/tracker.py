import numpy as np
import multiprocessing as mp
import cv2
from multiprocessing import shared_memory
from multiprocessing.connection import Listener
from queue import Empty
from ..utils import detect_fish_body, encode_frame_to_array, decode_array_to_frame



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
        listener = Listener(('localhost', self.param['localhost_port']))

        # Initially there is no connection -- this will be used to update the connect button in the GUI
        self.connection_lost_event.set()

        # placeholder for the background image
        bg_image = None
        bg_update_flag = False

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

                # Get the content of the frame queue (from the camera process)
                frame = decode_array_to_frame(self.shared_arrays['current_raw_frame']) 

                # If this is the very first frame, store that as a background
                if bg_image is None:
                    bg_image = np.zeros(frame.shape, dtype=np.uint8)
                    bg_image = bg_image + frame

                # do the preprocessing
                body_frame = detect_fish_body(frame, bg_image, **self.param)
                processed_frame = body_frame + cv2.threshold(cv2.subtract(bg_image, frame), self.param['head_threshold'], 100, cv2.THRESH_BINARY)[1]
                # Do the tracking
                # Each row of stats are structured as [x, y, w, h, area] 
                n_labels, _, stats, centroids = cv2.connectedComponentsWithStats(body_frame)

                if n_labels > 1:
                    # assume that the second biggest contiguous thing is the fish (1st being the background)
                    fish_id = np.argsort(-stats[:, -1])[1]
                    fish_x, fish_y = centroids[fish_id] / self.param['image_scale']
                    xpx, ypx, wpx, hpx, _ = (stats[fish_id] / self.param['image_scale']).astype(int)
                    fish_only_image = cv2.subtract(bg_image, frame)[ypx:(ypx+hpx), xpx:(xpx+wpx)]
                    processed_frame[ypx:(ypx+hpx),:][:, xpx:(xpx+wpx)] += 55

                    # mu11 are covariance of (x, y) positive pixel positions and
                    # mu20, mu02 are respectively variances in x, y dimensions
                    # Think of the covariance matrix M = [[mu20, mu11], [mu11, mu02]]
                    # The angle of the first eigen vector of M is going to be the long axis of the object
                    # Let  the eigenvector v = (cos(theta), sin(theta))) and eigenvalues lambda
                    # Now by expanding the character equation Mv=lambda*v, we get
                    # tan(theta) = (lambda-mu20)/mu11 [E1] (note if mu11=0, M is diagonal and theta is 0 or pi/2)
                    # At the same time, we can erase theta dependent terms and solve a quadratic equation
                    # for lambda to get lambda = [(mu20+mu02)+sqrt((mu20-mu02)**2+4*mu11**2)] / 2 [E2]
                    # Now using tan(2*theta) = 2*tan(theta)/(1-tan(theta)**2) and inserting [E1][E2]
                    # We arrive at tan(2*theta) = 2mu11/(mu20-mu02)
                    # Hence the definition of the angle below
                    moments = cv2.moments(cv2.threshold(fish_only_image, self.param['body_threshold'], 255, cv2.THRESH_BINARY)[1])
                    angle = 0.5 * np.arctan2(2 * moments['mu11'], moments['mu20'] - moments['mu02'])

                    # Now I find the position relative to fish only image center 
                    moments = cv2.moments(cv2.threshold(fish_only_image, self.param['head_threshold'], 255, cv2.THRESH_BINARY)[1])
                    if moments['m00'] > 0:
                        x_com = moments['m10'] / moments['m00'] - wpx/2
                        y_com = moments['m01'] / moments['m00'] - hpx/2
                        fish_x += x_com
                        fish_y += y_com
                        if x_com < 0:
                            angle = angle+np.pi
                    else:
                        print('head not found')

                    previous_ii = (self.ii - 1) % self.param['trace_length']
                    this_frame_d_fish = np.sqrt((self.shared_arrays['tracking_history'][0, previous_ii]-fish_x)**2 + 
                                                (self.shared_arrays['tracking_history'][1, previous_ii]-fish_y)**2)
                    bg_update_flag = this_frame_d_fish > 5


                else:
                    fish_x = 0
                    fish_y = 0
                    angle = 0

                

                if bg_update_flag:
                    print('update background', this_frame_d_fish)
                    bg_image = ((bg_image*0.99) + frame*0.01).astype(np.uint8)

                # send tracking results to stimulus program through the named pipe
                self.send_results_through_pipe(timestamp, 0)

                # write results into the shared memory array so the main process can see it
                # note that this function mutate the content of the input array
                encode_frame_to_array(processed_frame, self.shared_arrays['current_processed_frame'])
                self.shared_arrays['tracking_history'][0, self.ii] = fish_x
                self.shared_arrays['tracking_history'][1, self.ii] = fish_y
                self.shared_arrays['tracking_history'][2, self.ii] = (angle + np.pi) % (np.pi * 2.0) - np.pi
                self.shared_arrays['tracking_history'][3, self.ii] = timestamp
                self.ii = (self.ii + 1) % self.param['trace_length']

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
            tracking_memory   = shared_memory.SharedMemory(name='tracking_memory')
        )

        # The sizes of ndarrays are hard-coded without referencing the memory size, because memory size cannot be
        # an arbitrary number and can be different from what we specified in the parent process
        self.shared_arrays = dict(
            current_raw_frame        = np.ndarray((1000000,), dtype=np.uint8, buffer=self.shared_memories['raw_frame_memory'].buf),
            current_processed_frame  = np.ndarray((1000000,), dtype=np.uint8, buffer=self.shared_memories['processed_frame_memory'].buf),
            tracking_history   = np.ndarray((4, self.param['trace_length']), dtype=np.float64, buffer=self.shared_memories['tracking_memory'].buf)
        )

    def send_results_through_pipe(self, timestamp, d_angle):
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


