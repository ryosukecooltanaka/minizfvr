from minizfvr.minizfstim.main import StimulusApp
from minizfvr.minizfstim.stimulus_generator import StimulusGenerator
import numpy as np

"""
This script is intended to show how to structure your stimulus script.
At the very minimum, a script needs to create its own StimulusGenerator object,
and run the StimulusApp, while passing the StimulusGenerator.

"""

class TestStim(StimulusGenerator):
    """
    This object stores all the necessary information to draw stimuli.
    """


    def __init__(self):
        super().__init__()
        self.xx, self.yy = np.meshgrid(np.linspace(-0.5, 0.5, 100), np.linspace(-0.5, 0.5, 100))
        self.phi = np.arctan2(self.yy, self.xx)

        # it is important to initialize these in the correct types, as saving routine check the type of initial
        # values and prepare save files accordingly
        self.y_displacement = 0.0
        self.phi_displacement = 0.0
        self.vigor = 0.0
        self.bias = 0.0

        self.variables_to_save.extend(
            [
                'y_displacement',
                'phi_displacement',
                'vigor',
                'bias'
            ]
        )
        self.last_t = 0

    def draw_frame(self, t, paint_area_mm, vigor, bias):
        """
        draw_frame method will be called regularly, and is expected to return frames as a list of ndarrays
        Receive timestamp, scale info, and closed loop information from the main app
        Return the stimulus frame
        """

        dt = t - self.last_t
        self.last_t = t

        self.vigor = vigor
        self.bias = bias

        w_mm, h_mm = paint_area_mm
        wavelength_mm = 10

        # threshold to prevent continuous drifting & "baseline gain" to convert rad to mm/s
        self.y_displacement -= (vigor * 30 * (vigor>0.1) - 5) * dt
        self.phi_displacement -= bias * 3

        linear_wave = np.cos((self.yy * h_mm + self.y_displacement) / wavelength_mm * 2.0 * np.pi)
        axial_wave = np.cos((self.phi + self.phi_displacement) * 16)

        wave = (128 + 127 * np.dstack((linear_wave, axial_wave, axial_wave))).astype(np.uint8)

        return [wave]


"""
This is the part that will be executed as you call this file as a script.
"""
if __name__ == "__main__":
    # Instantiate custom stim generator
    stimulus_generator = TestStim()
    # Instantiate the StimulusApp, passing the stim generator
    StimulusApp(stimulus_generator, is_panorama=False)