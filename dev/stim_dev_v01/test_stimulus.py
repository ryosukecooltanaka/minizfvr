import numpy as np
from main import StimulusApp

class testStimulusGenerator:
    def __init__(self):
        self.xx, self.yy = np.meshgrid(np.linspace(-0.5, 0.5, 100), np.linspace(-0.5, 0.5, 100))
        self.phi = np.arctan2(self.yy, self.xx)
        self.y_displacement = 0
        self.phi_displacement = 0

    def update(self, dt, paint_area_mm, vigor, laterality, **kwargs):
        """
        Receive timestamp, scale info, and closed loop information from the main app
        Return the stimulus frame
        """
        w_mm, h_mm = paint_area_mm
        wavelength_mm = 10

        # threshold to prevent continuous drifting & "baseline gain" to convert rad to mm/s
        self.y_displacement -= vigor * 30 * (vigor>0.1) * dt
        self.phi_displacement -= laterality * 3

        linear_wave = np.cos((self.yy * h_mm + self.y_displacement) / wavelength_mm * 2.0 * np.pi)
        axial_wave = np.cos((self.phi + self.phi_displacement) * 16)

        wave = (128 + 127 * np.dstack((linear_wave, axial_wave, axial_wave))).astype(np.uint8)

        return wave

if __name__ == "__main__":
    stimulus_generator = testStimulusGenerator()
    StimulusApp(stimulus_generator, is_panorama=False)


