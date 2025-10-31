# version 330

in vec2 input_vertices;
out vec2 vpos;


void main(){
  gl_Position = vec4(input_vertices, 0.0, 1.0);
  vpos = input_vertices * 0.5 + 0.5;
}