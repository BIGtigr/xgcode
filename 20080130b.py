"""Given a newick tree, merge segmented branches.
"""

from SnippetUtil import HandlingError
import Newick
import Form
import FormOut

#FIXME use const data

def get_form():
    """
    @return: the body of a form
    """
    # define the tree string
    tree_string = '((((a:5)a:5, (b:5)b:5)A:1.5)A:1.5, (((c:5)c:5, (d:5)d:5)B:1.5)B:1.5);'
    tree = Newick.parse(tree_string, Newick.NewickTree)
    formatted_tree_string = Newick.get_narrow_newick_string(tree, 60)
    # define the form objects
    return [Form.MultiLine('tree', 'newick tree', formatted_tree_string)]

def get_form_out():
    return FormOut.Newick()

def get_response_content(fs):
    # get the tree
    tree = Newick.parse(fs.tree, Newick.NewickTree)
    tree.assert_valid()
    # modify the tree
    segmenting_nodes = [p for p in tree.preorder() if len(p.children) == 1]
    for node in segmenting_nodes:
        tree.remove_node(node)
    # return the response
    return tree.get_newick_string() + '\n'
