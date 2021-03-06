"""Remove root branch length and internal labels from a tree, and unroot it.
"""

from StringIO import StringIO
import os

from SnippetUtil import HandlingError
import Form
import FormOut
import NewickIO
import FelTree
import Newick
import BuildTreeTopology
import const

g_tree_data = const.read('20090802d')


def get_form():
    """
    @return: the body of a form
    """
    # define the formatted tree string
    tree = NewickIO.parse(g_tree_data, Newick.NewickTree) 
    formatted_tree_string = NewickIO.get_narrow_newick_string(tree, 60) 
    # return the form objects
    form_objects = [
            Form.MultiLine('tree', 'newick tree', formatted_tree_string)]
    return form_objects

def get_form_out():
    return FormOut.Newick()

def remove_redundant_nodes(tree):
    """
    @param tree: a NewickTree newick tree
    """
    # find nodes with a branch length of zero
    zero_blen_nodes = [node for node in tree.preorder() if node.blen == 0.0]
    # deal with these nodes appropriately
    for node in zero_blen_nodes:
        if node.blen != 0.0:
            # it is possible that this node no longer has branch length zero
            continue
        elif node.has_children():
            # remove internal nodes with zero branch length
            tree.remove_node(node)
        else:
            # prune terminal nodes with zero branch length
            intersection = tree.prune(node)
            # remove intersection nodes that have a single child
            if intersection.get_child_count() == 1:
                tree.remove_node(intersection)

def get_response_content(fs):
    # read the tree
    tree = NewickIO.parse(fs.tree, Newick.NewickTree) 
    # begin the response
    out = StringIO()
    # remove the branch length associated with the root
    if tree.get_root().blen is not None:
        print >> out, 'the root originally had a branch length of', tree.get_root().blen
        tree.get_root().blen = None
    else:
        print >> out, 'the root did not originally have a branch length'
    # force a trifurcation at the root
    if tree.get_root().get_child_count() < 3:
        print >> out, 'the original root had', tree.get_root().get_child_count(), 'children'
        max_children, best_child = max((child.get_child_count(), child) for child in tree.get_root().gen_children())
        old_root = tree.get_root()
        tree.reroot(best_child)
        tree.remove_node(old_root)
        print >> out, 'the new root has', tree.get_root().get_child_count(), 'children'
    else:
        print >> out, 'the root has', tree.get_root().get_child_count(), 'children'
    # remove names of internal nodes
    nremoved_names = 0
    for node in tree.preorder():
        if node.has_children() and node.name is not None:
            node.name = None
            nremoved_names += 1
    print >> out, 'removed', nremoved_names, 'internal node names'
    # draw the new formatted newick string after a break
    print >> out
    formatted_tree_string = NewickIO.get_narrow_newick_string(tree, 120) 
    print >> out, formatted_tree_string
    # return the response
    return out.getvalue()
