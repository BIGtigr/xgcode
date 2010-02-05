"""Calculate the determinants of some matrices derived from a matrix.

The derived matrices are Schur complements and sub-matrices.
For the applications of interest the input matrix should be a Laplacian.
"""

from StringIO import StringIO

import numpy

from SnippetUtil import HandlingError
import MatrixUtil
import Form

def get_form():
    """
    @return: the body of a form
    """
    M = numpy.array([
            [1.0, 0.0, 0.0, 0.0, -1.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, -1.0, 0.0],
            [0.0, 0.0, 1.0, 0.0, 0.0, -1.0],
            [0.0, 0.0, 0.0, 1.0, 0.0, -1.0],
            [-1.0, -1.0, 0.0, 0.0, 3.0, -1.0],
            [0.0, 0.0, -1.0, -1.0, -1.0, 3.0]])
    # define the form objects
    form_objects = [
            Form.Matrix('matrix', 'a square matrix', M, MatrixUtil.assert_square),
            Form.Integer('nw_size', 'number of rows in the square northwest block', 4, low=1),
            Form.Integer('index_a', 'the zero based index of the first vertex in the northwest block', 0, low=0),
            Form.Integer('index_b', 'the zero based index of the second vertex in the northwest block', 2, low=0)]
    return form_objects

def get_deleted_matrix(M, row_indices, column_indices):
    """
    @param M: a numpy array
    @param row_indices: the indices of the rows to delete
    @param column_indices: the indices of the columns to delete
    """
    nrows, ncols = M.shape
    D = []
    for i in range(nrows):
        row = []
        for j in range(ncols):
            if j not in column_indices:
                row.append(M[i][j])
        if i not in row_indices:
            D.append(row)
    return numpy.array(D)

def get_response(fs):
    """
    @param fs: a FieldStorage object containing the cgi arguments
    @return: a (response_headers, response_text) pair
    """
    # read the matrix
    M = fs.matrix
    n = len(M)
    # validate the input interactions
    if fs.nw_size >= n:
        raise HandlingError('the number of rows in the northwest block must be less than the number of rows in the matrix')
    if fs.index_a >= fs.nw_size:
        raise HandlingError('the first index must be less than the number of rows in the northwest block')
    if fs.index_b >= fs.nw_size:
        raise HandlingError('the second index must be less than the number of rows in the northwest block')
    # partition the matrix
    a = fs.nw_size
    c = n - fs.nw_size
    A = numpy.zeros((a,a))
    for i in range(a):
        for j in range(a):
            A[i][j] = M[i][j]
    B = numpy.zeros((a,c))
    for i in range(a):
        for j in range(c):
            B[i][j] = M[i][a+j]
    C = numpy.zeros((c,c))
    for i in range(c):
        for j in range(c):
            C[i][j] = M[a+i][a+j]
    D = numpy.zeros((c,a))
    for i in range(c):
        for j in range(a):
            D[i][j] = M[a+i][j]
    # get the derived matrices
    i, j = fs.index_a, fs.index_b
    S = A - numpy.dot(B, numpy.dot(numpy.linalg.inv(C), D))
    S_deleted = get_deleted_matrix(S, [i,j], [i,j])
    M_deleted = get_deleted_matrix(M, [i,j], [i,j])
    # define the ordered matrix names and the correspondingly ordered matrices
    names = ('M', 'M with deletion', 'the Schur complement of C in M', 'the Schur complement with deletion', 'C')
    matrices = (M, M_deleted, S, S_deleted, C)
    # define the response
    out = StringIO()
    for name, matrix in zip(names, matrices):
        print >> out, ('%s:' % name)
        print >> out, MatrixUtil.m_to_string(matrix)
        print >> out, ('determinant of %s:' % name), numpy.linalg.det(matrix)
        print >> out
    # write the response
    response_headers = [('Content-Type', 'text/plain')]
    return response_headers, out.getvalue().strip()
