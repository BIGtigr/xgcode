"""Do a MAPP analysis. [UNFINISHED]
"""

from StringIO import StringIO
import string

import argparse

from SnippetUtil import HandlingError
import Form
import Util
import FelTree
import Newick
import NewickIO
import MatrixUtil
import HtmlTable
import MAPP
import Codon
import LeafWeights

g_ordered_taxon_names = [
        'hg18',
        'rheMac2',
        'mm9',
        'canFam2',
        'loxAfr2',
        'monDom4',
        'ornAna1',
        'galGal3',
        'anoCar1',
        'xenTro2',
        'gasAcu1']

g_unordered_taxon_names = set(g_ordered_taxon_names)


def get_reverse_complement(s):
    trans = {
            'A' : 'T',
            'T' : 'A',
            'C' : 'G',
            'G' : 'C'}
    return ''.join(trans[nt] for nt in reversed(s))

def lines_to_annotated_snps(lines):
    """
    Yield Snp objects.
    @param lines: raw lines
    """
    for clump in gen_clumped_lines(lines):
        yield Snp(clump)

def gen_clumped_lines(lines):
    """
    Yield clumps of contiguous lines with no intervening blank lines.
    Also comment lines are removed.
    @param lines: raw lines
    """
    clump = []
    for line in lines:
        line = line.strip()
        if line.startswith('#'):
            continue
        if line:
            clump.append(line)
        elif clump:
            yield clump
            clump = []
    if clump:
        yield clump


class SnpError(Exception): pass

class Snp(object):

    def __init__(self, lines):
        # check the number of lines
        if len(lines) != 4:
            msg_a = 'expected 4 lines per annotated SNP '
            msg_b = 'but found %d' % len(lines)
            raise SnpError(msg_a + msg_b)
        # unpack the lines into member variables
        self.parse_first_line(lines[0])
        self.codon = lines[1].upper()
        self.within_codon_pos = int(lines[2])
        self.column = [x.upper() if x.isalpha() else None for x in lines[3]]
        # do some basic validation
        if not self.column[0]:
            msg = 'expected an aligned human amino acid for each SNP'
            raise SnpError(msg)
        if self.codon not in Codon.g_non_stop_codons:
            msg = 'expected a codon but found ' + self.codon
            raise SnpError(msg)
        if self.within_codon_pos not in (1, 2, 3):
            msg_a = 'expected the within-codon position '
            msg_b = 'to be either 1, 2, or 3, '
            msg_c = 'but found %d' % self.within_codon_pos
            raise SnpError(msg_a + msg_b + msg_c)
        # Assert that the major allele is actually in the codon
        # at the correct position, taking into account strand orientation.
        expected_nt = self.major_allele
        if self.orientation == '+':
            codon = self.codon
            observed_nt = codon[self.within_codon_pos - 1]
        else:
            codon = get_reverse_complement(self.codon)
            observed_nt = codon[2 - (self.within_codon_pos - 1)]
        if expected_nt != observed_nt:
            raise SnpError(
                    'the major allele is not in the codon '
                    'at the correct position '
                    'even after taking into account the strand orientation.')
        # Assert that the human amino acid,
        # the first amino acid in the column,
        # is equal to the translation of the codon
        # taking into account the strand orientation.
        if self.orientation == '+':
            codon = self.codon
        else:
            codon = get_reverse_complement(self.codon)
        expected_aa = self.column[0]
        observed_aa = Codon.g_codon_to_aa_letter[codon]
        if expected_aa != observed_aa:
            raise SnpError(
                    'the oriented codon does not translate to '
                    'the human amino acid in the aligned column')
        # Get the mutant amino acid.
        if self.orientation == '+':
            c = list(self.codon)
            c[self.within_codon_pos - 1] = self.minor_allele
        else:
            c = list(get_reverse_complement(self.codon))
            c[2 - (self.within_codon_pos - 1)] = self.minor_allele
        codon = ''.join(c)
        self.mutant_aa = Codon.g_codon_to_aa_letter[codon]

    def parse_first_line(self, line):
        """
        @param line: a line of comma separated values
        """
        # break the line into unquoted elements
        ignore = string.whitespace + '"'
        v = [x.strip(ignore) for x in line.split(',')]
        # check the number of elements on the line
        if len(v) != 8:
            msg_a = 'expected 8 elements on the first line '
            msg_b = 'but found %d' % len(v)
            raise SnpError(msg_a + msg_b)
        # unpack the elements into member variables
        self.variant_id = v[0]
        self.chromosome_name = v[1]
        self.position = int(v[2])
        self.gene_id = v[3]
        self.gene_name = v[4]
        self.major_allele = v[5].upper()
        self.minor_allele = v[6].upper()
        self.orientation = v[7]
        # do some basic validation
        if self.major_allele not in 'ACGT':
            msg = 'major allele is invalid nucleotide: ' + self.major_allele
            raise SnpError(msg)
        if self.minor_allele not in 'ACGT':
            msg = 'minor allele is invalid nucleotide: ' + self.minor_allele
            raise SnpError(msg)
        if self.orientation not in '+-':
            msg_a = 'expected the orientation to be + or - '
            msg_b = 'but found ' + self.orientation
            raise SnpError(msg_a + msg_b)

    def get_pruned_tree(self, tree_string):
        all_taxon_aa_pairs = zip(g_ordered_taxon_names, snp.column)
        # get the newick tree.
        tree = NewickIO.parse(fs.tree, Newick.NewickTree)
        # define the taxa that will be pruned
        unordered_tip_names = set(node.name for node in tree.gen_tips())
        names_to_remove = unordered_tip_names - observed_taxon_names
        # prune the tree
        for name in names_to_remove:
            tree.prune(tree.get_unique_node(name))
        # merge segmented branches 
        internal_nodes_to_remove = [node for node in tree.preorder()
                if node.get_child_count() == 1] 
        for node in internal_nodes_to_remove: 
            tree.remove_node(node) 



