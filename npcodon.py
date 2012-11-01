"""
This is for using numpy with codon models.
"""

from itertools import product

import numpy
from numpy import testing


# http://en.wikipedia.org/wiki/Stop_codon
g_stop = {'tag', 'taa', 'tga'}

# http://en.wikipedia.org/wiki/Human_mitochondrial_genetics
g_stop_mito = {'tag', 'taa', 'aga', 'agg'}

# http://en.wikipedia.org/wiki/File:Transitions-transversions-v3.png
g_ts = {'ag', 'ga', 'ct', 'tc'}
g_tv = {'ac', 'ca', 'gt', 'tg', 'at', 'ta', 'cg', 'gc'}

# http://en.wikipedia.org/wiki/DNA_codon_table
g_code = {
        ('gct', 'gcc', 'gca', 'gcg'),
        ('cgt', 'cgc', 'cga', 'cgg', 'aga', 'agg'),
        ('aat', 'aac'),
        ('gat', 'gac'),
        ('tgt', 'tgc'),
        ('caa', 'cag'),
        ('gaa', 'gag'),
        ('ggt', 'ggc', 'gga', 'ggg'),
        ('cat', 'cac'),
        ('att', 'atc', 'ata'),
        ('tta', 'ttg', 'ctt', 'ctc', 'cta', 'ctg'),
        ('aaa', 'aag'),
        ('atg',),
        ('ttt', 'ttc'),
        ('cct', 'ccc', 'cca', 'ccg'),
        ('tct', 'tcc', 'tca', 'tcg', 'agt', 'agc'),
        ('act', 'acc', 'aca', 'acg'),
        ('tgg',),
        ('tat', 'tac'),
        ('gtt', 'gtc', 'gta', 'gtg'),
        ('taa', 'tga', 'tag'),
        }

# http://en.wikipedia.org/wiki/Human_mitochondrial_genetics
g_code_mito = {
        ('gct', 'gcc', 'gca', 'gcg'),
        ('cgt', 'cgc', 'cga', 'cgg'),
        ('aat', 'aac'),
        ('gat', 'gac'),
        ('tgt', 'tgc'),
        ('caa', 'cag'),
        ('gaa', 'gag'),
        ('ggt', 'ggc', 'gga', 'ggg'),
        ('cat', 'cac'),
        ('att', 'atc'),
        ('tta', 'ttg', 'ctt', 'ctc', 'cta', 'ctg'),
        ('aaa', 'aag'),
        ('atg', 'ata'),
        ('ttt', 'ttc'),
        ('cct', 'ccc', 'cca', 'ccg'),
        ('tct', 'tcc', 'tca', 'tcg', 'agt', 'agc'),
        ('act', 'acc', 'aca', 'acg'),
        ('tgg', 'tga'),
        ('tat', 'tac'),
        ('gtt', 'gtc', 'gta', 'gtg'),
        ('tag', 'taa', 'aga', 'agg'),
        }


def enum_codons(stop):
    """
    Enumerate lower case codon strings with all stop codons at the end.
    @return: a list of 64 codons
    """
    codons = [''.join(triple) for triple in product('acgt', repeat=3)]
    return sorted(set(codons) - set(stop)) + sorted(stop)

def get_hamming(codons):
    """
    Get the hamming distance between codons, in {0, 1, 2, 3}.
    @param codons: sequence of lower case codon strings
    @return: matrix of hamming distances
    """
    ncodons = len(codons)
    ham = numpy.zeros((ncodons, ncodons), dtype=int)
    for i, ci in enumerate(codons):
        for j, cj in enumerate(codons):
            ham[i, j] = sum(1 for a, b in zip(ci, cj) if a != b)
    return ham

def get_ts_tv(codons):
    """
    Get binary matrices defining codon pairs differing by single changes.
    @param codons: sequence of lower case codon strings
    @return: two binary numpy arrays
    """
    ncodons = len(codons)
    ts = numpy.zeros((ncodons, ncodons), dtype=int)
    tv = numpy.zeros((ncodons, ncodons), dtype=int)
    for i, ci in enumerate(codons):
        for j, cj in enumerate(codons):
            nts = sum(1 for p in zip(ci,cj) if ''.join(p) in g_ts)
            ntv = sum(1 for p in zip(ci,cj) if ''.join(p) in g_tv)
            if nts == 1 and ntv == 0:
                ts[i, j] = 1
            if nts == 0 and ntv == 1:
                tv[i, j] = 1
    return ts, tv

def get_syn_nonsyn(code, codons):
    """
    Get binary matrices defining synonymous or nonynonymous codon pairs.
    @return: two binary matrices
    """
    ncodons = len(codons)
    inverse_table = dict((c, i) for i, cs in enumerate(code) for c in cs)
    syn = numpy.zeros((ncodons, ncodons), dtype=int)
    for i, ci in enumerate(codons):
        for j, cj in enumerate(codons):
            if inverse_table[ci] == inverse_table[cj]:
                syn[i, j] = 1
    return syn, 1-syn

def get_compo(codons):
    """
    Get a matrix defining site-independent nucleotide composition of codons.
    @return: integer matrix
    """
    ncodons = len(codons)
    compo = numpy.zeros((ncodons, 4), dtype=int)
    for i, c in enumerate(codons):
        for j, nt in enumerate('acgt'):
            compo[i, j] = c.count(nt)
    return compo

def get_asym_compo(codons):
    """
    This is an ugly function.
    Its purpose is to help determine which is the mutant nucleotide type
    given an ordered pair of background and mutant codons.
    This determination is necessary if we want to follow
    the mutation model of Yang and Nielsen 2008.
    Entry [i, j, k] of the returned matrix gives the number of positions
    for which the nucleotides are different between codons i and j and
    the nucleotide type of codon j is 'acgt'[k].
    @return: a three dimensional matrix
    """
    ncodons = len(codons)
    asym_compo = numpy.zeros((ncodons, ncodons, 4), dtype=int)
    for i, ci in enumerate(codons):
        for j, cj in enumerate(codons):
            for k, nt in enumerate('acgt'):
                asym_compo[i, j, k] = sum(1 for a, b in zip(ci, cj) if (
                    a != b and b == nt))
    return asym_compo


class Test_NumpyCodons(testing.TestCase):

    def _help_test_invariants(self, code, stop):
        all_codons = enum_codons(stop)
        codons = all_codons[:-len(stop)]
        ts, tv = get_ts_tv(codons)
        syn, nonsyn = get_syn_nonsyn(code, codons)
        compo = get_compo(codons)
        asym_compo = get_asym_compo(codons)
        ham = get_hamming(codons)
        # check some invariants
        testing.assert_equal(len(all_codons), 64)
        testing.assert_equal(len(codons), 64 - len(stop))
        testing.assert_equal(numpy.unique(ts), [0, 1])
        testing.assert_equal(numpy.unique(tv), [0, 1])
        # check the genetic code for typos
        table_codons = list(c for cs in code for c in cs)
        testing.assert_equal(len(code), 21)
        testing.assert_equal(len(table_codons), len(set(table_codons)))
        if set(codons) - set(table_codons):
            raise Exception(set(all_codons) - set(table_codons))
        if set(table_codons) - set(all_codons):
            raise Exception(set(table_codons) - set(all_codons))

    def test_mito_invariants(self):
        self._help_test_invariants(g_code_mito, g_stop_mito)

    def test_plain_invariants(self):
        self._help_test_invariants(g_code, g_stop)

if __name__ == '__main__':
    testing.run_module_suite()
