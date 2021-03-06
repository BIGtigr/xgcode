"""Calculate pairwise correlations between rows.
"""

import numpy as np

from SnippetUtil import HandlingError
import SnippetUtil
import Form
import FormOut
import MatrixUtil

def get_form():
    """
    @return: the body of a form
    """
    # define the default data lines
    M = np.array([
            [1, 2, 3],
            [4, 5, 6],
            [1, 0, 1]])
    # define the list of form objects
    form_objects = [
            Form.Matrix('matrix', 'rows of data',
                M),
            Form.Float('epsilon', 'small values will be shown as zero',
                '1e-10', low_inclusive=0)]
    return form_objects

def get_form_out():
    return FormOut.CorrelationMatrix()

def get_response_content(fs):
    """
    @param fs: a FieldStorage object containing the cgi arguments
    @return: a (response_headers, response_text) pair
    """
    # get the matrix of correlation coefficients
    cmat = np.corrcoef(fs.matrix)
    # set values smaller than user-defined epsilon to zero
    # so the output is easy to read
    cmat[abs(cmat) < fs.epsilon] = 0
    # return the response
    return MatrixUtil.m_to_string(cmat) + '\n'
