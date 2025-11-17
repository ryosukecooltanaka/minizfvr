# version 330

// basic vertex shader that takes care of model, viewing, and perspective transformations
// See Readme for the reasoning behind all the linear algebra

// --- Inputs & Outputs

// Input is 5 dimensional: 3D (model local) coordinate + 2D UV mapping
in vec3 vert; // vertex coordinate
in vec2 orig_uv_coord; // UV values

// We pass through the UV coordinate
out vec2 uv_coord;

// --- Uniform Keywords

// Uniform keywords for model translation and rotation (model transform)
uniform vec3 rot;
uniform vec3 tr;

// Uniform keywords for camera definition (viewing transform)
uniform vec3 camera;
uniform vec3 gaze;
uniform vec3 up;

// Uniform keywords for perspective transformation
uniform vec2 fov_x; // (left, right), where left < right
uniform vec2 fov_y; // (bottom, top), where bottom < top
uniform vec2 clip_z; // (near, far), both positive! (distance, not coordinate)

// --- Matrix Definitions
// Caution: matrices are defined column first -- what you see is the transpose of the actual matrix!

// Rotation about each axis (model transform)

mat3 aboutX(){
    return mat3(
        1, 0,          0,
        0, cos(rot.x), sin(rot.x),
        0, -sin(rot.x), cos(rot.x)
    );
}

mat3 aboutY(){
    return mat3(
        cos(rot.y), 0, -sin(rot.y),
        0,          1, 0,
        sin(rot.y), 0, cos(rot.y)
    );
}

mat3 aboutZ(){
    return mat3(
        cos(rot.z),  sin(rot.z), 0,
        -sin(rot.z), cos(rot.z), 0,
        0,           0,          1
    );
}

// Viewing transform matrix (i.e. lookat matrix)

mat4 lookat(){
    // First, define axes as necessary
    vec3 view_z = -normalize(gaze - camera); // camera points negative Z!
    vec3 view_x = normalize(cross(up, view_z)); // right hand rule!
    vec3 view_y = cross(view_z, view_x); // recalculate up so it is orthogonal to both Z/X

    return mat4(
        view_x.x, view_y.x, view_z.x, 0,
        view_x.y, view_y.y, view_z.y, 0,
        view_x.z, view_y.z, view_z.z, 0,
        -dot(view_x, camera), -dot(view_y, camera), -dot(view_z, camera), 1
    );
}

// Perspective transformation
mat4 perspective(){
    // first define the edges of clipping planes
    float N = clip_z.x;
    float F = clip_z.y;
    float L = tan(fov_x.x) * N;
    float R = tan(fov_x.y) * N;
    float B = tan(fov_y.x) * N;
    float T = tan(fov_y.y) * N;

    // again mind the transpose...
    return mat4(
        2.0*N/(R-L), 0, 0, 0,
        0, 2.0*N/(T-B), 0, 0,
        (R+L)/(R-L), (T+B)/(T-B), -(F+N)/(F-N), -1,
        0, 0, -2.0*F*N/(F-N), 0
    );
}

// --- Do the projection!
void main(){
    // This is not commutative... but it's unlikely I ever rotate things on multiple axes!
    vec3 rotated = aboutZ() * aboutY() * aboutX() * vert;
    vec3 translated = rotated + tr;
    vec4 lookedat = lookat() * vec4(translated, 1.0); // padding for homogeneous notation
    gl_Position = perspective() * lookedat;
    uv_coord = orig_uv_coord; // just pass through
}