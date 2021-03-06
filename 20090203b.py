"""Given a newick tree, calculate the full combinatorial Laplacian matrix.
"""

from StringIO import StringIO
import math

import numpy as np

from SnippetUtil import HandlingError
import Form
import FormOut
import MatrixUtil
import NewickIO
import FelTree
import const

g_default_string = const.read('20100730m')

def get_form():
    """
    @return: a list of form objects
    """
    # define the default tree string
    #ordered_labels = ('a', 'b', 'c', 'x', 'm', 'n', 'p', 'y', 'ab', 'abc', 'mn', 'mnp', 'mnpy', 'abcxmnpy')
    tree = NewickIO.parse(g_default_string, FelTree.NewickTree)
    formatted_tree_string = NewickIO.get_narrow_newick_string(tree, 60)
    # return the form objects
    return [
            Form.MultiLine('tree', 'newick tree with branch lengths',
                formatted_tree_string),
            Form.Integer('precision', 'precision', 4, low=2, high=17)]

def get_form_out():
    return FormOut.Report()

#FIXME replace with np.diag and test
def list_to_diagonal_matrix(arr):
    """
    @param arr: a one dimensional array of numbers
    @return: a two dimensional square matrix of numbers where non-diagonal elements are zero
    """
    n = len(arr)
    D = np.zeros((n,n))
    for i, value in enumerate(arr):
        D[i][i] = value
    return D

def get_response_content(fs):
    # get the tree
    tree = NewickIO.parse(fs.tree, FelTree.NewickTree)
    # define the ordering of the nodes
    ordered_tip_names, ordered_tip_ids = zip(*list(
        (node.get_name(), id(node)) for node in tree.gen_tips()))
    ordered_internal_names, ordered_internal_ids = zip(*list(
        (node.get_name(), id(node)) for node in tree.gen_internal_nodes()))
    ordered_names = ordered_tip_names + ordered_internal_names
    ordered_ids = ordered_tip_ids + ordered_internal_ids
    # get the affinity matrix
    A = np.array(tree.get_affinity_matrix(ordered_ids))
    # get the laplacian
    row_sums = [sum(row) for row in A]
    L = list_to_diagonal_matrix(row_sums) - A.copy()
    # write the text
    out = StringIO()
    print >> out, 'Laplacian:'
    print >> out, MatrixUtil.m_to_string(L, precision=fs.precision)
    print >> out
    print >> out, 'ordered node labels:'
    print >> out, '\n'.join(ordered_names)
    # write the response
    return out.getvalue()
