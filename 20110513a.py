"""Draw some TikZ figures to illustrate an ad hoc tree topology resolution.
"""

from StringIO import StringIO

import Form
import FormOut
import tikz


def get_form():
    """
    @return: a list of form objects
    """
    # define the form objects
    form_objects = [
            Form.TikzFormat(),
            Form.ContentDisposition()]
    return form_objects

def get_form_out():
    return FormOut.Tikz()

def get_tikz_text(tikz_body):
    tikz_header = '\\begin{tikzpicture}[scale=0.8]'
    tikz_footer = '\\end{tikzpicture}'
    return '\n'.join([tikz_header, tikz_body, tikz_footer])

def get_latex_text(tikz_text):
    latex_header = '\n'.join([
        '\\documentclass{article}',
        '\\usepackage{tikz}',
        '\\usepackage{subfig}',
        '\\begin{document}'])
    latex_body = tikz_text
    latex_footer = '\\end{document}'
    return '\n'.join([latex_header, latex_body, latex_footer])

def get_float_figure_lines(subfloat_pictures):
    arr = []
    arr.extend([
        '\\begin{figure}',
        '\\centering'])
    for i, picture_text in enumerate(subfloat_pictures):
        arr.extend([
            '\\subfloat[]{',
            '\\label{fig:subfloat-%s}' % i,
            picture_text,
            '}'])
    arr.extend([
        '\\caption{',
        'This figure illustrates an ad-hoc tree topology resolution,',
        'given that the signs of the entries of the',
        '$v^2$ (Fiedler) eigenvector of $L*$',
        'partition the leaves like $\\{1,2\\},\\{3,4,5\\}$',
        'while the signs of the entries of the',
        '$v^3$ eigenvector of $L*$',
        'partition the leaves like $\\{1,2,3,4\\},\\{5\\}$.',
        'Because the harmonically extended Fiedler vector cuts a single edge',
        'separating leaves 1 and 2 from the rest of the leaves, we know',
        'that the tree topology is like (a).',
        'This cuts the tree into \'thick\' and \'thin\' nodal domains,',
        'each of which is cut exactly once by the zeros of the harmonically',
        'extended $v^3$ vector.',
        'Because the $v^3$ signs of 1 and 2 are the same,',
        'the single $v^3$ cut of the \'thick\' domain',
        'must be again on the edge that separates leaves 1 and 2',
        'from the rest of the leaves.',
        'Of the remaining possible tree topologies (b), (c), (d), and (e),',
        'only topology (d) allows a $v^3$ cut of the \'thin\' domain',
        'which in conjunction',
        'with the previously deduced $v^3$ thick domain cut',
        'sign-isolates leaf 5 from the other leaves',
        '(each path between leaf 5 and each leaf in \\{1,2,3,4\\}',
        'intersects an odd number of',
        '$v^3$ cuts while each path between two leaves in \\{1,2,3,4\\}',
        'intersects an even number of $v^3$ cuts).',
        'Therefore given only the leaf partitions induced by the',
        'signs of the first two nonconstant eigenvectors of $L*$',
        'we are in this case able to deduce the topology of the tree.',
        'In general this is not always possible.',
        '}',
        '\\label{fig:subfloats}',
        '\\end{figure}'])
    return arr

def get_vertex_line(v, x, y):
    """
    @param v: the vertex
    @param x: vertex x location
    @param y: vertex y location
    @return: tikz line
    """
    style = 'draw,shape=circle,inner sep=0pt'
    line = '\\node (%s)[%s] at (%.4f, %.4f) {};' % (v, style, x, y)
    return line

def get_edge_line(va, vb):
    """
    @param va: first vertex
    @param vb: second vertex
    @return: tikz line
    """
    line = '\\path (%s) edge node {} (%s);' % (va, vb)
    return line

