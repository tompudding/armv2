import drawing
import os

from OpenGL.arrays import numpymodule
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GL import shaders
from OpenGL.GL.framebufferobjects import *
from globals.types import Point
import globals
import time
import constants

numpymodule.NumpyHandler.ERROR_ON_COPY = True

class ShaderLocations(object):
    def __init__(self):
        self.tex               = None
        self.vertex_data       = None
        self.tc_data           = None
        self.colour_data       = None
        self.using_textures    = None
        self.screen_dimensions = None
        self.translation       = None
        self.scale             = None

class ShaderData(object):
    def __init__(self):
        self.program   = None
        self.locations = ShaderLocations()
        self.dimensions = (0, 0, 0)

    def Use(self):
        shaders.glUseProgram(self.program)

    def Load(self,name,uniforms,attributes):
        vertex_name,fragment_name = (os.path.join('drawing','shaders','%s_%s.glsl' % (name,typeof)) for typeof in ('vertex','fragment'))
        codes = []
        for name in vertex_name,fragment_name:
            with open(name,'rb') as f:
                data = f.read()
            codes.append(data)
        VERTEX_SHADER   = shaders.compileShader(codes[0]  , GL_VERTEX_SHADER)
        FRAGMENT_SHADER = shaders.compileShader(codes[1]  , GL_FRAGMENT_SHADER)
        self.program = glCreateProgram()
        shads = (VERTEX_SHADER, FRAGMENT_SHADER)
        for shader in shads:
            glAttachShader(self.program, shader)
        self.fragment_shader_attrib_binding()
        self.program = shaders.ShaderProgram( self.program )
        glLinkProgram(self.program)
        self.program.check_validate()
        self.program.check_linked()
        for shader in shads:
            glDeleteShader(shader)
        #self.program    = shaders.compileProgram(VERTEX_SHADER,FRAGMENT_SHADER)
        for (namelist,func) in ((uniforms,glGetUniformLocation),(attributes,glGetAttribLocation)):
            for name in namelist:
                setattr(self.locations,name,func(self.program,name))

    def fragment_shader_attrib_binding(self):
        pass

default_shader   = ShaderData()

def Init(w,h):
    default_shader.Load('default',
                        uniforms = ('tex','translation','scale',
                                    'screen_dimensions',
                                    'using_textures'),
                        attributes = ('vertex_data',
                                      'tc_data',
                                      'colour_data'))

    glClearColor(0.0, 0.0, 0.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)

    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glEnable(GL_DEPTH_TEST);
    #glAlphaFunc(GL_GREATER, 0.25);
    glEnable(GL_ALPHA_TEST);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

def NewFrame():
    #default_shader.Use()
    #glDepthMask(GL_TRUE)
    #glClearColor(0.0, 0.0, 0.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    #glEnable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

def EndFrame():
    pass

def InitDrawing():
    """
    Should only need to be called once at the start (but after Init)
    to enable the full client state. We turn off and on again where necessary, but
    generally try to keep them all on
    """
    default_shader.Use()
    glUniform3f(default_shader.locations.screen_dimensions, globals.screen.x, globals.screen.y, 10)
    glUniform1i(default_shader.locations.tex, 0)
    glUniform2f(default_shader.locations.translation, 0, 0)
    glUniform2f(default_shader.locations.scale, 1, 1)


def DrawAll(quad_buffer,texture):
    #This is a copy paste from the above function, but this is the inner loop of the program, and we need it to be fast.
    #I'm not willing to put conditionals around the normal lines, so I made a copy of the function without them
    glActiveTexture(GL_TEXTURE0)
    glBindTexture(GL_TEXTURE_2D, texture.texture)
    glUniform1i(default_shader.locations.using_textures, 1)

    glEnableVertexAttribArray( default_shader.locations.vertex_data );
    glEnableVertexAttribArray( default_shader.locations.tc_data );
    glEnableVertexAttribArray( default_shader.locations.colour_data );

    glVertexAttribPointer( default_shader.locations.vertex_data, 3, GL_FLOAT, GL_FALSE, 0, quad_buffer.vertex_data );
    glVertexAttribPointer( default_shader.locations.tc_data, 2, GL_FLOAT, GL_FALSE, 0, quad_buffer.tc_data );
    glVertexAttribPointer( default_shader.locations.colour_data, 4, GL_FLOAT, GL_FALSE, 0, quad_buffer.colour_data );

    glDrawElements(GL_QUADS,quad_buffer.current_size,GL_UNSIGNED_INT,quad_buffer.indices)
    glDisableVertexAttribArray( default_shader.locations.vertex_data );
    glDisableVertexAttribArray( default_shader.locations.tc_data );
    glDisableVertexAttribArray( default_shader.locations.colour_data );

def DrawNoTexture(quad_buffer):
    glUniform1i(default_shader.locations.using_textures, 0)

    glEnableVertexAttribArray( default_shader.locations.vertex_data );
    glEnableVertexAttribArray( default_shader.locations.colour_data );

    glVertexAttribPointer( default_shader.locations.vertex_data, 3, GL_FLOAT, GL_FALSE, 0, quad_buffer.vertex_data );
    glVertexAttribPointer( default_shader.locations.colour_data, 4, GL_FLOAT, GL_FALSE, 0, quad_buffer.colour_data );

    glDrawElements(GL_QUADS,quad_buffer.current_size,GL_UNSIGNED_INT,quad_buffer.indices)

    glDisableVertexAttribArray( default_shader.locations.vertex_data );
    glDisableVertexAttribArray( default_shader.locations.colour_data );

