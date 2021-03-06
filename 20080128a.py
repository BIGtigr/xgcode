"""Given a newick tree, remove a set of tips.
"""

from SnippetUtil import HandlingError
import Newick
import Util
import Form
import FormOut

def get_form():
    """
    @return: the body of a form
    """
    # define the tree string
    tree_string = '((a:10, b:10)A:3, (c:10, d:10)B:3);'
    # define the form objects
    form_objects = [
            Form.MultiLine('tree', 'newick tree', tree_string),
            Form.MultiLine('names', 'selected taxa', '\n'.join(('c', 'd'))),
            Form.RadioGroup('selection_style', 'selection style', [
                Form.RadioItem('remove', 'remove the selected taxa', True),
                Form.RadioItem('keep', 'keep the selected taxa')])]
    return form_objects

def get_form_out():
    return FormOut.Newick()

def get_response_content(fs):
    # get the tree
    tree = Newick.parse(fs.tree, Newick.NewickTree)
    tree.assert_valid()
    # get the set of names
    selection = Util.get_stripped_lines(fs.names.splitlines())
    selected_name_set = set(selection)
    possible_name_set = set(node.get_name() for node in tree.gen_tips())
    extra_names = selected_name_set - possible_name_set
    if extra_names:
        msg_a = 'the following selected names '
        msg_b = 'are not valid tips: ' + ', '.join(extra_names)
        raise HandlingError(msg_a + msg_b)
    # get the list of tip nodes to remove
    if fs.remove:
        nodes_to_remove = [
                node for node in tree.gen_tips() if node.name in selection]
    elif fs.keep:
        nodes_to_remove = [
                node for node in tree.gen_tips() if node.name not in selection]
    # prune the tree
    for node in nodes_to_remove:
        tree.prune(node)
    # merge segmented branches
    internal_nodes_to_remove = [
            node for node in tree.preorder() if node.get_child_count() == 1]
    for node in internal_nodes_to_remove:
        tree.remove_node(node)
    # return the response
    return tree.get_newick_string() + '\n'
