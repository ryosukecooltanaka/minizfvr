"""
To create visual stimuli using 3DCG, we use moderngl, which is a python API for modern versions of OpenGL with
"programmable pipelines" (>v3.3). The SceneEngine() object wraps around the moderngl pipeline, such that
StimulusGenerator() can instantiate a SceneEngine(), and just pass models / textures etc. and get rendered frames
without worrying much about shaders etc.

To understand how opengl/moderngl work, one should refer to:
- https://learnopengl.com/
- https://moderngl.readthedocs.io/

### Overview of moderngl pipeline ###

## Context

First, one needs to create a Context() object, under which everything happens. Context() is a bit like a handle to
the graphics card (I think), and as such you can't open multiple Context() at a time (on the whole system).
Every other relevant objects (like buffer(), program(), vertex_array(), texture()) can only be created from the
Context() object methods.

## Shaders

Once you have a Context() open, you create 'shader programs' (program() object) by passing shader source codes
written in GLSL (opengl shader language) as string. Each shader program should at least contain a 'vertex shader'
and 'fragment shader', and an optional 'geometry shader' in between.

In a typical case, the vertex shader is called once for each vertex in the mesh you are rendering, and project its 3D
coordinates into the 2D screen space, while passing through other vertex attributes (e.g., surface normals, UV
coordinates for texture mapping). Note that the depth information post-projection is retained such that the fragment
shader can only draw what is supposed to be in front for each pixel.

A geometry shader, if specified, will receive a set of transformed vertices that form a 'primitive' which is typically
a triangle but can be a line or a point etc., and perform additional processing (e.g., reject far-away vertices).

OpenGL then performs rasterization and interpolation over the outputs of the vertex shader, such that each 'pixel' or
'fragment' within the primitive have appropriate attributes (e.g., normals, UV). The interpolation is done in a view
corrected fashion, rather than simply in the 2D space (which would result in weird distortions).

Finally, for each fragment resulted from this interpolation process will be fed into the fragment shader, and the color
of the corresponding fragment (i.e., pixel) will be determined by looking up the texture or doing the lighting
calculation.

## Rendering and buffers

Buffers are memory on the graphics card, where we store inputs (vertices, textures etc.) and outputs (rendered frames)
of the shaders. In moderngl, we first create vertices as a numpy array, and pass it to a buffer (after casting as byte
arrays), which would create vertex buffer object (VBO). We then pair each VBO with shader programs, forming a vertex
array object (VAO). Next, we prepare a buffer to store rendered frames (frame buffer object, FBO). Finally, we call
render() method on the VAO, whose result will go into the specified FBO.

Also note that underlying buffer objects are not cleared until you manually do so, unlike python objects that are
automatically garbage-collected.

"""

import moderngl
from pathlib import Path
import re
import numpy as np
from utils import parse_glsl
from PIL import Image

class SceneEngine:
    """
    How to use SceneEngine():
    - First, instantiate a SceneEngine object
    - Next, load shader from a path by add_share() method
    - If necessary, create a texture buffer by add_texture() method
    - Create objects to be rendered by running add_object() method, passing reference to existing shader and texture
    - At each refresh, update render parameters by calling set_global_uniform() of the SceneEngine or set() of each
      VirtualObject, so you can move around the camera or the object. Also, update texture buffers with write() method.
    - Call render() to get bitmap output.
    """

    def __init__(self, render_size=(300,300), background=(0.0, 0.0, 0.0, 1.0)):
        # Create the context
        self.ctx = moderngl.create_standalone_context()
        # Enable depth testing & point-with-size drawing
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)

        """
        So, we have to store and manage
        - Shader programs
            We could use multiple shaders for a single scene (e.g., triangles + points)
            Also, each shader program can take different argument from CPU ('Uniform' variables etc) which can
            be a bit opaque from the python side.
        - Vertices
            Typically this would be N x 5 array (x, y, z, u, v), but the shape is dependent upon the shader
        - Vertex buffer object (VBO)
            This is a memory handle for the vertices in the Graphics memory.
        - Vertex array object (VAO)
            This is a pair of VBO and a shader program
        - Frame buffer object (FBO)
            There should be only one of this
        - Texture buffer
            
        Considering that there will be only a handful shader programs per experiment tops and Vertices/VBO/VAO should
        be almost always one-to-one corresponding, I decided to create wrapper classes for shader (WrappedShader) and 
        Vertices/VBO/VAO triplets (VirtualObject). SceneEngine class will hold a list of WrappedShader and a list of 
        VirtualObject.
        """

        # first prepare frame buffer
        self.render_size = render_size
        self.frame_buffer = self.ctx.simple_framebuffer(render_size)
        self.frame_buffer.use()
        self.background = background

        # attributes (lists) to store shaders, objects, and textures
        self.shaders = []
        self.textures = []
        self.objects = [] # object is dependent on shader and texture, so make this last

    def add_shader(self, path, primitive_type=moderngl.TRIANGLES):
        self.shaders.append(WrappedShader(self.ctx, path, primitive_type))

    def add_texture(self, bitmap):
        """
        Here, we reserve the space for texture based on a bitmap (i.e. buffer)
        To change the content of the buffer, use write() method of the texture buffer object
        """
        texture_buffer = self.ctx.texture(bitmap.shape[:2], 3, data=bitmap)
        texture_buffer.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.textures.append(texture_buffer)

    def add_object(self, shader, vertices, texture_buffer=None):
        self.objects.append(VirtualObject(shader, vertices, texture_buffer))

    def set_global_uniform(self, key, val):
        """
        Enforce a globally shared value for a certain uniform variable
        Use this for camera parameters etc. that should be consistent across shaders/objects
        """
        for obj in self.objects:
            obj.set(key, val)

    def render(self):
        self.frame_buffer.clear(*self.background)
        for obj in self.objects:
            obj.render()
        img = np.asarray(Image.frombytes('RGB', self.render_size, self.frame_buffer.read()))
        return img

    def release(self):
        print('Release all OpenGL objects')
        [obj.release() for obj in self.objects]
        [tex.release() for tex in self.textures]
        [shader.release() for shader in self.shaders]
        self.frame_buffer.release()
        self.ctx.release()

