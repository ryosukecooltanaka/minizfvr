import numpy as np
from main import StimulusApp

class stimulusGenerator:
    """
    This is a template for the stimulus generator.
    At the minimum, stimulus generators should have the following attributes
    - stim_state, which is a dictionary of state variables that is updated every frame and logged/saved
    - duration
    - update() method, which returns a stimulus frame to be painted
    """


    def __init__(self):
        self.stim_state = dict()
        self.duration = np.inf

    def get_state_names(self):
        return self.stim_state.keys()

    def update(self, t: float, paint_area_mm: tuple, vigor: float, laterality: float):
        """
        update() method is called at regular interval by the timer callback of the main app.
        It always receives the following four arguments:
        - t (time from stimulus start)
        - paint_area_mm (2-tuple for the paint area)
        - vigor
        - laterality
        """
        pass


class testStimulusGenerator(stimulusGenerator):
    def __init__(self):
        super().__init__()
        self.xx, self.yy = np.meshgrid(np.linspace(-0.5, 0.5, 100), np.linspace(-0.5, 0.5, 100))
        self.phi = np.arctan2(self.yy, self.xx)
        self.y_displacement = 0
        self.phi_displacement = 0
        self.last_t = 0


    def update(self, t: float, paint_area_mm: tuple, vigor: float, laterality: float):
        """
        Receive timestamp, scale info, and closed loop information from the main app
        Return the stimulus frame
        """
        dt = t - self.last_t
        self.last_t = t
        w_mm, h_mm = paint_area_mm
        wavelength_mm = 10

        # threshold to prevent continuous drifting & "baseline gain" to convert rad to mm/s
        self.y_displacement -= (vigor * 30 * (vigor>0.1) - 5) * dt
        self.phi_displacement -= laterality * 3

        linear_wave = np.cos((self.yy * h_mm + self.y_displacement) / wavelength_mm * 2.0 * np.pi)
        axial_wave = np.cos((self.phi + self.phi_displacement) * 16)

        wave = (128 + 127 * np.dstack((linear_wave, axial_wave, axial_wave))).astype(np.uint8)

        return wave

if __name__ == "__main__":
    stimulus_generator = testStimulusGenerator()
    StimulusApp(stimulus_generator, is_panorama=False)


