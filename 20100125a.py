"""Plot some connected points using resistance distance MDS.

From the input graph,
create the Laplacian using edge weights
equal to reciprocals of Euclidean distances.
The pseudoinverse of the Laplacian is the Gower
matrix used for MDS.
Vertices are visualized according to
the first two MDS coordinates.
Straight lines are drawn to connect points
for which an edge was specified in the input graph.
The aspect ratio is preserved.
"""

from StringIO import StringIO
import math

import cairo
import numpy as np

from SnippetUtil import HandlingError
import Codon
import Form
import FormOut
import CairoUtil
import Util
import Euclid
import BuildTreeTopology
import const

g_default_data = const.read('20100730e')

class ImageInfo:

    def __init__(self, total_width, total_height, border, image_format):
        """
        @param total_width: total image width in pixels
        @param total_height: total image height in pixels
        @param border: image border size in pixels
        @param image_format: image format
        """
        self.total_width = total_width
        self.total_height = total_height
        self.border = border
        self.image_format = image_format
        if self.get_drawable_width() < 1 or self.get_drawable_height < 1:
            raise ValueError('no drawable area')

    def get_drawable_width(self):
        return self.total_width - 2*self.border

    def get_drawable_height(self):
        return self.total_height - 2*self.border


def get_form():
    """
    @return: the body of a form
    """
    # define the default labeled points
    lines = Util.get_stripped_lines(g_default_data.splitlines())
    # define the form objects
    form_objects = [
            Form.MultiLine('graph_data', 'connected points',
                '\n'.join(lines)),
            Form.RadioGroup('edge_weight_options', 'edge weights', [
                Form.RadioItem('unweighted', 'all weights are 1.0', True),
                Form.RadioItem('weighted', 'weights are inverse distances')]),
            Form.CheckGroup('axis_options', 'axis options', [
                Form.CheckItem('flip', 'flip principal axis', False)]),
            Form.RadioGroup('color_options', 'color options', [
                Form.RadioItem('black', 'all black', True),
                Form.RadioItem('color', 'first axis coloration')]),
            Form.Integer('total_width', 'total image width',
                640, low=3, high=2000),
            Form.Integer('total_height', 'total image height',
                480, low=3, high=2000),
            Form.Integer('border', 'image border size',
                10, low=0, high=2000),
            Form.ImageFormat()]
    return form_objects

def get_form_out():
    return FormOut.Image('plot')

def get_image_string(points, edges, point_colors, all_black, image_info):
    """
    @param points: an ordered list of (x, y) pairs
    @param edges: a set of point index pairs
    @param point_colors: a list of rgb float triples
    @param all_black: a flag that overrides the fancy coloring
    @param image_info: an object with image presentation details
    """
    # unpack some image info
    t_width = image_info.total_width
    t_height = image_info.total_height
    border = image_info.border
    image_format = image_info.image_format
    # define the drawable region
    width = image_info.get_drawable_width()
    height = image_info.get_drawable_height()
    # get the x and y coordinates of the points
    x_coords, y_coords_raw = zip(*points)
    # Flip the y coordinates so that greater values of y
    # are shown near the top of the image.
    y_coords = [-y for y in y_coords_raw]
    unscaled_width = max(x_coords) - min(x_coords)
    unscaled_height = max(y_coords) - min(y_coords)
    # rescale the points to fit in the drawable part of the image
    c_width = width / unscaled_width
    c_height = height / unscaled_height
    c = min(c_width, c_height)
    x_rescaled = [x*c for x in x_coords]
    y_rescaled = [y*c for y in y_coords]
    # translate the points so that their minimum coordinate is zero
    x_min = min(x_rescaled)
    y_min = min(y_rescaled)
    x_trans = [x-x_min for x in x_rescaled]
    y_trans = [y-y_min for y in y_rescaled]
    # translate the points to account for the border
    x_final = [x+border for x in x_trans]
    y_final = [y+border for y in y_trans]
    # create the surface
    cairo_helper = CairoUtil.CairoHelper(image_format)
    surface = cairo_helper.create_surface(t_width, t_height)
    context = cairo.Context(surface)
    # draw the background
    context.save()
    context.set_source_rgb(.9, .9, .9)
    context.paint()
    context.restore()
    # draw the edges
    for i, j in edges:
        context.save()
        if not all_black:
            context.set_source_rgb(0.6, 0.6, 0.6)
        context.move_to(x_final[i], y_final[i])
        context.line_to(x_final[j], y_final[j])
        context.close_path()
        context.stroke()
        context.restore()
    # draw the points
    radius = 3.0
    for x, y, point_color in zip(x_final, y_final, point_colors):
        # draw a filled circle
        context.save()
        if not all_black:
            context.set_source_rgb(*point_color)
        context.arc(x, y, radius, 0, 2 * math.pi)
        context.close_path()
        context.fill()
        context.restore()
    # get the image string
    return cairo_helper.get_image_string()

