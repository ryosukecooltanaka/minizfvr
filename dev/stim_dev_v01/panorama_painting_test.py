from main import StimulusApp
import numpy as np
from stimulus_generator import StimulusGenerator

class PanoTest(StimulusGenerator):
    def __init__(self):
        super().__init__()
        self.xx, self.yy = np.meshgrid(np.linspace(0, 255, 100), np.linspace(0, 255, 100))

    def draw_frame(self, t, paint_area_mm, vigor, bias):
        """
        Receive timestamp, scale info, and closed loop information from the main app
        Return the stimulus frame
        """

        nn = self.xx*0

        # for each panel
        # left->right gets redder
        # top->bottom gets bluer

        # left-front-right panels get greener

        frames = [
            np.dstack((self.xx, nn, self.yy)).astype(np.uint8),
            np.dstack((self.xx, nn+100, self.yy)).astype(np.uint8),
            np.dstack((self.xx, nn+200, self.yy)).astype(np.uint8)
        ]

        return frames


if __name__ == "__main__":
    stimulus_generator = PanoTest()
    StimulusApp(stimulus_generator, is_panorama=True)


