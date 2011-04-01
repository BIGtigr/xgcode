""" Look for a certificate of non-rejection of a topological alternative.

If the tree topology could not be rejected,
then provide a certificate of non-rejection.
This is a sequence of internal vertex valuation signs
which satisfies certain interlacing criteria.
These criteria are
an interlacing criterion,
sign harmonicity,
and k-cut.
Both trees should have named leaves,
and the set of names should be the same.
The first input tree should have branch lengths.
The second input tree should have named internal vertices.
The following pair of trees should show a difference
in power between the two interlacing conditions.
True tree:
(f:0.591193345089, h:1.57605191914, (e:0.750243005214,
((d:0.496115520823, (c:2.68037788672,
b:0.76093128912):0.324075331796):2.5059101047, (a:1.14799506243,
g:1.45272990456):0.731915700424):0.376369087037):0.392866293805);
Test tree:
(b:0.550310272598, c:1.16962862638, (d:4.75324051473,
(((f:5.88452092355, e:0.608632268794):1.8195499059,
h:0.0997247308189):0.962418679655, (a:0.5662859546,
g:0.87943036548):3.07343504802):1.37087427613):0.652254655969);
"""

from StringIO import StringIO
import unittest
from collections import defaultdict

import Newick
import Form
import FormOut
import Harmonic


def get_form():
    """
    @return: the body of a form
    """
    # define default tree strings
    true_tree_string = '((a:1, b:2):3, (c:4, d:5):6, e:7);'
    test_tree_string = '((a, b)x, (c, e)y, d)z;'
    # define the form objects
    form_objects = [
            Form.MultiLine('true_tree', 'true tree', true_tree_string),
            Form.MultiLine('test_tree', 'test topology', test_tree_string),
            Form.RadioGroup('power_level', 'interlacing condition', [
                Form.RadioItem('power_level_high',
                    'pairwise sign graph connectivity (higher power)', True),
                Form.RadioItem('power_level_low',
                    'principal orthant connectivity (lower power)')])]
    return form_objects

def get_form_out():
    return FormOut.Report()

def get_id_to_adj(tree):
    """
    Newick hackery.
    @param tree: a newick-like tree
    @return: a map from id to adjacent id list
    """
    id_to_adj = defaultdict(list)
    for a, b in tree.gen_bidirected_branches():
        id_to_adj[id(a)].append(id(b))
    return id_to_adj

def get_id_to_name(tree):
    """
    Newick hackery.
    @param tree: a newick-like tree where all nodes are named
    @return: a map from id to name
    """
    return dict((id(x), x.name) for x in tree.preorder())

def get_true_leaf_id_to_test_leaf_id(true_tree, test_tree):
    # Get maps from leaf id to name.
    true_leaf_id_to_name = dict((id(x), x.name) for x in true_tree.gen_tips())
    test_leaf_id_to_name = dict((id(x), x.name) for x in test_tree.gen_tips())
    if len(true_leaf_id_to_name) != len(set(true_leaf_id_to_name.values())):
        raise ValueError('found nonunique leaf names')
    if len(test_leaf_id_to_name) != len(set(test_leaf_id_to_name.values())):
        raise ValueError('found nonunique leaf names')
    true_leaf_name_set = set(true_leaf_id_to_name.values())
    test_leaf_name_set = set(test_leaf_id_to_name.values())
    if true_leaf_name_set != test_leaf_name_set:
        raise ValueError('leaf name mismatch')
    # Get map from name to test tree id.
    name_to_test_leaf_id = dict((b,a) for a, b in test_leaf_id_to_name.items())
    # Get map from true leaf id to test leaf id.
    true_leaf_id_to_test_leaf_id = dict(
            (true_leaf_id, name_to_test_leaf_id[name]) for true_leaf_id,
            name in true_leaf_id_to_name.items())
    return true_leaf_id_to_test_leaf_id

def get_sign_string(arr):
    return ' '.join('+' if x > 0 else '-' for x in arr)

