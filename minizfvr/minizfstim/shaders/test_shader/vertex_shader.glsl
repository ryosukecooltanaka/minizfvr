#version 330

// Minimal shader program to make sure things work as intended on the python side

in vec2 in_vert; // take 2d vertices and draw triangles
out vec2 v_pos;  // pass through coordinates for cool coloring effect
uniform vec2 wriggle; // this is added to in_vert for global translation

void main(){
    gl_Position = vec4(in_vert+wriggle, 0.0, 1.0);
    v_pos = in_vert * 0.5 + 0.5;
}