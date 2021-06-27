#version 130
#extension GL_ARB_explicit_attrib_location : require
//MattiasCRT from shadertoy.org/view/Ms23DR
// Loosely based on postprocessing shader by inigo quilez, License Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License.


uniform sampler2D tex;
uniform float global_time;
uniform vec2 screen_index;
in vec2 texcoord;
in vec3 screen_dimensions;

out vec4 out_colour;

//TODO: set this dynamically?
#define NUM_SCREENS 5

/* void main() */
/* { */
/*     out_colour = texture(tex, texcoord); */
/* } */

vec2 curve(vec2 uv)
{
	uv = (uv - 0.5) * 2.0;
	uv *= 1.1;
	uv.x *= 1.0 + pow((abs(uv.y) / 5.0), 2.0);
	uv.y *= 1.0 + pow((abs(uv.x) / 4.0), 2.0);
	uv  = (uv / 2.0) + 0.5;
	uv =  uv *0.92 + 0.04;
	return uv;
}

vec2 adjust_tc(vec2 uv, vec2 screen_index) {
    return screen_index + (uv/NUM_SCREENS);
}

void main()
{
    vec2 q = texcoord;
    vec2 uv = q;
    //float global_time = 1.0;
    uv = curve( uv );
    //vec3 oricol = texture2D( tex, vec2(q.x*2,q.y*2) ).xyz;
    vec3 col;
    float x = 0.00;// sin(0.3*global_time+uv.y*21.0)*sin(0.7*global_time+uv.y*29.0)*sin(0.3+0.33*global_time+uv.y*31.0)*0.0017;
    float screen_x = 1;
    float screen_y = 0;

    col.r = texture2D(tex, adjust_tc(vec2(x+uv.x+0.001,uv.y+0.001), screen_index)).x+0.05;
    col.g = texture2D(tex, adjust_tc(vec2(x+uv.x+0.000,uv.y-0.002), screen_index)).y+0.05;
    col.b = texture2D(tex, adjust_tc(vec2(x+uv.x-0.002,uv.y+0.000), screen_index)).z+0.05;
    col.r += 0.08*texture2D(tex,adjust_tc(0.75* vec2(x+0.025, -0.027)+vec2(uv.x+0.001,uv.y+0.001), screen_index)).x;
    col.g += 0.05*texture2D(tex,adjust_tc(0.75* vec2(x+-0.022, -0.02)+vec2(uv.x+0.000,uv.y-0.002), screen_index)).y;
    col.b += 0.08*texture2D(tex,adjust_tc(0.75* vec2(x+-0.02, -0.018)+vec2(uv.x-0.002,uv.y+0.000), screen_index)).z;

    col = clamp(col*0.6+0.4*col*col*1.0,0.0,1.0);

    float vig = (0.0 + 1.0*16.0*uv.x*uv.y*(1.0-uv.x)*(1.0-uv.y));
    col *= vec3(pow(vig,0.3));

    col *= vec3(0.95,1.05,0.95);
    col *= 2.8;

    float scans = 0.9;

    float s = pow(scans,1.7);
    col = col*vec3( 0.4+0.7*s) ;

    col *= 1.0+0.01*sin(110.0*global_time);
    if (uv.x < 0.0 || uv.x > 1.0)
        col *= 0.0;
    if (uv.y < 0.0 || uv.y > 1.0)
        col *= 0.0;

    col*=1.0-0.65*vec3(clamp((mod(gl_FragCoord.x, 2.0)-1.0)*2.0,0.0,1.0));

    //float comp = smoothstep( 0.1, 0.9, sin(global_time) );

    // Remove the next line to stop cross-fade between original and postprocess
//	col = mix( col, oricol, comp );

    out_colour = vec4(col,1.0);
}
