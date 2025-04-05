#version 130
#extension GL_ARB_explicit_attrib_location : require

uniform sampler2D tex;
uniform int using_textures;
//This is apparently a horrible idea, but I'm not sure how else to get all the pixel data in. "Render it to a texture" people say, but this is rendering it to a texture! Maybe I need to build it up in segments or something, rendering small subsections to textures?
uniform uvec4 pixels[600];
in vec2 texcoord;
in vec4 fore_colour;
in vec4 back_colour;

out vec4 out_colour;

void main()
{

        //We need to ask if this pixel is on or not
        uint x = uint(gl_FragCoord.x);
        uint y = uint(gl_FragCoord.y);
        uint cell_x = x / uint(8);
        uint cell_y = y / uint(8);
        uint n = x + y*uint(320);
        uint word = n / uint(32);
        uint outer_word = word / uint(4);
        uint inner_word = word & uint(3);
        uint bit = n & uint(0x1f);
        uint bob = (pixels[outer_word][inner_word] >> bit)&uint(1);
        //if( uint(1) == uint(1) ) {
        if( bob == uint(1)) {
            out_colour = fore_colour;
        }
        else {
            out_colour = back_colour;
        }

    //if(out_colour.a == 0) {
    //    discard;
    //}
}
