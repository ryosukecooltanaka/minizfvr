import numpy as np


class Estimator:
    """
    The job of an estimator is to log the tail angle and timestamp information and calculate fictive swim properties
    (i.e., swim speed and turn angles)
    """

    def __init__(self, buffer_size=300):

        ## Prepare buffers
        self.timestamp_buffer = np.zeros(buffer_size, dtype=float)
        self.angle_buffer = np.zeros(buffer_size, dtype=float)

        ## index for the buffer
        self.buffer_index = -1

        ## store the latest estimated swim properties
        self.vigor = 0
        self.laterality = 0

        ## flags for laterality calculation
        self.in_bout = False
        self.bout_onset_t = 0
        self.laterality_calc_pending = 0

    def register_new_data(self, timestamp, angle):
        """
        Increment the buffer index by one tick, and write the new data into the buffer.
        The buffer index is always pointing to the latest data point this way
        """
        self.buffer_index = (self.buffer_index + 1) % self.timestamp_buffer.size
        self.timestamp_buffer[self.buffer_index] = timestamp
        self.angle_buffer[self.buffer_index] = angle
        self.update_swim_estimate()

    def update_swim_estimate(self,
                             vigor_window=0.05,
                             laterality_window=0.07,
                             laterality_baseline_window=0.05,
                             vigor_threshold=0.1):
        """
        Update swim vigor and laterality estimate.
        Called every time new data is added.
        """
        # This is the current time stamp (or so we assume)
        last_t = self.timestamp_buffer[self.buffer_index]

        # Vigor is just the standard deviation of tail angle within a short window, typically 50 ms
        # this can be thresholded?
        self.vigor = np.nanstd(self.angle_buffer[self.timestamp_buffer > (last_t - vigor_window)])

        # A swim bout is defined as a continuous period of time during which swim vigor is above a certain threshold
        # (typically 0.1 rad). Each swim bout is assigned a bout laterality, which is a (baseline-subtracted) mean
        # tail angle during the initial segment of the bout (typically 70 ms).
        if not self.in_bout and (self.vigor > vigor_threshold):
            print('bout start')
            self.in_bout = True
            self.laterality_calc_pending = True
            self.bout_onset_t = last_t

        if self.vigor < vigor_threshold:
            self.in_bout = False

        # Check if a set amount of time has passed after the bout onset. If so, we calculate the laterality, and
        # clear the flag
        if self.laterality_calc_pending:
            if last_t > (self.bout_onset_t + laterality_window):
                self.laterality_calc_pending = False
                in_baseline_window = (self.timestamp_buffer > (last_t - laterality_window - laterality_baseline_window)) *\
                                     (self.timestamp_buffer < (last_t - laterality_window))
                in_laterality_window = self.timestamp_buffer > (last_t - laterality_window)
                self.laterality = np.nanmean(self.angle_buffer[in_laterality_window]) - np.nanmean(self.angle_buffer[in_baseline_window])
                print('laterality of this bout is ',self.laterality)
        else:
            self.laterality = 0