def get_response_content(fs):
    # Read the newick trees.
    true_tree = Newick.parse(fs.true_tree, Newick.NewickTree)
    test_tree = Newick.parse(fs.test_tree, Newick.NewickTree)
    # Get a list of maps from node id to harmonic extension.
    true_tree_leaf_ids = set(id(x) for x in true_tree.gen_tips())
    nleaves = len(true_tree_leaf_ids)
    id_to_full_val_list = [Harmonic.get_harmonic_valuations(
        true_tree, i) for i in range(1, nleaves)]
    id_map =  get_true_leaf_id_to_test_leaf_id(true_tree, test_tree)
    test_id_to_adj = get_id_to_adj(test_tree)
    test_id_to_name = get_id_to_name(test_tree)
    # Get the list of id to val maps with respect to leaf ids of the test tree.
    test_tree_internal_ids = set(id(x) for x in test_tree.gen_internal_nodes())
    test_tree_leaf_ids = set(id(x) for x in test_tree.gen_tips())
    id_to_val_list = []
    for id_to_full_val in id_to_full_val_list:
        d = {}
        for x in true_tree_leaf_ids:
            value = id_to_full_val[x]
            if abs(value) < 1e-8:
                raise ValueError('the true tree is too symmetric')
            elif value < 0:
                s = -1
            else:
                s = 1
            d[id_map[x]] = s
        for x in test_tree_internal_ids:
            d[x] = None
        id_to_val_list.append(d)
    id_to_list_val = {}
    id_to_vals = rec_eigen_strong(
            test_id_to_adj, id_to_val_list, id_to_list_val, 0)
    # Reorder the leaf and the internal node ids according to name order.
    leaf_pair = sorted(
            (test_id_to_name[x], x) for x in test_tree_leaf_ids)
    internal_pair = sorted(
            (test_id_to_name[x], x) for x in test_tree_internal_ids)
    reordered_leaf_ids = zip(*leaf_pair)[1]
    reordered_internal_ids = zip(*internal_pair)[1]
    # Check for a failure to find a certificate.
    if not id_to_vals:
        return 'no non-rejection certificate was found'
    # Start writing the response.
    out = StringIO()
    print >> out, 'leaf sign valuations:'
    for x in reordered_leaf_ids:
        print >> out, test_id_to_name[x], get_sign_string(id_to_vals[x])
    print >> out
    print >> out, 'vertex sign compatible internal vertex valuations:'
    for x in reordered_internal_ids:
        print >> out, test_id_to_name[x], get_sign_string(id_to_vals[x])
    return out.getvalue()

def is_branch_compat(nsame, ndifferent, ntarget, nbranches):
    """
    @param nsame: number of placed edges without sign change
    @param ndifferent: number of placed edges with sign change
    @param ntarget: target number of edges with sign change
    @param nbranches: the total number of branches in the tree.
    """
    if nsame + ndifferent > nbranches:
        raise ValueError('branch sign change error')
    if ndifferent > ntarget:
        return False
    npotential = nbranches - nsame
    if npotential < ntarget:
        return False
    return True

def rec_internal(
        id_to_adj, id_to_val,
        nsame, ndifferent, ntarget, nbranches,
        internals, depth):
    """
    This is a recursive function.
    Each level corresponds to an internal vertex.
    Each time a +1/-1 is assigned to an internal vertex,
    check that the number of sign changes on edges is correct.
    @param id_to_adj: node id to list of ids of adjacent nodes
    @param id_to_val: node id to valuation
    @param nsame: number of placed edges without sign change
    @param ndifferent: number of placed edges with sign change
    @param ntarget: target number of edges with sign change
    @param nbranches: the total number of branches in the tree.
    @param internals: list of ids of internal nodes
    @param depth: recursion depth starts at zero
    """
    idcur = internals[depth]
    for value in (-1, 1):
        # Check the number of edges where the signs
        # change and where the signs stay the same
        # under the proposed valuation for the current internal vertex.
        nsame_next = nsame
        ndifferent_next = ndifferent
        for adj in id_to_adj[idcur]:
            adj_val = id_to_val[adj]
            if adj_val is not None:
                prod = adj_val * value
                if prod == -1:
                    ndifferent_next += 1
                elif prod == 1:
                    nsame_next += 1
                else:
                    raise ValueError('edge sign error')
        # If the target number of edges with sign changes
        # is compatible with the current known edge change status
        # then we are OK.
        if is_branch_compat(nsame_next, ndifferent_next, ntarget, nbranches):
            id_to_val[idcur] = value
            if depth == len(internals) - 1:
                yield dict(id_to_val)
            else:
                for v in rec_internal(
                        id_to_adj, id_to_val,
                        nsame_next, ndifferent_next, ntarget, nbranches,
                        internals, depth+1):
                    yield v
        # Reset the current value to None.
        id_to_val[idcur] = None