class WrappedShader:
    """
    Given the moderngl context and paths to shader programs, create Program() objects.
    Also parse the shader program and get the names and shapes of input vertices & parameters (i.e. Uniform keyword
    variables)
    """
    def __init__(self, ctx, shader_path, primitive_type):
        self.ctx = ctx
        # We use this flag for rendering a VAO
        self.primitive_type = primitive_type

        # load glsl source code from files, and create a program
        vsh, gsh, fsh = self.load_shader_from_path(shader_path)
        self.prog = self.ctx.program(vertex_shader=vsh, geometry_shader=gsh, fragment_shader=fsh) # this is the Program() object!

        # Parse glsl source code and log expected input name and size
        # The list of names are useful, because we need that to create VAO from VBO+shader
        self.input_keys = [x[0] for x in parse_glsl(vsh, 'in')] # list of (string, int) tuples
        self.input_total_width = np.sum([x[1] for x in self.input_keys]) # this is the number of dimensions each vertex is supposed to have

        # Also get the list of Uniform (which is like the shader parameters) by parsing GLSL
        # Uniforms are variables that can be set from CPU and the same value are shared across all GPU processors
        # for each render call. This is used to for example set the camera directions and model translation.
        uniforms = []
        for sh in (vsh, gsh, fsh):
            uniforms.extend(parse_glsl(sh, 'uniform'))
        self.uniforms = uniforms

    def load_shader_from_path(self, path):
        """
        Given a path to a shader program folder, return shader as text
        We assume a folder to contain one each of text files named as 'vertex_shader.glsl', 'fragment_shader.glsl',
        as well as an optional 'geometry_shader.glsl'
        """

        with open(Path(path) / 'vertex_shader.glsl', 'r') as f:
            vertex_shader = f.read()

        with open(Path(path) / 'fragment_shader.glsl', 'r') as f:
            fragment_shader = f.read()

        if (Path(path) / 'geometry_shader.glsl').exists():
            with open(Path(path) / 'geometry_shader.glsl', 'r') as f:
                geometry_shader = f.read()
        else:
            geometry_shader = None # if we pass None, geometry shader is ignored

        return vertex_shader, geometry_shader, fragment_shader

    def release(self):
        self.prog.release()

class VirtualObject:
    """
    A thin wrapper that combines a WrappedShader, ndarray representing vertices (with a dimension specified by the
    WrappedShader), VBO made for these vertices, VAO combining the shaders and VBO, and texture buffer.
    """
    def __init__(self, shader:WrappedShader, vertices, texture_buffer):
        ctx = shader.prog.ctx # Shader Program() has reference to the parent context, so we don't need to explicitly pass this here
        self.shader = shader

        if vertices.shape[1] != shader.input_total_width:
            raise ValueError("The dimension of provided vertices {} "
                             "did not match the requirement of "
                             "the vertex shader {}".format(vertices.shape[1], shader.input_total_width))

        # Register vertices to the buffer (Graphics memory)
        self.vertex_buffer = ctx.buffer(vertices.astype('f4').tobytes())
        # Pair the vertices in the buffer with the shader
        self.vertex_array = ctx.simple_vertex_array(shader.prog, self.vertex_buffer, *self.shader.input_keys)

        # Because Uniform variables in the shader program are used to control object specific setting such as the
        # model translation and rotation, it makes sense for VirtualObject to keep these values as its own attributes
        # and enforce these values onto the shader program before each render call (although Uniform is also used
        # for global purposes such as camera directions etc.). To render dynamic scenes, one should update the values
        # in this uniform_dict under the each VirtualObject within a SceneEngine.
        self.uniform_dict = {}
        for key_len_pair in self.shader.uniforms:
            # we are being loose about the actual value type here because as long as you feed ndarray it is nicely
            # implicitly cast (which is not the case if you give them length 1 list or tuple)
            self.uniform_dict[key_len_pair[0]] = np.zeros(key_len_pair[1])

        # Prepare attributes to store a handle for the texture buffer
        # I am imagining the case where I have to use different buffer on the same object (e.g., use the same virtual
        # cylinder, but different size of bitmap to be texture-mapped etc)
        self.texture_buffer = texture_buffer

    def set(self, key, val):
        """
        Set uniform value
        """
        if key in self.uniform_dict.keys():
            self.uniform_dict[key] = val
        else:
            raise ValueError('{} is not a Uniform variable of this shader'.format(key) )

    def render(self):
        """
        Render VAO with the primitive hint specified by the shader, as well as using the texture in the buffer
        """
        # Use texture buffer
        if self.texture_buffer is not None:
            self.texture_buffer.use()
        # synchronize uniform variables
        for key in self.uniform_dict.keys():
            self.shader.prog[key].value = self.uniform_dict[key]
        # render
        self.vertex_array.render(self.shader.primitive_type)

    def release(self):
        """
        Release underlying buffer and VAO manually, because OpenGL doesn't do garbage collection
        """
        self.vertex_array.release()
        self.vertex_buffer.release()