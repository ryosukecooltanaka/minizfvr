# version 330

// passed thru from the vertex shader
in vec2 uv_coord;

uniform sampler2D Texture;

void main(){
    gl_FragColor = texture(Texture, uv_coord);
}