def read_points_and_edges(multiline):
    """
    @param multiline: input like the default data
    @return: a list of (x, y) points and a set of point-index-pair edges
    """
    lines = Util.get_stripped_lines(multiline.splitlines())
    try:
        POINTS_index = lines.index('POINTS')
    except ValueError as e:
        raise HandlingError('expected a line that says POINTS')
    try:
        EDGES_index = lines.index('EDGES')
    except ValueError as e:
        raise HandlingError('expected a line that says EDGES')
    if POINTS_index > EDGES_index:
        raise HandlingError('expected points before edges')
    # read the points
    points = []
    points_lines = lines[POINTS_index + 1: EDGES_index]
    for i, point_line in enumerate(points_lines):
        values = point_line.split()
        if len(values) != 3:
            raise ValueError('each POINTS row should have three values')
        s_index, s_x, s_y = values
        try:
            index = int(s_index)
            x = float(s_x)
            y = float(s_y)
        except ValueError as e:
            raise HandlingError('a value in a POINTS row has the wrong type')
        if index != i:
            raise HandlingError('the POINTS indices should match their order')
        point = (x, y)
        points.append(point)
    # read the edges
    edges = set()
    edges_lines = lines[EDGES_index + 1:]
    for edge_line in edges_lines:
        values = edge_line.split()
        if len(values) != 2:
            raise ValueError('each EDGES row should have three values')
        s_i, s_j = values
        try:
            i = int(s_i)
            j = int(s_j)
        except ValueError as e:
            raise HandlingError('a value in a EDGES row has the wrong type')
        edge = (i, j)
        edges.add(edge)
    # return the points and edges
    return points, edges

def edges_to_laplacian(edges, edge_weights):
    """
    Return a Laplacian matrix given a list of unweighted edges.
    Vertices of the graph are expected to be indexed
    sequentially starting at zero.
    @param edges: a list of connected point index pairs
    @param edge_weights: a list of edge weights
    @return: a numpy array laplacian matrix
    """
    source_indices, sink_indices = zip(*edges)
    all_indices = set(source_indices) | set(sink_indices)
    npoints = max(all_indices) + 1
    if all_indices != set(range(npoints)):
        raise ValueError('the graph is not connected')
    # create the adjacency matrix
    A = np.zeros((npoints, npoints))
    for weight, (i, j) in zip(edge_weights, edges):
        A[i, j] = weight
        A[j, i] = weight
    # create the laplacian matrix
    L = Euclid.adjacency_to_laplacian(A)
    return L

def valuations_to_colors(valuations):
    """
    @param valuations: Principal axis valuations of the points
    @return: a conformant list of cairo formatted rgb triples
    """
    dark_blue = (0.0, 0.0, 1.0)
    light_blue = (0.4, 0.4, 1.0)
    dark_red = (1.0, 0.0, 0.0)
    light_red = (1.0, 0.4, 0.4)
    negative_valuations = [v for v in valuations if v <= 0]
    positive_valuations = [v for v in valuations if v > 0]
    neg_median = np.median(negative_valuations)
    pos_median = np.median(positive_valuations)
    colors = []
    for v in valuations:
        if v <= 0:
            if v <= neg_median:
                c = dark_blue
            else:
                c = light_blue
        else:
            if v >= pos_median:
                c = dark_red
            else:
                c = light_red
        colors.append(c)
    return colors

def get_response_content(fs):
    # read the points and edges
    points, edges = read_points_and_edges(fs.graph_data)
    # define edge weights
    if fs.weighted:
        np_points = [np.array(p) for p in points]
        dists = [np.linalg.norm(np_points[j] - np_points[i]) for i, j in edges]
        weights = [1.0 / d for d in dists]
    else:
        weights = [1.0 for e in edges]
    # get the width and height of the drawable area of the image
    width = fs.total_width - 2*fs.border
    height = fs.total_height - 2*fs.border
    if width < 1 or height < 1:
        msg = 'the image dimensions do not allow for enough drawable area'
        raise HandlingError(msg)
    # define the point colors using the unweighted graph Fiedler loadings
    L = edges_to_laplacian(edges, weights)
    G = np.linalg.pinv(L)
    X = Euclid.dccov_to_points(G)
    points = [(-p[0] if fs.flip else p[0], p[1]) for p in X]
    x_coords, y_coords = zip(*points)
    colors = valuations_to_colors(x_coords)
    # draw the image
    ext = Form.g_imageformat_to_ext[fs.imageformat]
    info = ImageInfo(fs.total_width, fs.total_height, fs.border, ext)
    try:
        return get_image_string(points, edges, colors, fs.black, info)
    except CairoUtil.CairoUtilError as e:
        raise HandlingError(e)
