import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

class StimulusGenerator(QObject):
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
        self.variables_to_save = []
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
        """
        Child classes should reimplement this method
        """
        pass

    def close(self):
        """
        In case you need to close handles for some externals, do it so here
        """
        pass
