import numpy as np
from main import StimulusApp

class testStimulusGenerator:
    def __init__(self):
        self.xx, self.yy = np.meshgrid(np.linspace(0, 1, 100), np.linspace(0, 1, 100))
        self.phase = 0

    def update(self, t, paint_area_mm, vigor, **kwargs):
        """
        Receive timestamp, scale info, and closed loop information from the main app
        Return the stimulus frame
        """
        w_mm, h_mm = paint_area_mm
        wavelength_mm = 20

        spatial_phase = self.yy * w_mm / wavelength_mm * 2.0 * np.pi
        self.phase += vigor * 3
        wave = (np.sin(spatial_phase + self.phase) * 127 + 128).astype(np.uint8)

        return wave

if __name__ == "__main__":
    stimulus_generator = testStimulusGenerator()
    StimulusApp(stimulus_generator, is_panorama=False)