def gen_assignments(
        id_to_adj, id_to_val,
        ntarget, nbranches, internals):
    """
    This is the facade for a recursive function.
    """
    # define the parameters for the recursive function
    # create the generator object
    nsame = 0
    ndifferent = 0
    depth = 0
    obj = rec_internal(
            id_to_adj, id_to_val,
            nsame, ndifferent, ntarget, nbranches,
            internals, depth)
    # return the generator object
    return obj

def rec_eigen_weak(id_to_adj, id_to_val_list, id_to_list_val, depth):
    """
    This is a recursive function.
    Each level corresponds to an eigenvector.
    This uses the relatively weak condition of principal orthant connectivity.
    @param id_to_adj: maps an id to a list of adjacent ids
    @param id_to_val_list: a list of k partial valuation maps
    @param id_to_list_val: maps an id to a list of values
    @param depth: zero corresponds to fiedler depth
    @return: None or a valid map
    """
    # Define the set of ids.
    ids = set(id_to_adj)
    # Define the requested number of cut branches at this depth.
    ntarget = depth + 1
    # Get the number of branches in the tree.
    nbranches = sum(len(v) for v in id_to_adj.values()) / 2
    # Get the list of internal ids.
    internals = sorted(get_internal_set(id_to_adj))
    # Consider each assignment at this level that satisfies ntarget.
    for d in gen_assignments(
            id_to_adj, id_to_val_list[depth],
            ntarget, nbranches, internals):
        # Require the assignment to satisfy sign harmonicity.
        if is_sign_harmonic(id_to_adj, d):
            # make the putative next cumulative valuation
            id_to_list_next = {}
            for x in ids:
                v = id_to_list_val.get(x, [])
                id_to_list_next[x] = tuple(list(v) + [d[x]])
            # Require the cumulative assignment to meet orthant connectivity.
            if is_value_connected(id_to_adj, id_to_list_next):
                if depth == len(id_to_val_list) - 1:
                    return id_to_list_next
                else:
                    return rec_eigen_weak(
                            id_to_adj, id_to_val_list, id_to_list_next,
                            depth + 1)

def rec_eigen_strong(id_to_adj, id_to_val_list, id_to_list_val, depth):
    """
    This is a recursive function.
    Each level corresponds to an eigenvector.
    This uses the stronger condition relating sign graphs.
    @param id_to_adj: maps an id to a list of adjacent ids
    @param id_to_val_list: a list of k partial valuation maps
    @param id_to_list_val: maps an id to a list of values
    @param depth: zero corresponds to fiedler depth
    @return: None or a valid map
    """
    # Define the set of ids.
    ids = set(id_to_adj)
    # Define the requested number of cut branches at this depth.
    ntarget = depth + 1
    # Get the number of branches in the tree.
    nbranches = sum(len(v) for v in id_to_adj.values()) / 2
    # Get the list of internal ids.
    internals = sorted(get_internal_set(id_to_adj))
    # Consider each assignment at this level that satisfies ntarget.
    for d in gen_assignments(
            id_to_adj, id_to_val_list[depth],
            ntarget, nbranches, internals):
        # Require the assignment to satisfy sign harmonicity.
        if is_sign_harmonic(id_to_adj, d):
            # make the putative next cumulative valuation
            id_to_list_next = {}
            for x in ids:
                v = id_to_list_val.get(x, [])
                id_to_list_next[x] = tuple(list(v) + [d[x]])
            # Require the cumulative assignment to meet
            # the sequential sign graph connectivity criterion.
            #
            # First get the regions
            # defined by the previous valuation if any.
            if depth:
                d_prev = dict((x, id_to_list_val[x][-1]) for x in ids)
            else:
                d_prev = dict((x, 0) for x in ids)
            id_to_region = get_regions(id_to_adj, d_prev)
            # Get a map from id to (prev_region, current_sign).
            id_to_pair = dict((x, (id_to_region[x], d[x])) for x in ids)
            # Require pair connectivity using this criterion.
            if is_value_connected(id_to_adj, id_to_pair):
                if depth == len(id_to_val_list) - 1:
                    return id_to_list_next
                else:
                    return rec_eigen_strong(
                            id_to_adj, id_to_val_list, id_to_list_next,
                            depth + 1)

