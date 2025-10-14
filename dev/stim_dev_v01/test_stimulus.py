import numpy as np
from main import StimulusApp

class testStimulusGenerator:
    def __init__(self):
        self.xx, self.yy = np.meshgrid(np.linspace(0, np.pi*2, 200), np.linspace(0, np.pi*2, 200))


    def update(self, t):
        return (127.5*(1+np.sin(self.xx*4.0 - np.sin(self.yy)*4.0 +t*np.pi*2.0))).astype(np.uint8)

if __name__ == "__main__":
    stimulus_generator = testStimulusGenerator()
    StimulusApp(stimulus_generator, is_panorama=False)


