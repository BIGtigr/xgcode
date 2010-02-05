"""Split a distance matrix, adding a new vertex to each group.

The underlying tree must be bifurcating.
The selected and unselected sets should each have at least two vertices.
This procedure is based on R code by Eric Stone.
"""

from StringIO import StringIO

import numpy

from SnippetUtil import HandlingError
import Util
import MatrixUtil
import NeighborhoodJoining
import Form

def get_form():
    """
    @return: the body of a form
    """
    # define the default distance matrix, the ordered labels, and the selected labels
    D = numpy.array([
            [0, 4, 5, 7],
            [4, 0, 7, 7],
            [5, 7, 0, 10],
            [7, 7, 10, 0]])
    labels = list('abcd')
    selection = list('ac')
    # define the form objects
    form_objects = [
            Form.Matrix('matrix', 'distance matrix', D, MatrixUtil.assert_predistance),
            Form.MultiLine('labels', 'ordered labels', '\n'.join(labels)),
            Form.MultiLine('selection', 'selected labels', '\n'.join(selection))]
    return form_objects

def get_response(fs):
    """
    @param fs: a FieldStorage object containing the cgi arguments
    @return: a (response_headers, response_text) pair
    """
    # read the matrix
    D = fs.matrix
    # read the ordered labels
    ordered_labels = list(Util.stripped_lines(StringIO(fs.labels)))
    # read the set of selected labels
    selected_labels = set(Util.stripped_lines(StringIO(fs.selection)))
    # get the set of selected indices and its complement
    n = len(D)
    selection = set(i for i, label in enumerate(ordered_labels) if label in selected_labels)
    complement = set(range(n)) - selection
    # verify that a minimum number of nodes is in the selection and the complement
    for A in (selection, complement):
        if len(A) < 2:
            raise HandlingError('the selected and unselected sets should each contain at least two vertices')
    # get the new distance matrices
    D_selection, D_complement = NeighborhoodJoining.split_distance_matrix(D.tolist(), selection, complement)
    # start to prepare the reponse
    out = StringIO()
    # show the new distance matrices
    for rows, index_subset, description in ((D_selection, selection, 'first'), (D_complement, complement, 'second')):
        # show the ordered labels of the set
        print >> out, description, 'subtree ordered labels:'
        for i in sorted(index_subset):
            print >> out, ordered_labels[i]
        print >> out, '*'
        print >> out, ''
        # show the distance matrix of the set
        print >> out, description, 'subtree distance matrix:'
        print >> out, MatrixUtil.m_to_string(rows)
        print >> out, ''
    # write the response
    response_headers = [('Content-Type', 'text/plain')]
    return response_headers, out.getvalue().strip()
