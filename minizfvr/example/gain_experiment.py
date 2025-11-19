from minizfvr.minizfstim.main import StimulusApp
from minizfvr.minizfstim.stimulus_generator import StimulusGenerator
import numpy as np
from random import shuffle

"""
This script is intended to show how you can program an actual bottom-projection
closed loop experiment in this framework.
"""

class GainExperiment(StimulusGenerator):
    """
    This object stores all the necessary information to draw stimuli.
    """


    def __init__(self):
        super().__init__()

        # phase map for frame generation
        _, yy = np.meshgrid(np.linspace(0.0, 1.0, 100), np.linspace(0.0, 1.0, 100))
        self.yy = np.dstack((yy, yy, yy)) # save y phase as 3d stack

        # experiment structure
        self.flow_off_duration = 10
        self.flow_on_duration = 10
        self.gains = (0.0, 0.5, 1.0, 2.0)
        self.n_repeat_per_condition = 10
        self.duration = self.n_repeat_per_condition * (self.flow_off_duration + self.flow_on_duration) * len(self.gains)

        self.gain_sequence = []
        for i in range(self.n_repeat_per_condition):
            temp = list(self.gains)
            shuffle(temp)
            self.gain_sequence.extend(temp)

        self.wave_length = 10.0 # mm
        self.flow_velocity = 10.0 # mm/s

        # it is important to initialize these in the correct types, as saving routine check the type of initial
        # values and prepare save files accordingly
        self.y_displacement = 0.0
        self.vigor = 0.0
        self.bias = 0.0
        self.gain = 1.0
        self.reafference_speed = 0.0
        self.exafference_speed = 0.0
        self.epoch = 0

        self.variables_to_save.extend(
            [
                'y_displacement',
                'vigor',
                'bias',
                'gain',
                'reafference_speed',
                'exafference_speed',
                'epoch'
            ]
        )
        self.last_t = 0

    def draw_frame(self, t, paint_area_mm, vigor, bias):
        """
        draw_frame method will be called regularly, and is expected to return frames as a list of ndarrays
        Receive timestamp, scale info, and closed loop information from the main app
        Return the stimulus frame
        """
        # Register inputs and manage timestamp
        dt = t - self.last_t
        self.last_t = t
        self.vigor = vigor
        self.bias = bias
        w_mm, h_mm = paint_area_mm

        ## epoch state control
        # Epoch number calculation
        self.epoch = int(t // (self.flow_off_duration + self.flow_on_duration)) # which epoch are we in?
        # Check if we are in exafference on or off state
        is_moving = (t % (self.flow_off_duration + self.flow_on_duration)) > self.flow_off_duration
        # If it is moving, use the pre-designated gain, otherwise just 1.0
        if is_moving:
            self.gain = self.gain_sequence[self.epoch]
        else:
            self.gain = 1.0

        # TODO: Maybe this should be somehow referenced from the estimator?
        # 30 is a hard-coded baseline gain to convert tail angle std to mm/s
        is_in_bout = vigor > 0.05
        self.reafference_speed = is_in_bout * self.gain * self.vigor * 30.0
        self.exafference_speed = is_moving * self.flow_velocity

        # y movement in this frame (in mm)
        dy = (self.exafference_speed - self.reafference_speed) * dt
        if not np.isnan(dy):
            self.y_displacement += dy

        # the "phase map" ranges from 0 to 1, so you can just multiply it
        # paint area (in mm) to get correct mm readout
        out = (127.5 * (np.cos((self.yy * h_mm + self.y_displacement) / self.wave_length * 2.0 * np.pi) + 1.0)).astype(np.uint8)

        return [out]


"""
This is the part that will be executed as you call this file as a script.
"""
if __name__ == "__main__":
    # Instantiate custom stim generator
    stimulus_generator = GainExperiment()
    # Instantiate the StimulusApp, passing the stim generator
    StimulusApp(stimulus_generator, is_panorama=False)