def get_form():
    """
    @return: the body of a form
    """
    # define the default tree
    with open('const-data/20100526b.dat') as fin:
        tree_string = fin.read()
    default_tree = NewickIO.parse(tree_string, FelTree.NewickTree)
    default_tree_string = NewickIO.get_narrow_newick_string(default_tree, 60)
    # define the default annotation string
    with open('const-data/20100526a.dat') as fin:
        default_annotation_string = fin.read()
    # define the list of form objects
    form_objects = [
            Form.MultiLine('tree', 'tree',
                default_tree_string),
            Form.MultiLine('annotation', 'SNP annotations',
                default_annotation_string)]
    return form_objects

def aa_letter_to_aa_index(aa_letter):
    """
    @param aa_letter: an amino acid letter
    @return: None or an index between 0 and 19
    """
    for i, aa in enumerate(Codon.g_aa_letters):
        if aa == aa_letter:
            return i
    return None

def get_tree_and_column(fs):
    """
    @param fs: a FieldStorage object decorated with field values
    @return: the pruned tree and a map from taxa to amino acids
    """
    # get the newick tree.
    tree = NewickIO.parse(fs.tree, Newick.NewickTree)
    unordered_tip_names = set(node.name for node in tree.gen_tips())
    # get the lines that give an amino acid for each of several taxa
    column_lines = Util.get_stripped_lines(StringIO(fs.column))
    if len(column_lines) < 7:
        msg = 'the alignment column should have at least seven taxa'
        raise HandlingError(msg)
    # get the mapping from taxon to amino acid
    taxon_to_aa_letter = {}
    for line in column_lines:
        pair = line.split()
        if len(pair) != 2:
            raise HandlingError('invalid line: %s' % line)
        taxon, aa_letter = pair
        aa_letter = aa_letter.upper()
        if aa_letter not in Codon.g_aa_letters:
            msg = 'expected an amino acid instead of this: %s' % aa_letter
            raise HandlingError(msg)
        taxon_to_aa_letter[taxon] = aa_letter
    # Assert that the names in the column are a subset of the names
    # of the tips of the tree.
    unordered_taxon_names = set(taxon_to_aa_letter)
    weird_names = unordered_taxon_names - unordered_tip_names
    if weird_names:
        msg = 'these taxa were not found on the tree: %s' % str(weird_names)
        raise HandlingError(msg)
    # define the taxa that will be pruned
    names_to_remove = unordered_tip_names - unordered_taxon_names
    # prune the tree
    for name in names_to_remove:
        tree.prune(tree.get_unique_node(name))
    # merge segmented branches 
    internal_nodes_to_remove = [node for node in tree.preorder()
            if node.get_child_count() == 1] 
    for node in internal_nodes_to_remove: 
        tree.remove_node(node) 
    return tree, taxon_to_aa_letter

