#version 330

// Minimal shader program for checking that python side is doing the right thing

in vec2 v_pos; // passed through vertex coordinate (with interpolation) from the vertex shader
uniform float t; // Gets time (or anything else) for phase shifting stimuli

void main(){
    // Calculate each RGB channel as some periodic function of position and time
    float r = sin(v_pos.x * 6.28 + t) * 0.5 + 0.5;
    float g = 1.0 - r;
    float b = cos(v_pos.y * 6.28 + t * 2.0) * 0.5 + 0.5;
    gl_FragColor = vec4(r, g, b, 1.0);
}