from minizfvr.minizfstim.main import StimulusApp
from minizfvr.minizfstim.stimulus_generator import StimulusGenerator
from minizfvr.minizfstim.scene_engine import SceneEngine
from minizfvr.minizfstim.shaders.shader_utils import get_in_package_shader_path
import numpy as np

# Utility for vertex generation

def create_centered_cylinder(r=1.0, h=1.0, n_face = 32):
    '''
    Create cylinder with a sensible UV map
    Here we do this s.t. each vertex is clockwise viewed from outside
    (this doesn't matter unless you do back-face culling)
    Each side requires 2 triangles = 6 vertices
    Just do this with unit radius and height 1
    Do scaling later
    '''

    verts = []

    for i in range(n_face):
        t0 = np.pi * 2.0 / n_face * i
        t1 = np.pi * 2.0 / n_face * (i+1)

        # define points
        bottom_right = (r*np.sin(t0), -h/2, r*np.cos(t0), i/n_face, 0) # u is t0/2pi (range 0-1)
        top_right =    (r*np.sin(t0),  h/2, r*np.cos(t0), i/n_face, 1)
        bottom_left =  (r*np.sin(t1), -h/2, r*np.cos(t1), (i+1)/n_face, 0)
        top_left     = (r*np.sin(t1),  h/2, r*np.cos(t1), (i+1)/n_face, 1)

        # arrange
        verts.extend(
            [
                bottom_right, # vertex 1
                bottom_left,
                top_right,
                bottom_left, # vertex 2
                top_left,
                top_right
            ]
        )
    return np.asarray(verts)

class CylinderExperiment(StimulusGenerator):
    def __init__(self):
        super().__init__()

        # create scene engine
        self.se = SceneEngine()
        self.initialize_scene_engine()

        # experiment parameters
        self.duration = 600
        self.omega = 18.0 # exafferent angular velocity (deg/s)
        self.tau_theta = 0.1

        self.last_switch_t = 0.0
        self.this_epoch_duration = 0.0


        # it is important to initialize these in the correct types, as saving routine check the type of initial
        # values and prepare save files accordingly
        self.vigor = 0.0
        self.bias = 0.0
        self.theta = 0.0
        self.reafference = 0.0
        self.exafference = 0.0

        self.variables_to_save.extend(['vigor', 'bias', 'theta', 'reafference', 'exafference'])
        self.last_t = 0.0
        self.t_last_bout = 0.0
        self.last_bias = 0.0

    def reset(self):
        self.last_t = 0.0
        self.t_last_bout = 0.0
        self.last_bias = 0.0

    def initialize_scene_engine(self):
        """
        Separating out this here for the sake of readability
        called once from the constructor
        """
        # We load shader from files
        self.se.add_shader(get_in_package_shader_path('perspective_shader'))

        # prepare texture
        uu, _ = np.meshgrid(np.linspace(0, 1, 256), np.linspace(0, 1, 32))
        wave = np.cos(2.0*np.pi*uu)+1.0
        # add bars
        wave *= (uu%0.2) > 0.03

        tex = np.stack((wave, 0*uu, 0*uu), axis=-1)
        tex = (tex * 127).astype(np.uint8)
        self.se.add_texture(tex)

        # create object by combining (cylinder with radius and height 10
        verts = create_centered_cylinder(r=25, h=50)
        self.se.add_object(self.se.shaders[-1], verts, self.se.textures[-1])

        ## pass initial parameters for the shader
        # model (rotation will be set frame by frame)
        self.se.set_uniform('tr', (0, 0, 0))

        # view (gaze will be set per screen)
        self.se.set_uniform('camera', (0, 0, 0))
        self.se.set_uniform('up', (0, 1, 0))

        # perspective (90 deg gaze for both sides)
        self.se.set_uniform('fov_x', (-np.pi / 4.0, np.pi / 4.0))
        self.se.set_uniform('fov_y', (-np.pi / 4.0, np.pi / 4.0))
        self.se.set_uniform('clip_z', (10.0, 100.0))
        self.se.background = (0.0, 0.0, 0.0, 1.0) # black

    def draw_frame(self, t, paint_area_mm, vigor, bias):
        """
        Receive timestamp, scale info, and closed loop information from the main app
        Return the stimulus frame
        """
        ## register inputs / timestamp management
        self.vigor = vigor
        self.bias = bias
        dt = t - self.last_t
        self.last_t = t

        ## state management
        # turn on/off exafference for random durations
        if self.last_switch_t + self.this_epoch_duration < t:
            self.last_switch_t = t
            self.this_epoch_duration = np.random.randint(1,9)
            if self.exafference == 0:
                sign = np.random.randint(2) - 1
                self.exafference = sign * self.omega / 180 * np.pi
            else:
                self.exafference = 0

        ## reafference calculation
        # do the exponential decay thing
        if bias != 0:
            self.t_last_bout = t
            self.last_bias = bias
        # divide by theta, so it will integrate to 1
        self.reafference = self.last_bias * np.exp(-(t-self.t_last_bout)/self.tau_theta) / self.tau_theta

        dtheta = (self.exafference - self.reafference) * dt
        self.theta += dtheta


        # move the thing
        self.se.set_uniform('rot', (0, -self.theta, 0))

        # render 3 frames for each screen
        frame = []

        # gaze direction in world coordinate
        # not to be confused with the one in viewing coordinate (where camera points negative z)
        # as long as it is a consistent right-handed coordinate, it does not matter
        gazes = ((1, 0, 0), # left: positive X
                 (0, 0, 1), # front: positive Z
                 (-1, 0, 0)) # right: negative X
        for this_gaze in gazes:
            self.se.set_uniform('gaze', this_gaze)
            frame.append(self.se.render())

        return frame

    def close(self):
        print('stim generator close event called')
        self.se.release()

if __name__ == "__main__":
    stimulus_generator = CylinderExperiment()
    StimulusApp(stimulus_generator, is_panorama=True)