def get_internal_set(id_to_adj):
    return set(v for v, d in id_to_adj.items() if len(d) > 1)

def get_leaf_set(id_to_adj):
    return set(v for v, d in id_to_adj.items() if len(d) == 1)

def get_leaf_lists(id_to_adj, id_to_val):
    """
    Find leaf ids with common values.
    @param id_to_adj: maps an id to a list of adjacent ids
    @param id_to_val: maps an id to a value
    @return: a list of lists of leaf ids
    """
    value_to_set = defaultdict(set)
    leaves = get_leaf_set(id_to_adj)
    for leaf in leaves:
        val = id_to_val[leaf]
        value_to_set[val].add(leaf)
    return [list(s) for s in value_to_set.values()]

def is_value_connected(id_to_adj, id_to_val):
    """
    Note that in this case the value can be a tuple of values.
    This function checks that in the tree,
    elements with the same values are connected.
    Note that id_to_adj is assumed to be a tree,
    and the values in id_to_val must be hashable.
    Here are two usage examples.
    The first usage example is to check principal orthant connectivity
    by looking at the tuple of the first k valuations.
    The second usage example is to check a stronger
    connectivity criterion by looking at the pair
    such that the first element is a region index for the kth valuation
    and where the second element is the (k+1)st valuation itself.
    @param id_to_adj: maps an id to a list of adjacent ids
    @param id_to_val: maps an id to a value
    """
    leaf_lists = get_leaf_lists(id_to_adj, id_to_val)
    id_to_region = get_regions(id_to_adj, id_to_val)
    for leaf_list in leaf_lists:
        regions = set(id_to_region[leaf] for leaf in leaf_list)
        if len(regions) > 1:
            return False
    return True

def get_regions(id_to_adj, id_to_val):
    """
    Find connected regions with uniform value.
    Assume a tree topology.
    Each region will get an arbitrary color.
    @param id_to_adj: maps an id to a list of adjacent ids
    @param id_to_val: maps an id to a value
    @return: a map from id to region
    """
    # begin with the min id for determinism for testing
    x = min(id_to_adj)
    id_to_region = {x : 0}
    nregions = 1
    shell = set([x])
    visited = set([x])
    while shell:
        next_shell = set()
        for v in shell:
            v_val = id_to_val[v]
            v_region = id_to_region[v]
            # sort for determinism for testing
            for u in sorted(id_to_adj[v]):
                if u not in visited:
                    u_val = id_to_val[u]
                    if u_val == v_val:
                        id_to_region[u] = v_region
                    else:
                        id_to_region[u] = nregions
                        nregions += 1
                    visited.add(u)
                    next_shell.add(u)
        shell = next_shell
    return id_to_region

def is_sign_harmonic(id_to_adj, id_to_val):
    """
    Sign harmonic will mean that each strong sign graph has a leaf.
    Assume all values are either +1 or -1.
    @param id_to_adj: maps an id to a list of adjacent ids
    @param id_to_val: maps an id to a value
    """
    leaves = get_leaf_set(id_to_adj)
    visited = set(leaves)
    shell = set(leaves)
    while shell:
        next_shell = set()
        for v in shell:
            v_val = id_to_val[v]
            for u in id_to_adj[v]:
                if u not in visited:
                    u_val = id_to_val[u]
                    if u_val == v_val:
                        visited.add(u)
                        next_shell.add(u)
        shell = next_shell
    nvertices = len(id_to_adj)
    nvisited = len(visited)
    return nvertices == nvisited


g_test_id_to_adj = {
        1 : [6],
        2 : [6],
        3 : [8],
        4 : [7],
        5 : [7],
        6 : [1, 2, 8],
        7 : [4, 5, 8],
        8 : [3, 6, 7]}

