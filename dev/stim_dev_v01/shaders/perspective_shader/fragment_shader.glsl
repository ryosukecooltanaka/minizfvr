# version 330

// 3D vertex coordinates + 2D UV map = 5D input
in vec3 vert;
in vec2 uv_orig;

// For each fragment, we output UV coordinate
out vec2 uv;

// Parameters defining the projections
uniform vec2 z_clip; // (near, far)
uniform vec2 fov;