def get_tikz_lines(newick):
    """
    @param newick: a newick tree string
    @return: a sequence of tikz lines
    """
    # hardcode the axes
    x_index = 0
    y_index = 1
    # get the tree with ordered vertices
    T, B = FtreeIO.newick_to_TB(newick, int)
    leaves = Ftree.T_to_leaves(T)
    internal = Ftree.T_to_internal_vertices(T)
    vertices = leaves + internal
    # get the harmonic extension points
    w, v = Ftree.TB_to_harmonic_extension(T, B, leaves, internal)
    # do not scale using eigenvalues!
    #X_full = np.dot(v, np.diag(np.reciprocal(np.sqrt(w))))
    X_full = v
    X = np.vstack([X_full[:,x_index], X_full[:,y_index]]).T
    # get the tikz lines
    axis_lines = [
            '% draw the axes',
            '\\node (axisleft) at (0, -1.2) {};',
            '\\node (axisright) at (0, 1.2) {};',
            '\\node (axistop) at (1.2, 0) {};',
            '\\node (axisbottom) at (-1.2, 0) {};',
            '\\path (axisleft) edge[draw,color=lightgray] node {} (axisright);',
            '\\path (axistop) edge[draw,color=lightgray] node {} (axisbottom);']
    node_lines = []
    for v, (x,y) in zip(vertices, X.tolist()):
        line = get_vertex_line(v, x, y)
        node_lines.append(line)
    edge_lines = []
    for va, vb in T:
        line = get_edge_line(va, vb)
        edge_lines.append(line)
    return axis_lines + node_lines + edge_lines

def get_tikz_crossed_line(pt, direction, solid=False):
    """
    @param pt: a point
    @param direction: a unit vector
    @param solid: True if the cross should be solid
    @return: some lines of tikz text
    """
    segment_length = 1.0
    cross_radius = 0.25
    ax, ay = pt
    dx, dy = direction
    bx = ax + segment_length * dx
    by = ay + segment_length * dy
    center_x = ax + (segment_length / 2.0) * dx
    center_y = ay + (segment_length / 2.0) * dy
    cos_90 = 0
    sin_90 = 1
    cos_n90 = 0
    sin_n90 = -1
    qx = center_x + cross_radius * (dx*cos_90 - dy*sin_90)
    qy = center_y + cross_radius * (dx*sin_90 + dy*cos_90)
    rx = center_x + cross_radius * (dx*cos_n90 - dy*sin_n90)
    ry = center_y + cross_radius * (dx*sin_n90 + dy*cos_n90)
    style = '' if solid else '[densely dotted]'
    lines = [
        '\\draw[color=lightgray] (%s,%s) -- (%s,%s);' % (ax, ay, bx, by),
        '\\draw%s (%s,%s) -- (%s,%s);' % (style, qx, qy, rx, ry)]
    return lines

def get_fiedler_tikz_lines():
    """
    This should show the Fiedler cut of a tree.
    """
    lines = [
            '\\node[anchor=south] (1) at (1,1) {1};',
            '\\node[anchor=north] (1) at (1,-1) {2};',
            '\\node[anchor=west] (x) at (2.4,0) {$\\{3,4,5\\}$};',
            '\\draw[color=lightgray] (1,1) -- (1,0);',
            '\\draw[color=lightgray] (1,0) -- (1,-1);',
            '\\draw[color=lightgray] (1,0) -- (2,0);',
            '\\draw[color=lightgray] (2,0) -- (2.4,0.4);',
            '\\draw[color=lightgray] (2,0) -- (2.4,-0.4);',
            '\\draw[color=lightgray] (2.4,0.4) -- (2.4,-0.4);',
            '\\draw (1.5,0.25) -- (1.5,-0.25);']
    return lines

def get_preamble_lines():
    """
    @return: some tikz lines common to several tikz figures
    """
    preamble_horizontal = [
            '\\node[anchor=east] (1) at (0,0) {1};',
            '\\node[anchor=north] (2) at (1,-1) {2};',
            '\\draw[line width=0.1cm,color=lightgray] (0,0) -- (1.5,0);',
            '\\draw[line width=0.1cm,color=lightgray] (1,0) -- (1,-1);',
            '\\draw[color=lightgray] (1.5,0) -- (2,0);',
            '\\draw (1.25,0.25) -- (1.25,-0.25);']
    preamble = [
            '\\node[anchor=south] (1) at (1,1) {1};',
            '\\node[anchor=north] (2) at (1,-1) {2};',
            '\\draw[line width=0.1cm,color=lightgray] (1,1) -- (1,-1);',
            '\\draw[line width=0.1cm,color=lightgray] (1,0) -- (1.5,0);',
            '\\draw[color=lightgray] (1.5,0) -- (2,0);',
            '\\draw (1.25,0.25) -- (1.25,-0.25);']
    return preamble

