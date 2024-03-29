import numpy

# import globals as globals
# from rebellion.globals.types import Point

from .. import globals
from ..globals.types import Point

from . import opengl
from . import constants
import OpenGL.GL


class ShapeBuffer(object):
    """
    Keeps track of a potentially large number of quads that are kept in a single contiguous array for
    efficient rendering.

    It is used by instantiating it and then passing it as an argument to the quad constructor. The quad
    then remembers where it's vertices and other data are in the large buffers
    """

    def __init__(self, size):
        self.vertex_data = numpy.zeros((size * self.num_points, 3), numpy.float32)
        self.tc_data = numpy.zeros((size * self.num_points, 2), numpy.float32)
        self.colour_data = numpy.ones(
            (size * self.num_points, 4), numpy.float32
        )  # RGBA default is white opaque
        self.back_colour_data = numpy.ones(
            (size * self.num_points, 4), numpy.float32
        )  # RGBA default is white opaque
        self.indices = numpy.zeros(size * self.num_points, numpy.uint32)  # de
        self.size = size
        for i in range(size * self.num_points):
            self.indices[i] = i
        self.current_size = 0
        self.max_size = size * self.num_points
        self.vacant = set()

    def __next__(self):
        """
        Please can we have another quad? If some quads have been deleted and left a hole then we give
        those out first, otherwise we add one to the end.

        FIXME: Implement resizing when full
        """
        if len(self.vacant) > 0:
            # for a vacant one we blatted the indices, so we should reset those...
            out = self.vacant.pop()
            for i in range(self.num_points):
                self.indices[out + i] = out + i
                for j in range(4):
                    self.colour_data[out + i][j] = 1
            return out

        out = self.current_size
        self.current_size += self.num_points
        if self.current_size > self.max_size:
            raise NotImplemented
            # self.max_size *= 2
            # self.vertex_data.resize( (self.max_size,3) )
            # self.tc_data.resize    ( (self.max_size,2) )
        return out

    def truncate(self, n):
        """
        All quads pointing after the truncation point are subsequently invalid, so this call is fairly dangerous.
        In the future we could keep track of child quads and update them ourselves, but right now that is too
        much overhead
        """
        self.current_size = n
        for i in range(self.size * self.num_points):
            self.indices[i] = i
        self.colour_data = numpy.ones((self.max_size, 4), numpy.float32)  # RGBA default is white opaque
        self.vacant = set()

    def remove_shape(self, index):
        """A quad is no longer needed. Because it can be in the middle of our nice block and we can't be spending
        serious cycles moving everything, we just disable it by zeroing out it's indicies. This fragmentation
        has a cost in terms of the number of quads we're going to be asking the graphics card to draw, but
        because the game is so simple I'm hoping it won't ever be an issue

        """
        self.vacant.add(index)
        for i in range(self.num_points):
            self.indices[index + i] = 0
            for j in range(3):
                self.vertex_data[index + i][j] = 0


class QuadBuffer(ShapeBuffer):
    num_points = 4
    draw_type = OpenGL.GL.GL_QUADS

    def __init__(self, size, ui=False, mouse_relative=False):
        self.is_ui = ui
        self.mouse_relative = mouse_relative
        super(QuadBuffer, self).__init__(size)

    def sort_for_depth(self):
        depths = [
            (i, min(self.vertex_data[self.indices[i + j]][1] for j in range(4)))
            for i in range(0, self.current_size, 4)
            if i not in self.vacant
        ]
        # The dotted textures are supposed to be drawn on top of the tiles, so they have their z coordinates
        # added to max_world.y so they have the highest z values. However for draw order we don't want them
        # drawn last else they'll mess up the occlude maps (they have no occlude component), so we mod
        # everything by max_world.y to get them back in place
        depths.sort(key=lambda x: x[1] % globals.tiles.max_world.y, reverse=True)
        # print depths[:100]
        pos = 0
        new_indices = numpy.zeros(self.size * self.num_points, numpy.uint32)
        for i, depth in depths:
            for j in range(4):
                new_indices[pos + j] = self.indices[i + j]
            pos += 4
        self.indices = new_indices


class ShadowQuadBuffer(QuadBuffer):
    def new_light(self):
        row = self.current_size / self.num_points
        light = Quad(self)
        # Now set the vertices for the next line ...
        bl = Point(0, row)
        tr = Point(globals.tactical_screen.x, row + 1)
        light.set_vertices(bl, tr, 0)
        light.shadow_index = row
        return light


class VertexBuffer(ShapeBuffer):
    num_points = 1
    draw_type = OpenGL.GL.GL_POINTS

    def __init__(self, size, ui=False, mouse_relative=False):
        self.is_ui = ui
        self.mouse_relative = mouse_relative
        super(VertexBuffer, self).__init__(size)


class ShapeVertex(object):
    """Convenience object to allow nice slicing of the parent buffer"""

    def __init__(self, index, buffer):
        self.index = index
        self.buffer = buffer

    def __getitem__(self, i):
        if isinstance(i, slice):
            start, stop, stride = i.indices(len(self.buffer) - self.index)
            return self.buffer[self.index + start : self.index + stop : stride]
        return self.buffer[self.index + i]

    def __setitem__(self, i, value):
        if isinstance(i, slice):
            start, stop, stride = i.indices(len(self.buffer) - self.index)
            self.buffer[self.index + start : self.index + stop : stride] = value
        else:
            self.buffer[self.index + i] = value


