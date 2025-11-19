import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
import json
from pathlib import Path

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

        # return should be a list of frame even if there is only one frame,
        # so we can handle single panel vs. panorama outputs in a consistent fashion
        return frame

    def draw_frame(self, t, *args, **kwargs):
        """
        Child classes should reimplement this method
        """
        return [np.random.rand(100)]

    def close(self):
        """
        In case you need to close handles for some externals, do it so here
        """
        pass

    def reset(self):
        """
        This will be called at start/stop of the stimulus
        If your stimulus depends on history of timestamps, you probably want to clear them when you start/stop them,
        which you can implement here
        """
        pass

    def save_metadata(self, save_file_path):
        """
        dump all attributes as a json
        """
        print('saving metadata')
        with open(save_file_path, 'w', encoding='utf-8') as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=2, default=lambda o: '<not serializable>')
