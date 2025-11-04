from main import StimulusApp
import numpy as np
from stimulus_generator import StimulusGenerator
from scene_engine import SceneEngine

# Utility for vertex generation

def create_cylinder(scale=1.0, n_face = 32):
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
        bottom_right = (scale*np.sin(t0), 0, scale*np.cos(t0), i/n_face, 0) # u is t0/2pi (range 0-1)
        top_right =    (scale*np.sin(t0), scale, scale*np.cos(t0), i/n_face, 1)
        bottom_left =  (scale*np.sin(t1), 0, scale*np.cos(t1), (i+1)/n_face, 0)
        top_left     = (scale*np.sin(t1), scale, scale*np.cos(t1), (i+1)/n_face, 1)

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



class TestPRStim(StimulusGenerator):
    def __init__(self):
        super().__init__()

        # create scene engine
        self.se = SceneEngine()


        # We load shader from files
        self.se.add_shader('./shaders/perspective_shader')

        # prepare texture
        uu, vv = np.meshgrid(np.linspace(0,1,32), np.linspace(0,1,32))
        tex = np.stack((uu, 1.0-uu, vv), axis=-1)
        tex = (tex * 255).astype(np.uint8)
        self.se.add_texture(tex)

        # create object by combining (cylinder with radius and height 10
        verts = create_cylinder(scale=10)
        print(verts.shape)
        self.se.add_object(self.se.shaders[-1], verts, self.se.textures[-1])

        ## pass initial parameters for the shader
        # model (rotation will be set frame by frame)
        self.se.set_uniform('tr', (0, 0, 30))

        # view (gaze will be set per screen)
        self.se.set_uniform('camera', (0,0,0))
        self.se.set_uniform('up', (0,1,0))

        # perspective (90 deg gaze for both sides)
        self.se.set_uniform('fov_x', (-np.pi/4.0, np.pi/4.0))
        self.se.set_uniform('fov_y', (-np.pi/4.0, np.pi/4.0))
        self.se.set_uniform('clip_z', (10.0, 100.0))

        self.se.background = (0.1, 0.1, 0.1, 1.0)



    def draw_frame(self, t, paint_area_mm, vigor, bias):
        """
        Receive timestamp, scale info, and closed loop information from the main app
        Return the stimulus frame
        """
        # move the thing
        #self.se.set_uniform('rot', (t, 0, 0))
        self.se.set_uniform('tr', (40*np.cos(t), 0, 30*np.sin(t)))

        # render 3 frames for each screen
        frame = []

        gazes = ((1, 0, 0), # left: positive X
                 (0, 0, 1), # front: positive Z
                 (-1, 0, 0)) # right: negative X
        for this_gaze in gazes:
            self.se.set_uniform('gaze', this_gaze)
            frame.append(self.se.render())

        return frame

    def close(self):
        self.se.release()

if __name__ == "__main__":
    stimulus_generator = TestPRStim()
    StimulusApp(stimulus_generator, is_panorama=True)


