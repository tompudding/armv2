#version 130
#extension GL_ARB_explicit_attrib_location : require
//MattiasCRT from shadertoy.org/view/Ms23DR
// Loosely based on postprocessing shader by inigo quilez, License Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License.


uniform sampler2D tex;
uniform float global_time;
in vec2 texcoord;
in vec3 screen_dimensions;

out vec4 out_colour;

/*    Phosphor-21x
    Copyright (C) 2011 caligari
    This program is free software; you can redistribute it and/or modify it
    under the terms of the GNU General Public License as published by the Free
    Software Foundation; either version 2 of the License, or (at your option)
    any later version.
    (caligari gave their consent to have this shader distributed under the GPL
    in this message:
        http://board.byuu.org/viewtopic.php?p=36219#p36219
        "As I said to Hyllian by PM, I'm fine with the GPL (not really a big
        deal...)"
   )
*/

//#version 150

//uniform sampler2D tex[];
//uniform vec4 sourceSize[];
//uniform vec4 screen_dimensions;
vec2 sourceSize = vec2(320,240);
//in Vertex {
//  vec2 texcoord;
//};

//out vec4 out_colour;

//	#define TRIAD1
//	#define TRIAD2
//	#define distortion 0.15

// Uncomment to use neighbours from previous and next scanlines
//#define USE_ALL_NEIGHBOURS
#define distortion 0.2

	// 0.5 = same width as original pixel	1.0-1.2 seems nice
	#define SPOT_WIDTH	1.2
	// Shape of the spots	1.0 = circle, 4.0 = ellipse with width = 2*height  ************/
    #define X_SIZE_ADJUST	2.0
/******************************** To increase bloom / luminosity play with this parameter ************/
    #define FACTOR_ADJUST 2.5

#ifdef distortion
    vec2 barrelDistortion(vec2 coord) {
      vec2 cc = coord - 0.5;
      float dist = dot(cc, cc);
      return 0.5 + cc * (1.0 + (dist + distortion * dist * dist) * distortion) / (1.0 + (0.25 + distortion * 0.25 * 0.25) * distortion);
    }

    #define TEXCOORDS	barrelDistortion(texcoord * sourceSize / sourceSize) * sourceSize / sourceSize
#else
    #define TEXCOORDS	texcoord.xy
#endif

	#define SCALE	21.0
    // Constants
    vec4 luminosity_weights = vec4( 0.2126, 0.7152, 0.0722, 0.0 );		//  Y = 0.2126 R + 0.7152 G + 0.0722 B
	//vec4 luminosity_weights = vec4( 0.6, 0.3, 0.1, 0.0 );

    vec2 onex = vec2( 1.0 / sourceSize.x, 0.0 );
    #ifdef USE_ALL_NEIGHBOURS
    vec2 oney = vec2( 0.0, 1.0 / sourceSize.y);
    #endif

    float factor( float lumi, vec2 dxy)
	{
		float dist = sqrt( dxy.x * dxy.x + dxy.y * dxy.y * X_SIZE_ADJUST  ) / SCALE;
		return (2.0 + lumi ) * (1.0 - smoothstep( 0.0, SPOT_WIDTH, dist ) ) / FACTOR_ADJUST ;
	}

    void main(void) {
    	vec2 coords_scaled = floor( TEXCOORDS * sourceSize.xy * SCALE );
    	vec2 coords_snes = floor( coords_scaled / SCALE );	//TEXCOORDS * sourceSize ) ;
    	vec2 coords_texture = ( coords_snes + vec2(0.5) ) / sourceSize.xy;

    	vec2 ecart = coords_scaled - ( SCALE * coords_snes + vec2( SCALE * 0.5 - 0.5 ) ) ;

    	vec4 color = texture(tex, coords_texture );
    	float luminosity = dot( color, luminosity_weights );

    	color *= factor( luminosity, ecart );

    	// RIGHT NEIGHBOUR
    	vec4 pcol = texture(tex, coords_texture + onex);
    	luminosity = dot( pcol, luminosity_weights );
    	color += pcol * factor( luminosity, ecart + vec2( -SCALE , 0.0) );

    	// LEFT NEIGHBOUR
	   	pcol = texture(tex, coords_texture - onex);
    	luminosity = dot( pcol, luminosity_weights );
    	color += pcol * factor( luminosity, ecart + vec2( SCALE , 0.0) );

#ifdef USE_ALL_NEIGHBOURS
    	// TOP
	   	pcol = texture(tex, coords_texture + oney);
    	luminosity = dot( pcol, luminosity_weights );
    	color += pcol * factor( luminosity, ecart + vec2( 0.0, -SCALE) );

    	// TOP-LEFT
	   	pcol = texture(tex, coords_texture + oney - onex);
    	luminosity = dot( pcol, luminosity_weights );
    	color += pcol * factor( luminosity, ecart + vec2( SCALE, -SCALE) );

    	// TOP-RIGHT
	   	pcol = texture(tex, coords_texture + oney + onex);
    	luminosity = dot( pcol, luminosity_weights );
    	color += pcol * factor( luminosity, ecart + vec2( -SCALE, -SCALE) );

    	// BOTTOM
	   	pcol = texture(tex, coords_texture - oney);
    	luminosity = dot( pcol, luminosity_weights );
    	color += pcol * factor( luminosity, ecart + vec2( 0.0, SCALE) );

    	// BOTTOM-LEFT
	   	pcol = texture(tex, coords_texture - oney - onex);
    	luminosity = dot( pcol, luminosity_weights );
    	color += pcol * factor( luminosity, ecart + vec2( SCALE, SCALE) );

    	// BOTTOM-RIGHT
	   	pcol = texture(tex, coords_texture - oney + onex);
    	luminosity = dot( pcol, luminosity_weights );
    	color += pcol * factor( luminosity, ecart + vec2( -SCALE, SCALE) );
#endif

#ifdef TRIAD1
    	vec2 coords_screen = floor( texcoord.xy * screen_dimensions.xy );

		float modulo = mod( coords_screen.y + coords_screen.x , 3.0 );
		if ( modulo == 0.0 )
			color.rgb *= vec3(1.0,0.5,0.5);
		else if  ( modulo <= 1.0 )
			color.rgb *= vec3(0.5,1.0,0.5);
		else
			color.rgb *= vec3(0.5,0.5,1.0);
#endif

#ifdef TRIAD2
		color = clamp( color, 0.0, 1.0 );

		vec2 coords_screen = floor( texcoord.xy * screen_dimensions.xy );

		float modulo = mod( coords_screen.x , 3.0 );
		if ( modulo == 0.0 )		color.gb *= 0.8;
		else if (  modulo == 1.0 )	color.rb *= 0.8;
		else						color.rg *= 0.8;
#endif

   		out_colour = clamp( color, 0.0, 1.0 );
}
