"""Given a distance matrix, get the difference between two related matrices.

The related matrices are
first the corresponding laplacian matrix and
second the inverse of the covariance matrix
implied by the neighbor joining Q criterion
"""

from StringIO import StringIO

import numpy as np

from SnippetUtil import HandlingError
import MatrixUtil
import Euclid
import Form
import FormOut

def get_form():
    """
    @return: the body of a form
    """
    D = np.array([
            [0, 4.0, 5.0, 7.0],
            [4.0, 0, 7.0, 7.0],
            [5.0, 7.0, 0, 10.0],
            [7.0, 7.0, 10.0, 0]])
    form_objects = [
            Form.Matrix('matrix', 'distance matrix',
                D, MatrixUtil.assert_predistance)]
    return form_objects

def get_form_out():
    return FormOut.Report()

def get_sigma_matrix(D):
    """
    @param D: a distance matrix
    @return: the sigma matrix implied by the neighbor joining Q matrix
    """
    n = len(D)
    # get the list of implied variances
    V = [sum(row) / (n - 2) for row in D]
    # create the sigma matrix
    sigma = np.zeros((n,n))
    for i in range(n):
        for j in range(n):
            sigma[i][j] = (V[i] + V[j] - D[i][j]) / 2
    return sigma

def get_precision_matrix(S):
    """
    @param S: the sigma matrix implied by the neighbor joining Q matrix
    @return: the precision matrix implied by the neighbor joining Q matrix
    """
    return np.linalg.inv(S)

def get_response_content(fs):
    D = fs.matrix
    L = Euclid.edm_to_laplacian(D)
    S = get_sigma_matrix(D)
    P = get_precision_matrix(S)
    # begin the response
    out = StringIO()
    print >> out, 'the Laplacian matrix:'
    print >> out, MatrixUtil.m_to_string(L)
    print >> out
    print >> out, 'the sigma matrix corresponding to the Q matrix:'
    print >> out, MatrixUtil.m_to_string(S)
    print >> out
    print >> out, 'the precision matrix corresponding to the Q matrix:'
    print >> out, MatrixUtil.m_to_string(P)
    print >> out
    print >> out, 'the precision matrix minus the laplacian matrix:'
    print >> out, MatrixUtil.m_to_string(P-L)
    print >> out
    print >> out, 'the double centered precision matrix minus the laplacian matrix:'
    print >> out, MatrixUtil.m_to_string(MatrixUtil.double_centered(P)-L)
    print >> out
    print >> out, 'the pseudo-inverse of the double centered sigma matrix minus the laplacian matrix:'
    print >> out, MatrixUtil.m_to_string(np.linalg.pinv(MatrixUtil.double_centered(S))-L)
    # write the response
    return out.getvalue()
