import numpy as np
from main import StimulusApp
from PyQt5.QtCore import QObject, pyqtSignal

class stimulusGenerator(QObject):
    """
    This is a template for the stimulus generator.
    At the minimum, stimulus generators should have the following attributes
    - stim_state, which is a dictionary of state variables that is updated every frame and logged/saved
    - duration
    - update() method, which returns a stimulus frame to be painted
    """

    durationPassed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.stim_state = dict()
        self.duration = 10

    def update(self, t, *args, **kwargs):
        """
        update() method is called at regular interval by the timer callback of the main app.
        """
        if t > self.duration:
            self.durationPassed.emit()
        frame = self.draw_frame(t, *args, **kwargs)
        return frame

    def draw_frame(self, t, *args, **kwargs):
        pass


class testStimulusGenerator(stimulusGenerator):
    def __init__(self):
        super().__init__()
        self.xx, self.yy = np.meshgrid(np.linspace(-0.5, 0.5, 100), np.linspace(-0.5, 0.5, 100))
        self.phi = np.arctan2(self.yy, self.xx)

        self.stim_dict = dict(
            y_displacement=0.0,
            phi_displacement=0.0
        )

        self.last_t = 0


    def draw_frame(self, t, paint_area_mm, vigor, laterality):
        """
        Receive timestamp, scale info, and closed loop information from the main app
        Return the stimulus frame
        """

        dt = t - self.last_t
        self.last_t = t

        w_mm, h_mm = paint_area_mm
        wavelength_mm = 10

        # threshold to prevent continuous drifting & "baseline gain" to convert rad to mm/s
        self.stim_dict['y_displacement'] -= (vigor * 30 * (vigor>0.1) - 5) * dt
        self.stim_dict['phi_displacement'] -= laterality * 3

        linear_wave = np.cos((self.yy * h_mm + self.stim_dict['y_displacement']) / wavelength_mm * 2.0 * np.pi)
        axial_wave = np.cos((self.phi + self.stim_dict['phi_displacement']) * 16)

        wave = (128 + 127 * np.dstack((linear_wave, axial_wave, axial_wave))).astype(np.uint8)

        return wave

if __name__ == "__main__":
    stimulus_generator = testStimulusGenerator()
    StimulusApp(stimulus_generator, is_panorama=False)


