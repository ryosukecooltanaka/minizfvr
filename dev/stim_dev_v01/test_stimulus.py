from main import StimulusApp
import numpy as np
from stimulus_generator import stimulusGenerator

class testStimulusGenerator(stimulusGenerator):
    def __init__(self):
        super().__init__()
        self.xx, self.yy = np.meshgrid(np.linspace(-0.5, 0.5, 100), np.linspace(-0.5, 0.5, 100))
        self.phi = np.arctan2(self.yy, self.xx)

        # it is important to initialize these in the correct types, as saving routine check the type of initial
        # values and prepare save files accordingly
        self.y_displacement = 0.0
        self.phi_displacement = 0.0
        self.vigor = 0.0
        self.laterality = 0.0

        self.variables_to_save.extend(
            [
                'y_displacement',
                'phi_displacement',
                'vigor',
                'laterality'
            ]
        )
        self.last_t = 0

    def draw_frame(self, t, paint_area_mm, vigor, laterality):
        """
        Receive timestamp, scale info, and closed loop information from the main app
        Return the stimulus frame
        """

        dt = t - self.last_t
        self.last_t = t

        self.vigor = vigor
        self.laterality = laterality

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