class Shape(object):
    """
    Object representing a quad. Called with a quad buffer argument that the quad is allocated from
    """

    def __init__(self, source, vertex=None, tc=None, colour_info=None, index=None):
        if index is None:
            self.index = next(source)
        else:
            self.index = index
        self.source = source
        self.vertex = ShapeVertex(self.index, source.vertex_data)
        self.tc = ShapeVertex(self.index, source.tc_data)
        self.colour = ShapeVertex(self.index, source.colour_data)
        self.back_colour = ShapeVertex(self.index, source.back_colour_data)
        if vertex is not None:
            self.vertex[0 : self.num_points] = vertex
        if tc is not None:
            self.tc[0 : self.num_points] = tc
        self.old_vertices = None
        self.deleted = False
        self.enabled = True

    def delete(self):
        """
        This quad is done with permanently. We set a deleted flag to prevent us from accidentally
        trying to use it again, which since the underlying buffers could have been reassigned would cause
        some graphical mentalness
        """
        self.source.remove_shape(self.index)
        self.deleted = True

    def disable(self):
        """
        Temporarily don't draw this quad. We don't have a very nice way of doing this other
        than turning it into an invisible dot in the corner, but since graphics card power is
        essentially free this seems to work nicely
        """
        if self.deleted:
            return
        self.enabled = False
        if self.old_vertices is None:
            self.old_vertices = numpy.copy(self.vertex[0 : self.num_points])
            for i in range(self.num_points):
                self.vertex[i] = (0, 0, 0)

    def enable(self):
        """
        Draw this quad again after it's been disabled
        """
        if self.deleted:
            return
        self.enabled = True
        if self.old_vertices is not None:
            for i in range(self.num_points):
                self.vertex[i] = self.old_vertices[i]
            self.old_vertices = None

    def set_vertices(self, bl, tr, z):
        if self.deleted:
            return
        self.setvertices(self.vertex, bl, tr, z)
        if self.old_vertices is not None:
            self.old_vertices = numpy.copy(self.vertex[0 : self.num_points])
            for i in range(self.num_points):
                self.vertex[i] = (0, 0, 0)

    def set_all_vertices(self, vertices, z):
        if self.deleted:
            return
        setallvertices(self, self.vertex, vertices, z)
        if self.old_vertices is not None:
            self.old_vertices = numpy.copy(self.vertex[0 : self.num_points])
            for i in range(self.num_points):
                self.vertex[i] = (0, 0, 0)

    def get_centre(self):
        return (Point(self.vertex[0][0], self.vertex[0][1]) + Point(self.vertex[2][0], self.vertex[2][1])) / 2

    def translate(self, amount):
        if self.old_vertices is not None:
            vertices = self.old_vertices
        else:
            vertices = self.vertex
        for i in range(4):
            vertices[i][0] -= amount[0]
            vertices[i][1] -= amount[1]

    def set_colour(self, colour):
        if self.deleted:
            return
        self.setcolour(self.colour, colour)

    def set_back_colour(self, colour):
        if self.deleted:
            return
        self.setcolour(self.back_colour, colour)

    def set_colours(self, colours):
        if self.deleted:
            return
        for current, target in zip(self.colour, colours):
            for i in range(self.num_points):
                current[i] = target[i]

    def set_texture_coordinates(self, tc):
        self.tc[0 : self.num_points] = tc


def setverticesquad(self, vertex, bl, tr, z):
    vertex[0] = (bl.x, bl.y, z)
    vertex[1] = (bl.x, tr.y, z)
    vertex[2] = (tr.x, tr.y, z)
    vertex[3] = (tr.x, bl.y, z)


def setallvertices(self, vertex, vertices, z):
    for i, v in enumerate(vertices):
        vertex[i] = (v.x, v.y, z)


def setverticesline(self, vertex, start, end, z):
    vertex[0] = (start.x, start.y, z)
    vertex[1] = (end.x, end.y, z)


def setverticesvertex(self, vertex, start, end, z):
    vertex[0] = (start.x, start.y, z)


def setcolourquad(self, colour, value):
    # colour[:][:] = value * 4
    # for i in range(4):
    #    colour[i][:] = value
    colour[0:4] = value


def setcolourline(self, colour, value):
    for i in range(2):
        for j in range(4):
            colour[i][j] = value[j]


def setcolourvertex(self, colour, value):
    for j in range(4):
        colour[0][j] = value[j]


class Quad(Shape):
    num_points = 4
    setvertices = setverticesquad
    setcolour = setcolourquad


class Line(Shape):
    num_points = 2
    setvertices = setverticesline
    setcolour = setcolourline


class Vertex(Shape):
    num_points = 1
    setvertices = setverticesvertex
    setcolour = setcolourvertex


class QuadBorder(object):
    """Class that draws the outline of a rectangle"""

    def __init__(self, source, line_width, colour=None):
        self.quads = [Quad(source) for i in range(4)]
        self.line_width = line_width
        if colour:
            self.set_colour(colour)

    def set_vertices(self, bl, tr):
        # top bar
        self.quads[0].set_vertices(Point(bl.x, tr.y - self.line_width), tr, constants.DrawLevels.ui + 1)
        # right bar
        self.quads[1].set_vertices(Point(tr.x - self.line_width, bl.y), tr, constants.DrawLevels.ui + 1)

        # bottom bar
        self.quads[2].set_vertices(bl, Point(tr.x, bl.y + self.line_width), constants.DrawLevels.ui + 1)

        # left bar
        self.quads[3].set_vertices(bl, Point(bl.x + self.line_width, tr.y), constants.DrawLevels.ui + 1)

    def set_colour(self, colour):
        for quad in self.quads:
            quad.set_colour(colour)

    def enable(self):
        for quad in self.quads:
            quad.enable()

    def disable(self):
        for quad in self.quads:
            quad.disable()

    def delete(self):
        for quad in self.quads:
            quad.delete()
