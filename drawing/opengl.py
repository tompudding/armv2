import os

from OpenGL.arrays import numpymodule
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GL import shaders
from OpenGL.GL.framebufferobjects import *

from .. import globals
from ..globals.types import Point


import sys
import time
from . import constants

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
        self.dirname = os.path.dirname(os.path.realpath(__file__))

    def Use(self):
        shaders.glUseProgram(self.program)

    def Load(self,name,uniforms,attributes):
        vertex_name,fragment_name = (os.path.join('shaders','%s_%s.glsl' % (name,typeof)) for typeof in ('vertex','fragment'))
        codes = []
        for name in vertex_name,fragment_name:
            with open(os.path.join(self.dirname,name),'rb') as f:
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

class CrtBuffer(object):
    TEXTURE_TYPE_SHADOW = 0
    NUM_TEXTURES        = 1
    #WIDTH               = 1024
    #HEIGHT              = 256

    def __init__(self, width, height):
        self.fbo = glGenFramebuffers(1)
        self.BindForWriting()
        try:
            self.InitBound(width,height)
        finally:
            self.Unbind()

    def InitBound(self,width,height):
        self.textures      = glGenTextures(self.NUM_TEXTURES)
        if self.NUM_TEXTURES == 1:
            #Stupid inconsistent interface
            self.textures = [self.textures]
        #self.depth_texture = glGenTextures(1)
        glActiveTexture(GL_TEXTURE0)

        for i in range(self.NUM_TEXTURES):
            glBindTexture(GL_TEXTURE_2D, self.textures[i])
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F, width, height, 0, GL_RGBA, GL_FLOAT, None)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER);
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER);
            glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0 + i, GL_TEXTURE_2D, self.textures[i], 0)

        #glBindTexture(GL_TEXTURE_2D, self.depth_texture)
        #glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT32, width, height, 0, GL_DEPTH_COMPONENT, GL_FLOAT, None)
        #glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, self.depth_texture, 0)
        glDrawBuffers([GL_COLOR_ATTACHMENT0])

        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            print('crapso1')
            raise SystemExit

    def BindForWriting(self):
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, self.fbo)

    def BindForReading(self,offset):
        self.Unbind()
        for i,texture in enumerate(self.textures):
            glActiveTexture(GL_TEXTURE0 + i + offset)
            glBindTexture(GL_TEXTURE_2D, texture)

    def Unbind(self):
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0)


default_shader   = ShaderData()
crt_shader       = ShaderData()

def Init(w, h, pixel_size):
    default_shader.Load('default',
                        uniforms = ('tex','translation','scale',
                                    'screen_dimensions',
                                    'using_textures'),
                        attributes = ('vertex_data',
                                      'tc_data',
                                      'colour_data'))

    crt_shader.Load('crt',
                    uniforms = ('tex','translation','scale',
                                'screen_dimensions','global_time'),
                    attributes = ('vertex_data',
                                  'tc_data'))

    #crt_buffer = CrtBuffer(*pixel_size)

    glClearColor(0.0, 0.0, 0.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)

    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glEnable(GL_DEPTH_TEST);
    #glAlphaFunc(GL_GREATER, 0.25);
    glEnable(GL_ALPHA_TEST);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

def clear_screen():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

def new_crt_frame(crt_buffer):
    default_shader.Use()
    crt_buffer.BindForWriting()
    #glDepthMask(GL_TRUE)
    glClearColor(0.0, 0.0, 0.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    #crt_buffer.BindForWriting()
    #glEnable(GL_DEPTH_TEST)
    #glEnable(GL_BLEND)
    #glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

def end_crt_frame(crt_buffer):
    return

def draw_crt_to_screen(crt_buffer):
    crt_shader.Use()
    glUniform1f(crt_shader.locations.global_time, globals.t/1000.0)
    crt_buffer.BindForReading(0)
    #glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glEnableVertexAttribArray( crt_shader.locations.vertex_data );
    glEnableVertexAttribArray( crt_shader.locations.tc_data );
    #glUniform2f(crt_shader.locations.scale, 0.33333, 0.3333)
    glVertexAttribPointer( crt_shader.locations.vertex_data, 3, GL_FLOAT, GL_FALSE, 0, globals.screen_quadbuffer.vertex_data );
    glVertexAttribPointer( crt_shader.locations.tc_data, 2, GL_FLOAT, GL_FALSE, 0, constants.full_tc );

    glDrawElements(GL_QUADS,globals.screen_quadbuffer.current_size,GL_UNSIGNED_INT,globals.screen_quadbuffer.indices)

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

    crt_shader.Use()
    glUniform3f(crt_shader.locations.screen_dimensions, globals.screen.x, globals.screen.y, 10)
    glUniform1i(crt_shader.locations.tex, 0)
    glUniform2f(crt_shader.locations.translation, 0, 0)
    glUniform2f(crt_shader.locations.scale, 1, 1)


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
