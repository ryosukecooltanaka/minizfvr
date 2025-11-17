import numpy as np

# todo: This could be separated into a template class and a child class implementing a specific bout calculation algo
class Estimator:
    """
    The job of an estimator is to log the tail angle and timestamp information and calculate fictive swim properties
    (i.e., swim speed and turn angles)
    """

    def __init__(self,
                 buffer_size=300,
                 vigor_window=0.05,
                 bias_window=0.07,
                 bias_baseline_window=0.05,
                 vigor_threshold=0.05):

        ## Parameters
        self.vigor_window = vigor_window
        self.bias_window = bias_window
        self.bias_baseline_window = bias_baseline_window
        self.vigor_threshold = vigor_threshold

        ## Prepare buffers
        self.timestamp_buffer = np.zeros(buffer_size, dtype=float)
        self.angle_buffer = np.zeros(buffer_size, dtype=float)

        ## index for the buffer
        self.buffer_index = -1

        ## store the latest estimated swim properties
        self.vigor = 0
        self.bias = 0

        ## flags for bias calculation
        self.in_bout = False
        self.bout_onset_t = 0
        self.bias_calc_pending = 0

    def register_new_data(self, timestamp, angle):
        """
        Increment the buffer index by one tick, and write the new data into the buffer.
        The buffer index is always pointing to the latest data point this way
        """
        self.buffer_index = (self.buffer_index + 1) % self.timestamp_buffer.size
        self.timestamp_buffer[self.buffer_index] = timestamp
        self.angle_buffer[self.buffer_index] = angle

    def update_swim_estimate(self):
        """
        Update swim vigor and bias estimate.
        Called every time new data is added.
        """
        # This is the current time stamp (or so we assume)
        last_t = self.timestamp_buffer[self.buffer_index]

        # Vigor is just the standard deviation of tail angle within a short window, typically 50 ms
        # this can be thresholded?
        self.vigor = np.nanstd(self.angle_buffer[self.timestamp_buffer > (last_t - self.vigor_window)])

        # A swim bout is defined as a continuous period of time during which swim vigor is above a certain threshold
        # (typically 0.1 rad). Each swim bout is assigned a bout bias, which is a (baseline-subtracted) mean
        # tail angle during the initial segment of the bout (typically 70 ms).
        if not self.in_bout and (self.vigor > self.vigor_threshold):
            self.in_bout = True
            self.bias_calc_pending = True
            self.bout_onset_t = last_t

        if self.vigor < self.vigor_threshold:
            self.in_bout = False

        # Check if a set amount of time has passed after the bout onset. If so, we calculate the bias, and
        # clear the flag
        if self.bias_calc_pending:
            if last_t > (self.bout_onset_t + self.bias_window):
                self.bias_calc_pending = False
                in_baseline_window = (self.timestamp_buffer > (last_t - self.bias_window - self.bias_baseline_window)) *\
                                     (self.timestamp_buffer < (last_t - self.bias_window))
                in_bias_window = self.timestamp_buffer > (last_t - self.bias_window)
                self.bias = np.nanmean(self.angle_buffer[in_bias_window]) - np.nanmean(self.angle_buffer[in_baseline_window])
                print('Bout (bias = {:0.2f} deg)'.format(self.bias/np.pi*180))
        else:
            self.bias = 0.0 # important that this is float because Saver typecheck on these things!





