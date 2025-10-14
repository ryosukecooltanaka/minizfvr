import numpy as np
from main import StimulusApp

class testStimulusGenerator:
    def __init__(self):
        self.xx, self.yy = np.meshgrid(np.linspace(-np.pi, np.pi, 200), np.linspace(-np.pi, np.pi, 200))
        self.rr = np.sqrt(self.xx**2 + self.yy**2)
        self.tt = np.arctan2(self.xx, self.yy)


    def update(self, t):
        frame = (
            np.sin((self.rr + t) * 4),
            np.cos((self.tt - t) * 4),
            np.sin((self.yy + t) * 4)
        )

        return (np.dstack(frame)*127+128).astype(np.uint8)

if __name__ == "__main__":
    stimulus_generator = testStimulusGenerator()
    StimulusApp(stimulus_generator, is_panorama=False)


