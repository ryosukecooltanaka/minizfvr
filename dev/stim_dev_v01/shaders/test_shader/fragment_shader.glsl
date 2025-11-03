#version 330

in vec2 v_pos;
uniform float t;
void main(){
    float r = sin(v_pos.x * 6.28 + t) * 0.5 + 0.5;
    float g = 1.0 - r;
    float b = cos(v_pos.y * 6.28 + t * 2.0) * 0.5 + 0.5;
    gl_FragColor = vec4(r, g, b, 1.0);
}