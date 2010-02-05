"""Given a matrix, visualize the eigenvectors with eigenvalues whose absolute values are smallest but nonzero.

The x axis is the main eigenvector and the y axis is the secondary eigenvector.
Nodes are labeled according to their zero based row index.
"""

from StringIO import StringIO

from scipy import linalg
import scipy
import numpy
import cairo

from SnippetUtil import HandlingError
import SnippetUtil
import CairoUtil
import MatrixUtil
import StoerWagner
import Euclid
import Form

def get_form():
    """
    @return: the body of a form
    """
    # define the default matrix string
    A = numpy.array(StoerWagner.g_stoer_wagner_affinity)
    M = -Euclid.adjacency_to_laplacian(A)
    # define the form objects
    form_objects = [
            Form.Matrix('matrix', 'matrix', M),
            Form.CheckGroup('drawing_options', 'drawing options', [
                Form.CheckItem('axes', 'draw axes', True),
                Form.CheckItem('connections', 'draw connections', True),
                Form.CheckItem('vertices', 'draw vertices', True)]),
            Form.RadioGroup('imageformat', 'image format options', [
                Form.RadioItem('png', 'png', True),
                Form.RadioItem('svg', 'svg'),
                Form.RadioItem('pdf', 'pdf'),
                Form.RadioItem('ps', 'ps')]),
            Form.RadioGroup('contentdisposition', 'image delivery options', [
                Form.RadioItem('inline', 'view the image', True),
                Form.RadioItem('attachment', 'download the image')])]
    return form_objects

def get_eigenvectors(row_major_matrix):
    """
    This gets a couple of left eigenvectors because of the standard format of rate matrices.
    @param row_major_matrix: this is supposed to be a rate matrix
    @return: a pair of eigenvectors
    """
    R = numpy.array(row_major_matrix)
    w, vl, vr = linalg.eig(R, left=True, right=True)
    eigenvalue_info = list(sorted((abs(x), i) for i, x in enumerate(w)))
    stationary_eigenvector_index = eigenvalue_info[0][1]
    first_axis_eigenvector_index = eigenvalue_info[1][1]
    second_axis_eigenvector_index = eigenvalue_info[2][1]
    return vl.T[first_axis_eigenvector_index], vl.T[second_axis_eigenvector_index]

def get_rescaled_vector(v):
    """
    @param v: an array or list of floating point values
    @return: a list of floating point values rescaled to be in the range (0, 1)
    """
    width = max(v) - min(v)
    if not width:
        return [.5 for x in v]
    return [(x-min(v)) / width for x in v]

def get_image(row_major_matrix, width_and_height, image_format, draw_axes, draw_connections, draw_labels):
    """
    @param row_major_matrix: this is supposed to be a rate matrix
    @param width_and_height: the dimensions of the output image
    @param image_format: like 'svg', 'png', 'ps', 'pdf', et cetera
    @param draw_axes: True if axes should be drawn
    @param draw_connections: True if connections should be drawn
    @param draw_labels: True if labels should be drawn
    @return: a string containing the image data
    """
    width, height = width_and_height
    n = len(row_major_matrix)
    # get eigenvectors scaled to [0, 1]
    va, vb = get_eigenvectors(row_major_matrix)
    rescaled_a = get_rescaled_vector(va)
    rescaled_b = get_rescaled_vector(vb)
    # create the surface
    cairo_helper = CairoUtil.CairoHelper(image_format)
    surface = cairo_helper.create_surface(width, height)
    context = cairo.Context(surface)
    # draw the background
    context.save()
    context.set_source_rgb(.9, .9, .9)
    context.paint()
    context.restore()
    # define the border
    border_fraction = .1
    # draw the axes if requested
    if draw_axes:
        # begin drawing
        context.save()
        context.set_source_rgb(.9, .7, .7)
        # draw the y axis
        dx = max(va) - min(va)
        tx = -min(va)/dx
        xzero = (tx * (1 - 2*border_fraction) + border_fraction) * width
        context.move_to(xzero, 0)
        context.line_to(xzero, height)
        context.stroke()
        # draw the x axis
        dy = max(vb) - min(vb)
        ty = -min(vb)/dy
        yzero = (ty * (1 - 2*border_fraction) + border_fraction) * height
        context.move_to(0, yzero)
        context.line_to(width, yzero)
        context.stroke()
        # stop drawing
        context.restore()
    # draw the connections if requested
    if draw_connections:
        # begin drawing
        context.save()
        context.set_source_rgb(.8, .8, .8)
        for i in range(n):
            for j in range(n):
                if i < j and row_major_matrix[i][j] != 0:
                    x, y = rescaled_a[i], rescaled_b[i]
                    nx = (x * (1 - 2*border_fraction) + border_fraction) * width
                    ny = (y * (1 - 2*border_fraction) + border_fraction) * height
                    context.move_to(nx, ny)
                    x, y = rescaled_a[j], rescaled_b[j]
                    nx = (x * (1 - 2*border_fraction) + border_fraction) * width
                    ny = (y * (1 - 2*border_fraction) + border_fraction) * height
                    context.line_to(nx, ny)
                    context.stroke()
        # stop drawing
        context.restore()
    # draw a scatter plot of the states using the eigenvectors as axes
    if draw_labels:
        for i, (x, y) in enumerate(zip(rescaled_a, rescaled_b)):
            state_string = str(i)
            nx = (x * (1 - 2*border_fraction) + border_fraction) * width
            ny = (y * (1 - 2*border_fraction) + border_fraction) * height
            context.move_to(nx, ny)
            context.show_text(state_string)
    # get the image string
    return cairo_helper.get_image_string()

def get_response(fs):
    """
    @param fs: a FieldStorage object containing the cgi arguments
    @return: a (response_headers, response_text) pair
    """
    M = fs.matrix
    if M.shape[0] < 3 or M.shape[1] < 3:
        raise HandlingError('expected at least a 3x3 matrix')
    # draw the image
    try:
        image_string = get_image(M.tolist(), (640, 480), fs.imageformat, fs.axes, fs.connections, fs.vertices)
    except CairoUtil.CairoUtilError, e:
        raise HandlingError(e)
    # specify the content type
    response_headers = []
    format_to_content_type = {'svg':'image/svg+xml', 'png':'image/png', 'pdf':'application/pdf', 'ps':'application/postscript'}
    response_headers.append(('Content-Type', format_to_content_type[fs.imageformat]))
    # specify the content disposition
    image_filename = 'plot.' + fs.imageformat
    response_headers.append(('Content-Disposition', "%s; filename=%s" % (fs.contentdisposition, image_filename)))
    # return the response
    return response_headers, image_string