def get_t1_tikz_lines():
    preamble = get_preamble_lines()
    extra_labels = [
            '\\node[anchor=north] (3) at (2,-1) {3};',
            '\\node[anchor=north] (4) at (3,-1) {4};',
            '\\node[anchor=south] (5) at (3,1) {5};']
    crossed_lines = []
    crossed_lines.extend(get_tikz_crossed_line((2,0), (0,-1)))
    crossed_lines.extend(get_tikz_crossed_line((2,0), (1,0)))
    crossed_lines.extend(get_tikz_crossed_line((3,0), (0,-1)))
    crossed_lines.extend(get_tikz_crossed_line((3,0), (0,1)))
    return preamble + extra_labels + crossed_lines

def get_t2_tikz_lines():
    preamble = get_preamble_lines()
    extra_labels = [
            '\\node[anchor=north] (4) at (2,-1) {4};',
            '\\node[anchor=north] (3) at (3,-1) {3};',
            '\\node[anchor=south] (5) at (3,1) {5};']
    crossed_lines = []
    crossed_lines.extend(get_tikz_crossed_line((2,0), (0,-1)))
    crossed_lines.extend(get_tikz_crossed_line((2,0), (1,0)))
    crossed_lines.extend(get_tikz_crossed_line((3,0), (0,-1)))
    crossed_lines.extend(get_tikz_crossed_line((3,0), (0,1)))
    return preamble + extra_labels + crossed_lines

def get_t3_tikz_lines():
    preamble = get_preamble_lines()
    extra_labels = [
            '\\node[anchor=north] (5) at (2,-1) {5};',
            '\\node[anchor=north] (3) at (3,-1) {3};',
            '\\node[anchor=south] (4) at (3,1) {4};']
    crossed_lines = []
    crossed_lines.extend(get_tikz_crossed_line((2,0), (0,-1)))
    crossed_lines.extend(get_tikz_crossed_line((2,0), (1,0), True))
    crossed_lines.extend(get_tikz_crossed_line((3,0), (0,-1)))
    crossed_lines.extend(get_tikz_crossed_line((3,0), (0,1)))
    return preamble + extra_labels + crossed_lines

def get_t4_tikz_lines():
    preamble = get_preamble_lines()
    extra_labels = [
            '\\node[anchor=north] (5) at (2,-1) {5};',
            '\\node[anchor=west] (4) at (3,0) {4};',
            '\\node[anchor=south] (3) at (2,1) {3};']
    crossed_lines = []
    crossed_lines.extend(get_tikz_crossed_line((2,0), (0,-1)))
    crossed_lines.extend(get_tikz_crossed_line((2,0), (1,0)))
    crossed_lines.extend(get_tikz_crossed_line((2,0), (0,1)))
    return preamble + extra_labels + crossed_lines

def get_response_content(fs):
    """
    @param fs: a FieldStorage object containing the cgi arguments
    @return: the response
    """
    # get the texts
    tikz_fiedler = get_tikz_text('\n'.join(get_fiedler_tikz_lines()))
    tikz_t1 = get_tikz_text('\n'.join(get_t1_tikz_lines()))
    tikz_t2 = get_tikz_text('\n'.join(get_t2_tikz_lines()))
    tikz_t3 = get_tikz_text('\n'.join(get_t3_tikz_lines()))
    tikz_t4 = get_tikz_text('\n'.join(get_t4_tikz_lines()))
    subfloat_pictures = [tikz_fiedler, tikz_t1, tikz_t2, tikz_t3, tikz_t4]
    tikz_text = '\n'.join(subfloat_pictures)
    figure_lines = get_float_figure_lines(subfloat_pictures)
    latex_text = get_latex_text('\n'.join(figure_lines))
    # decide the output format
    if fs.tikz:
        return tikz_text
    elif fs.tex:
        return latex_text
    elif fs.pdf:
        return tikz.get_pdf_contents(latex_text)
    elif fs.png:
        return tikz.get_png_contents(latex_text)

