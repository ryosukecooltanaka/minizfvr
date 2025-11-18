from minizfvr.minizfstim.main import StimulusApp
from minizfvr.minizfstim.stimulus_generator import StimulusGenerator
from minizfvr.minizfstim.scene_engine import SceneEngine
from minizfvr.minizfstim.shaders.shader_utils import get_in_package_shader_path
import numpy as np

class TestGLStim(StimulusGenerator):
    def __init__(self):
        super().__init__()

        # create scene engine
        self.se = SceneEngine()

        # We load shader from files
        self.se.add_shader(get_in_package_shader_path('test_shader'))
        # prepare vertices
        vertex = np.asarray((
            (-0.8, 0.8),
            (0.8, 0.8),
            (0.0, -0.8)
        ))
        self.se.add_object(self.se.shaders[-1], vertex)

    def draw_frame(self, t, paint_area_mm, vigor, bias):
        """
        Receive timestamp, scale info, and closed loop information from the main app
        Return the stimulus frame
        """
        self.se.set_uniform('wriggle', (np.sin(t*8)*0.1, np.cos(t*8)*0.1))
        self.se.set_uniform('t', t)
        frame = self.se.render()

        return [frame]

    def close(self):
        self.se.release()

if __name__ == "__main__":
    stimulus_generator = TestGLStim()
    StimulusApp(stimulus_generator, is_panorama=False)