#version 130

uniform vec3 screen_dimensions;
uniform vec2 translation;
uniform vec2 scale;
in vec3 vertex_data;
in vec2 tc_data;
in vec4 fore_colour_data;
in vec4 back_colour_data;

out vec2 texcoord;
out vec4 fore_colour;
out vec4 back_colour;

void main()
{
    gl_Position = vec4( (((vertex_data.x+translation.x)*2*scale.x)/screen_dimensions.x)-1,
                        (((vertex_data.y+translation.y)*2*scale.y)/screen_dimensions.y)-1,
                        -vertex_data.z/screen_dimensions.z,
                        1.0) ;
    texcoord    = tc_data;
    fore_colour = fore_colour_data / 256.0;
    back_colour = back_colour_data / 256.0;
}