class TestThis(unittest.TestCase):

    def test_gen_internal_assignments(self):
        id_to_val = {
                1 : 1,
                2 : 1,
                3 : 1,
                4 : 1,
                5 : -1,
                6 : None,
                7 : None,
                8 : None}
        ntarget = 2
        nbranches = 7
        internals = [6, 7, 8]
        # Get the list of observed compatible assignments.
        ds = list(gen_assignments(
                g_test_id_to_adj, id_to_val,
                ntarget, nbranches, internals))
        # Define the only true compatible assignment.
        d = {1: 1, 2: 1, 3: 1, 4: 1, 5: -1, 6: 1, 7: -1, 8: 1}
        # Compare the observed and expected assignments.
        self.assertEqual(len(ds), 1)
        self.assertEqual(ds[0], d)

    def test_sign_harmonic_a(self):
        id_to_val = {
                1:1, 2:1, 3:1, 4:1, 5:1, 6:1, 7:1, 8:1}
        observed = is_sign_harmonic(g_test_id_to_adj, id_to_val)
        expected = True
        self.assertEqual(observed, expected)

    def test_sign_harmonic_b(self):
        id_to_val = {
                1:-1, 2:-1, 3:1, 4:1, 5:1, 6:-1, 7:1, 8:1}
        observed = is_sign_harmonic(g_test_id_to_adj, id_to_val)
        expected = True
        self.assertEqual(observed, expected)

    def test_sign_harmonic_c(self):
        id_to_val = {
                1:1, 2:1, 3:1, 4:1, 5:1, 6:-1, 7:1, 8:-1}
        observed = is_sign_harmonic(g_test_id_to_adj, id_to_val)
        expected = False
        self.assertEqual(observed, expected)

    def test_get_regions_a(self):
        id_to_val = {
                1:1, 2:1, 3:1, 4:1, 5:1, 6:-1, 7:1, 8:-1}
        observed = get_regions(g_test_id_to_adj, id_to_val)
        expected = {1:0, 6:1, 2:2, 8:1, 3:3, 7:4, 5:4, 4:4}
        self.assertEqual(observed, expected)

    def test_get_regions_b(self):
        id_to_val = {
                1:1, 2:1, 3:1, 4:1, 5:1, 6:1, 7:1, 8:1}
        observed = get_regions(g_test_id_to_adj, id_to_val)
        expected = {1:0, 2:0, 3:0, 4:0, 5:0, 6:0, 7:0, 8:0}
        self.assertEqual(observed, expected)

    def test_orthant_connected_a(self):
        id_to_val = {
                1 : (1, 1),
                2 : (1, 1),
                3 : (-1, -1),
                4 : (-1, -1),
                5 : (-1, 1),
                6 : (1, 1),
                7 : (-1, -1),
                8 : (-1, -1)}
        observed = is_value_connected(g_test_id_to_adj, id_to_val)
        expected = True
        self.assertEqual(observed, expected)

    def test_orthant_connected_b(self):
        id_to_val = {
                1 : (1, 1),
                2 : (1, 1),
                3 : (-1, -1),
                4 : (-1, -1),
                5 : (-1, 1),
                6 : (1, 1),
                7 : (-1, 1),
                8 : (-1, -1)}
        observed = is_value_connected(g_test_id_to_adj, id_to_val)
        expected = False
        self.assertEqual(observed, expected)

    def test_rec_eigen_weak_a(self):
        id_to_val_list = [
                {1:1, 2:1, 3:-1, 4:-1, 5:-1, 6:None, 7:None, 8:None},
                {1:1, 2:1, 3:-1, 4:1, 5:1, 6:None, 7:None, 8:None}]
        id_to_list_val = {}
        observed = rec_eigen_weak(
                g_test_id_to_adj, id_to_val_list, id_to_list_val, 0)
        expected = {
                1: (1, 1),
                2: (1, 1),
                3: (-1, -1),
                4: (-1, 1),
                5: (-1, 1),
                6: (1, 1),
                7: (-1, 1),
                8: (-1, -1)}
        self.assertEqual(observed, expected)

    def test_rec_eigen_weak_b(self):
        id_to_val_list = [
                {1:1, 2:1, 3:-1, 4:-1, 5:-1, 6:None, 7:None, 8:None},
                {1:1, 2:1, 3:1, 4:1, 5:-1, 6:None, 7:None, 8:None}]
        id_to_list_val = {}
        observed = rec_eigen_weak(
                g_test_id_to_adj, id_to_val_list, id_to_list_val, 0)
        expected = None
        self.assertEqual(observed, expected)


if __name__ == '__main__':
    unittest.main()
