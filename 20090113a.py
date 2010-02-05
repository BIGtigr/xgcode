"""Calculate the MAPP score for an amino acid of interest at a genomic position.
"""

from StringIO import StringIO
import sys
import os

from SnippetUtil import HandlingError
import KGEA
import Form
import Codon
import MAPP
import LeafWeights
import NewickIO
import Newick
import FelTree

# define some web locations that should probably be moved to a config file somewhere
g_base_dir = '/var/www/python_scripts/data/exon-alignments'
g_fasta_dir = g_base_dir + '/fasta-pieces'
g_index_dir = g_base_dir + '/piece-index-files'
g_valid_chromosome_strings_pathname = g_base_dir + '/valid-chromosome-strings.txt'


def get_form():
    """
    @return: the body of a form
    """
    # define the default tree
    # http://hgdownload.cse.ucsc.edu/goldenPath/hg18/phastCons28way/28way.mod
    default_tree_lines = [
            '((((((((((((hg18:0.005873,panTro2:0.007668):0.026074,rheMac2:0.031973):0.073300,',
            'otoGar1:0.151185):0.015682,tupBel1:0.162844):0.006272,(((rn4:0.084383,',
            'mm8:0.076274):0.200607,cavPor2:0.202990):0.034350,oryCun1:0.208548):0.014587):0.019763,',
            '((sorAra1:0.248532,eriEur1:0.222255):0.045693,(((canFam2:0.101137,felCat3:0.098203):0.048213,',
            'equCab1:0.099323):0.007287,bosTau3:0.163945):0.012398):0.018928):0.030081,(dasNov1:0.133274,',
            '(loxAfr1:0.103030,echTel1:0.232706):0.049511):0.008424):0.213469,monDom4:0.320721):0.088647,',
            'ornAna1:0.488110):0.118797,(galGal3:0.395136,anoCar1:0.513962):0.093688):0.151358,xenTro2:0.778272):0.174596,',
            '(((tetNig1:0.203933,fr2:0.239587):0.203949,(gasAcu1:0.314162,oryLat1:0.501915):0.055354):0.346008,',
            'danRer4:0.730028):0.174596);']
    tree_string = '\n'.join(default_tree_lines)
    default_tree = NewickIO.parse(tree_string, FelTree.NewickTree)
    default_tree_string = NewickIO.get_narrow_newick_string(default_tree, 60)
    # define the list of form objects
    form_objects = [
            Form.MultiLine('tree', 'newick tree', default_tree_string),
            Form.SingleLine('chromosome', 'chromosome', 'chr17'),
            Form.Integer('position', 'position', 70360012, low=0),
            Form.SingleLine('aminoacid', 'the amino acid of interest', 'P')]
    return form_objects


def modify_tree(tree, selected_taxa):
    """
    Modify the tree by removing all taxa that are not selected.
    @param tree: a tree that will be modified by pruning
    @param selected_taxa: the set of selected taxa to keep
    """
    # get the set of names of the tips of the tree
    taxon_names = set(node.name for node in tree.gen_tips())
    # assert that each taxon in the alignment was found in the tree
    bad_taxa = selected_taxa - taxon_names
    if bad_taxa:
        s = ', '.join(bad_taxa)
        raise HandlingError('these taxa were found in the alignment but not in the tree: ' + s)
    # define the taxa that will be pruned
    taxa_to_remove = taxon_names - selected_taxa
    # prune the tree
    for taxon in taxa_to_remove:
        tree.prune(tree.get_unique_node(taxon))
    # merge segmented branches 
    internal_nodes_to_remove = [node for node in tree.preorder() if node.get_child_count() == 1] 
    for node in internal_nodes_to_remove: 
        tree.remove_node(node) 

def aa_letter_to_aa_index(aa_letter):
    """
    @param aa_letter: an amino acid letter
    @return: None or an index between 0 and 19
    """
    for i, aa in enumerate(Codon.g_aa_letters):
        if aa == aa_letter:
            return i
    return None

def get_response(fs):
    """
    @param fs: a FieldStorage object decorated with field values
    @return: a (response_headers, response_text) pair
    """
    # get the upper case amino acid letter
    aa_of_interest = fs.aminoacid.upper()
    if aa_of_interest not in Codon.g_aa_letters:
        raise HandlingError('invalid amino acid: ' + fs.aminoacid)
    # get the newick tree
    tree = NewickIO.parse(fs.tree, Newick.NewickTree)
    # get the alignment
    out = StringIO()
    try:
        finder = KGEA.Finder(g_index_dir, g_valid_chromosome_strings_pathname, g_fasta_dir)
        # note that some of these amino acids can be gaps
        taxon_aa_pairs = list(finder.gen_taxon_aa_pairs(fs.chromosome, fs.position))
        lines = [taxon + '\t' + aa for taxon, aa in taxon_aa_pairs]
        if taxon_aa_pairs:
            # get the map from the taxon to the amino acid
            taxon_to_aa_letter = dict((taxon, aa) for taxon, aa in taxon_aa_pairs if aa in Codon.g_aa_letters)
            selected_taxa = set(taxon_to_aa_letter)
            ntaxa = len(selected_taxa)
            # assert that we have enough taxa to calculate the p-value from the MAPP statistic
            mintaxa = 7
            if ntaxa < mintaxa:
                raise HandlingError('this column has only %d aligned amino acids but we want at least %d' % (ntaxa, mintaxa))
            # modify the tree so that we keep only the taxa of interest
            modify_tree(tree, selected_taxa)
            # get the taxon weights from the tree
            taxon_weight_pairs = LeafWeights.get_stone_weights(tree)
            # calculate the standardized physicochemical property table
            standardized_property_array = MAPP.get_standardized_property_array(MAPP.g_property_array)
            # calculate the physicochemical property correlation matrix
            correlation_matrix = MAPP.get_property_correlation_matrix(standardized_property_array)
            # estimate the amino acid distribution for the column
            weights = []
            aa_indices = []
            for taxon, weight in taxon_weight_pairs:
                weights.append(weight)
                aa_indices.append(aa_letter_to_aa_index(taxon_to_aa_letter[taxon]))
            aa_distribution = MAPP.estimate_aa_distribution(weights, aa_indices)
            # estimate the mean and variance of each physicochemical property
            est_pc_means = MAPP.estimate_property_means(standardized_property_array, aa_distribution)
            est_pc_variances = MAPP.estimate_property_variances(standardized_property_array, aa_distribution)
            # calculate the deviation from each property mean for each possible amino acid
            deviations = MAPP.get_deviations(est_pc_means, est_pc_variances, standardized_property_array)
            # calculate the impact scores
            impact_scores = MAPP.get_impact_scores(correlation_matrix, deviations)
            # calculate the p-values
            p_values = [MAPP.get_p_value(score, ntaxa) for score in impact_scores]
            # show the p-value of the amino acid of interest
            print >> out, 'MAPP p-value:'
            print >> out, p_values[aa_letter_to_aa_index(aa_of_interest)]
            print >> out
            # show the MAPP statistic of the amino acid of interest
            print >> out, 'MAPP statistic:'
            print >> out, impact_scores[aa_letter_to_aa_index(aa_of_interest)]
            print >> out
            # show the aligned column
            print >> out, 'aligned column:'
            print >> out, '\n'.join(lines)
        else:
            print >> out, 'no aligned amino acids were found at this position'
    except KGEA.KGEAError, e:
        print >> out, e
    response_headers = [('Content-Type', 'text/plain')]
    return response_headers, out.getvalue()