def process_obsolete():
    print >> out, '<html>'
    print >> out, '<body>'
    # get the tree and the column sent by the user
    pruned_tree, taxon_to_aa_letter = get_tree_and_column(fs)
    # get the weights of the taxa
    taxon_weight_pairs = LeafWeights.get_stone_weights(pruned_tree)
    # calculate the standardized physicochemical property table
    standardized_property_array = MAPP.get_standardized_property_array(
            MAPP.g_property_array)
    # calculate the physicochemical property correlation matrix
    correlation_matrix = MAPP.get_property_correlation_matrix(
            standardized_property_array)
    # estimate the amino acid distribution for the column,
    # taking into account the tree and a uniform prior.
    weights = []
    aa_indices = []
    for taxon, weight in taxon_weight_pairs:
        weights.append(weight)
        aa_indices.append(aa_letter_to_aa_index(taxon_to_aa_letter[taxon]))
    aa_distribution = MAPP.estimate_aa_distribution(weights, aa_indices)
    # estimate the mean and variance of each physicochemical property
    est_pc_means = MAPP.estimate_property_means(
            standardized_property_array, aa_distribution)
    est_pc_variances = MAPP.estimate_property_variances(
            standardized_property_array, aa_distribution)
    # calculate the deviation from each property mean
    # for each possible amino acid
    deviations = MAPP.get_deviations(
            est_pc_means, est_pc_variances, standardized_property_array)
    # calculate the impact scores
    impact_scores = MAPP.get_impact_scores(correlation_matrix, deviations)
    # show the impact scores
    table = [impact_scores]
    row_labels = ['impact']
    col_labels = Codon.g_aa_letters
    print >> out, 'impact scores:'
    print >> out, '<br/>'
    print >> out, HtmlTable.get_labeled_table_string(
            col_labels, row_labels, table)
    print >> out, '<br/><br/>'
    # calculate the p-values
    p_values = []
    for score in impact_scores:
        ntaxa = len(taxon_weight_pairs)
        p_values.append(MAPP.get_p_value(score, ntaxa))
    # show the p-values
    table = [p_values]
    row_labels = ['p-value']
    col_labels = Codon.g_aa_letters
    print >> out, 'p-values:'
    print >> out, '<br/>'
    print >> out, HtmlTable.get_labeled_table_string(
            col_labels, row_labels, table)
    print >> out, '<br/><br/>'
    # write the html footer
    print >> out, '</body>'
    print >> out, '</html>'
    # write the response
    response_headers = [('Content-Type', 'text/html')]
    return response_headers, out.getvalue()

def get_pruned_tree(snp, full_tree_string):
    all_taxon_aa_pairs = zip(g_ordered_taxon_names, snp.column)
    # get the newick tree.
    tree = NewickIO.parse(fs.tree, Newick.NewickTree)
    # define the taxa that will be pruned
    unordered_tip_names = set(node.name for node in tree.gen_tips())
    names_to_remove = unordered_tip_names - observed_taxon_names
    # prune the tree
    for name in names_to_remove:
        tree.prune(tree.get_unique_node(name))
    # merge segmented branches 
    internal_nodes_to_remove = [node for node in tree.preorder()
            if node.get_child_count() == 1] 
    for node in internal_nodes_to_remove: 
        tree.remove_node(node) 

def process_snp(snp, full_tree_string):

    # define the map from the taxon to the amino acid
    all_taxon_aa_pairs = zip(g_ordered_taxon_names, snp.column)
    taxon_to_aa_letter = dict((t, aa) for t, aa in taxon_aa_pairs if aa)
    # get the weights of the taxa
    taxon_weight_pairs = LeafWeights.get_stone_weights(pruned_tree)
    # calculate the standardized physicochemical property table
    standardized_property_array = MAPP.get_standardized_property_array(
            MAPP.g_property_array)
    # calculate the physicochemical property correlation matrix
    correlation_matrix = MAPP.get_property_correlation_matrix(
            standardized_property_array)
    # estimate the amino acid distribution for the column,
    # taking into account the tree and a uniform prior.
    weights = []
    aa_indices = []
    for taxon, weight in taxon_weight_pairs:
        weights.append(weight)
        aa_indices.append(aa_letter_to_aa_index(taxon_to_aa_letter[taxon]))
    aa_distribution = MAPP.estimate_aa_distribution(weights, aa_indices)
    # estimate the mean and variance of each physicochemical property
    est_pc_means = MAPP.estimate_property_means(
            standardized_property_array, aa_distribution)
    est_pc_variances = MAPP.estimate_property_variances(
            standardized_property_array, aa_distribution)
    # calculate the deviation from each property mean
    # for each possible amino acid
    deviations = MAPP.get_deviations(
            est_pc_means, est_pc_variances, standardized_property_array)
    # calculate the impact scores
    impact_scores = MAPP.get_impact_scores(correlation_matrix, deviations)
    # show the impact scores
    table = [impact_scores]
    row_labels = ['impact']
    col_labels = Codon.g_aa_letters
    print >> out, 'impact scores:'
    print >> out, '<br/>'
    print >> out, HtmlTable.get_labeled_table_string(
            col_labels, row_labels, table)
    print >> out, '<br/><br/>'
    # calculate the p-values
    p_values = []
    for score in impact_scores:
        ntaxa = len(taxon_weight_pairs)
        p_values.append(MAPP.get_p_value(score, ntaxa))
    # show the p-values
    table = [p_values]
    row_labels = ['p-value']
    col_labels = Codon.g_aa_letters
    print >> out, 'p-values:'
    print >> out, '<br/>'
    print >> out, HtmlTable.get_labeled_table_string(
            col_labels, row_labels, table)
    print >> out, '<br/><br/>'

def get_response(fs):
    """
    @param fs: a FieldStorage object decorated with field values
    @return: a (response_headers, response_text) pair
    """
    # start writing the html response
    out = StringIO()
    # get the list of annotated snps
    snps = list(lines_to_annotated_snps(StringIO(fs.annotation)))
    # write a line for each snp
    for snp in snps:
        print >> out, process_snp(snp, fs.tree)
    # return the response
    response_headers = [('Content-Type', 'text/plain')]
    return response_headers, out.getvalue().rstrip()

def main(args):
    pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    main(args)
