import numpy as np
import sys
import multiprocessing as mp
from queue import Empty
import time

from utils import preprocess_image, center_of_mass_based_tracking

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
        self.ii = 0

    def continuously_track_tail(self, frame_queue, param_queue, result_queue):
        """
        Continuously perform tail tracking (run in a child process)
        Read frames and parameters from the queues
        Put the results in the queue
        """
        print('Start tracking process')

        while not self.exit_acquisition_event.is_set():
            # check parameter queue for new parameters -- parameter change happens very infrequently,
            # so I will assume that the param_queue is either empty or has only one entry
            if not param_queue.empty():
                try: # expect to receive parameter as dict
                    print('New parameter received by the child process')
                    self.param = param_queue.get()
                except:
                    print('invalid object was passed to the parameter queue')

            # Process frames in the queue
            while not frame_queue.empty():
                try:
                    frame, timestamp = frame_queue.get(block=False)
                    processed_frame = preprocess_image(frame, **self.param)
                    segments, angles = center_of_mass_based_tracking(processed_frame,
                                                                     (self.param['base_x'], self.param['base_y']),
                                                                     (self.param['tip_x'], self.param['tip_y']),
                                                                      self.param['n_segments'],
                                                                      self.param['search_area'])
                    result_queue.put((frame, processed_frame, timestamp, segments, angles))
                    self.ii += 1
                    if self.ii % 100 == 0:
                        print('processed frame', self.ii)
                except Empty:
                    continue

        print('Exited tracking while loop')
