"""
This is currently a script but later it should be web accessible.
First version is October 4 2012.
It is for testing a pure recessive disease codon preference model
against the genic model of Yang and Nielsen 2008.
This script does not use so many biological libraries
because for some reason I am adopting a more matlab-like style.
All matrices in this script are ndarrays as opposed to actual python matrices.
"""

import string
import math
import argparse
from itertools import product

import numpy
import scipy
import scipy.optimize
import scipy.special
import scipy.linalg
import algopy
import algopy.special

import jeffopt
import kimrecessive


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
        #('cgt', 'cgc', 'cga', 'cgg', 'aga', 'agg'),
        ('cgt', 'cgc', 'cga', 'cgg'),
        ('aat', 'aac'),
        ('gat', 'gac'),
        ('tgt', 'tgc'),
        ('caa', 'cag'),
        ('gaa', 'gag'),
        ('ggt', 'ggc', 'gga', 'ggg'),
        ('cat', 'cac'),
        #('att', 'atc', 'ata'),
        ('att', 'atc'),
        ('tta', 'ttg', 'ctt', 'ctc', 'cta', 'ctg'),
        ('aaa', 'aag'),
        #('atg',),
        ('atg', 'ata'),
        ('ttt', 'ttc'),
        ('cct', 'ccc', 'cca', 'ccg'),
        ('tct', 'tcc', 'tca', 'tcg', 'agt', 'agc'),
        ('act', 'acc', 'aca', 'acg'),
        #('tgg',),
        ('tgg', 'tga'),
        ('tat', 'tac'),
        ('gtt', 'gtc', 'gta', 'gtg'),
        #('taa', 'tga', 'tag'),
        ('tag', 'taa', 'aga', 'agg'),
        }

g_mtdna_names = {'human_horai', 'chimp_horai'}


##########################################################################
# precomputation of pure numpy arrays


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


##########################################################################
# these two functions are also pure numpy and speed does not matter


def get_lb_neg_ll(subs_counts):
    """
    Get the lower bound negative log likelihood.
    It uses an entropy-based calculation.
    @param subs_counts: codon substitution counts
    """
    nstates = subs_counts.shape[0]
    counts = []
    for i in range(nstates):
        for j in range(nstates):
            if i < j:
                c = subs_counts[i, j] + subs_counts[j, i]
                counts.append(c)
            elif i == j:
                c = subs_counts[i, j]
                counts.append(c)
    # return the entropy of the unordered pair count vector
    probs = numpy.array(counts, dtype=float) / numpy.sum(counts)
    return numpy.sum(-c*math.log(p) for c, p in zip(counts, probs) if c)

def get_lb_expected_subs(ham, subs_counts):
    """
    Get the lower bound of expected substitutions.
    This is expected minimum possible number of substitutions
    between aligned codons.
    """
    return numpy.sum(ham * subs_counts) / float(numpy.sum(subs_counts))


##########################################################################
# algopy stuff involving parameters

def get_fixation_genic(S):
    return 1. / kimrecessive.denom_genic_a(0.5*S)

def get_fixation_recessive_disease(S):
    sign_S = algopy.sign(S)
    H = numpy.zeros_like(S)
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            H[i, j] = 1. / kimrecessive.denom_piecewise(
                    0.5*S[i, j], sign_S[i, j])
    return H

def get_selection_F(log_counts, compo, log_nt_weights):
    """
    The F and S notation is from Yang and Nielsen 2008.
    Note that three of the four log nt weights are free parameters.
    One of the four log weights is zero and the other three
    are free parameters to be estimated jointly in the
    maximimum likelihood search,
    so this function is inside the optimization loop.
    @param log_counts: logs of empirical codon counts
    @param compo: codon composition as defined in the get_compo function
    @param log_nt_weights: un-normalized log mutation process probabilities
    @return: a log selection for each codon, up to an additive constant
    """
    return log_counts - algopy.dot(compo, log_nt_weights)

def get_selection_S(F):
    """
    The F and S notation is from Yang and Nielsen 2008.
    @param F: a selection value for each codon, up to an additive constant
    @return: selection differences F_j - F_i, also known as S_ij
    """
    e = algopy.ones_like(F)
    return algopy.outer(e, F) - algopy.outer(F, e)

def get_Q(
        ts, tv, syn, nonsyn, compo, asym_compo,
        h,
        log_counts,
        log_mu, log_kappa, log_omega, log_nt_weights):
    """
    Notation is from Yang and Nielsen 2008.
    The first group of args consists of precomputed ndarrays.
    The second group is only the fixation function.
    The third group consists of empirically (non-free) estimated parameters.
    The fourth group depends only on free parameters.
    @param ts: indicator for transition
    @param tv: indicator for transversion
    @param syn: indicator for synonymous codons
    @param nonsyn: indicator for nonsynonymous codons
    @param compo: site independent nucleotide composition per codon
    @param asym_compo: tensor from get_asym_compo function
    @param h: fixation function
    @param log_counts: empirically counted codons in the data set
    @param log_mu: free param for scaling
    @param log_kappa: free param for transition transversion rate distinction
    @param log_omega: free param for syn nonsyn rate distinction
    @param log_nt_weights: mostly free param array for mutation equilibrium
    @return: rate matrix
    """
    mu = algopy.exp(log_mu)
    kappa = algopy.exp(log_kappa)
    omega = algopy.exp(log_omega)
    F = get_selection_F(log_counts, compo, log_nt_weights)
    S = get_selection_S(F)
    pre_Q = mu * (kappa * ts + tv) * (omega * nonsyn + syn) * algopy.exp(
            algopy.dot(asym_compo, log_nt_weights)) * h(S)
    Q = pre_Q - algopy.diag(algopy.sum(pre_Q, axis=1))
    return Q

def read_yang_alignments(codons, lines):
    """
    Read the file that Ziheng Yang put on his website.
    For our purposes,
    an alignment will be a list of [taxon_name, codon_index_sequence] pairs.
    @param codons: sequence lowercase codons
    @param lines: text lines of the alignment
    @return: list of alignments
    """
    names = {'hg18', 'pantro2', 'rhemac2', 'mm8', 'rn4'}
    # construct the inverse codon map
    c_to_i = dict((c, i) for i, c in enumerate(codons))
    # read the alignments
    alignments = []
    alignment = []
    expected_len = None
    for line in lines:
        line = line.strip().lower()
        if not line:
            continue
        elements = line.split()
        if elements[0] in names:
            seq = numpy.array([c_to_i[c] for c in elements[1:]], dtype=int)
            if len(seq) * 3 != expected_len:
                raise Exception((len(seq) * 3, expected_len))
            alignment.append((elements[0], seq))
        elif int(elements[0]) == len(names):
            if len(elements) != 2:
                raise Exception(elements)
            expected_len = int(elements[1])
            if alignment:
                alignments.append(alignment)
            alignment = []
        else:
            raise Exception(elements[0])
    if alignment:
        alignments.append(alignment)
    return alignments

def read_yang_mtdna_alignment(codons, lines):
    c_to_i = dict((c, i) for i, c in enumerate(codons))
    name = None
    alignment = []
    segments = []
    for line in lines:
        line = line.strip().lower()
        if line in g_mtdna_names or not line:
            if segments:
                dna = ''.join(segments)
                codons = [dna[i:i+3] for i in range(0, len(dna), 3)]
                seq = numpy.array(
                        [c_to_i[''.join(c)] for c in codons], dtype=int)
                alignment.append((name, seq))
        if line in g_mtdna_names:
            name = line
            segments = []
        elif not line:
            name = None
        else:
            if name:
                segments.append(line)
    return alignment

def get_empirical_summary(ncodons, alignments, t1, t2):
    """
    Get codon counts and substitution counts.
    @param ncodons: allowed number of codons
    @param alignments: from the get_yang_alignments function
    @param t1: first taxon name
    @param t2: second taxon name
    @return: codon_counts, subs_counts
    """
    codon_counts = numpy.zeros(ncodons, dtype=int)
    subs_counts = numpy.zeros((ncodons, ncodons), dtype=int)
    for alignment in alignments:
        d = dict(alignment)
        for i, j in zip(d[t1], d[t2]):
            codon_counts[i] += 1
            codon_counts[j] += 1
            subs_counts[i, j] += 1
    return codon_counts, subs_counts

def get_log_likelihood(P, v, subs_counts):
    """
    The stationary distribution of P is empirically derived.
    It is proportional to the codon counts by construction.
    @param P: a transition matrix using codon counts and free parameters
    @param v: stationary distribution proportional to observed codon counts
    @param subs_counts: observed substitution counts
    """
    return algopy.sum(subs_counts * algopy.log(P.T * v))

def minimize_me(
        theta,
        subs_counts, log_counts, v,
        h,
        ts, tv, syn, nonsyn, compo, asym_compo,
        ):
    """
    @param theta: length six unconstrained vector of free variables
    """
    #
    # unpack theta
    log_mu, log_kappa, log_omega, log_a, log_c, log_g = theta.tolist()
    log_nt_weights = numpy.array([log_a, log_c, log_g, 0], dtype=float)
    #
    # construct the transition matrix
    Q = get_Q(
            ts, tv, syn, nonsyn, compo, asym_compo,
            h,
            log_counts,
            log_mu, log_kappa, log_omega, log_nt_weights)
    P = algopy.expm(Q)
    #
    # return the neg log likelihood
    ret = -get_log_likelihood(P, v, subs_counts)
    return ret

def main(args):
    #
    # Precompute some ndarrays
    # according to properties of DNA and the genetic code.
    if args.mtdna:
        code = g_code_mito
        stop = g_stop_mito
    else:
        code = g_code
        stop = g_stop
    #
    all_codons = enum_codons(stop)
    codons = all_codons[:-len(stop)]
    ts, tv = get_ts_tv(codons)
    syn, nonsyn = get_syn_nonsyn(code, codons)
    compo = get_compo(codons)
    asym_compo = get_asym_compo(codons)
    ham = get_hamming(codons)
    #
    # check invariants of precomputed ndarrays
    if len(all_codons) != 64:
        raise Exception
    if len(codons) != 64 - len(stop):
        raise Exception
    if numpy.unique(ts).tolist() != [0, 1]:
        raise Exception
    if numpy.unique(tv).tolist() != [0, 1]:
        raise Exception
    #
    # check the genetic codes for typos
    for test_code in (g_code, g_code_mito):
        table_codons = list(c for cs in test_code for c in cs)
        if len(test_code) != 21:
            raise Exception
        if len(table_codons) != len(set(table_codons)):
            raise Exception
        if set(codons) - set(table_codons):
            raise Exception(set(all_codons) - set(table_codons))
        if set(table_codons) - set(all_codons):
            raise Exception(set(table_codons) - set(all_codons))
    #
    # Check reversibility of h functions with respect to F,
    # in the notation of Yang and Nielsen 2008.
    for h in (get_fixation_genic, get_fixation_recessive_disease):
        F = numpy.array([1.2, 2.3, 0, -1.1])
        S = get_selection_S(F)
        fixation = h(S)
        log_ratio = numpy.log(fixation / fixation.T)
        if not numpy.allclose(S, log_ratio):
            raise Exception((S, log_ratio))
    #
    # read alignments from the file
    with open(args.infile) as fin:
        if args.mtdna:
            alignments = [read_yang_mtdna_alignment(all_codons, fin)]
        else:
            alignments = read_yang_alignments(all_codons, fin)
    print 'read', len(alignments), 'alignments'
    print
    #
    # Extract the codon counts and the substitution counts.
    # Then compute the empirical codon distribution and log codon counts.
    if args.mtdna:
        t1, t2 = g_mtdna_names
    else:
        t1, t2 = args.t1, args.t2
    codon_counts, subs_counts = get_empirical_summary(64, alignments, t1, t2)
    for a, b in zip(codons, codon_counts):
        print a, ':', b
    print 'raw codon total:', numpy.sum(codon_counts)
    print 'raw codon counts:', codon_counts
    codon_counts = codon_counts[:len(codons)]
    print 'non-stop codon total:', numpy.sum(codon_counts)
    pseudocount = 0
    codon_counts += pseudocount
    subs_counts = subs_counts[:len(codons), :len(codons)]
    v = codon_counts / float(numpy.sum(codon_counts))
    log_counts = numpy.log(codon_counts)
    print 'codon counts including pseudocount:', codon_counts
    print
    #
    if args.disease == 'genic':
        h = get_fixation_genic
    elif args.disease == 'recessive':
        h = get_fixation_recessive_disease
    elif args.disease == 'dominant':
        h = get_fixation_dominant_disease
    else:
        raise Exception
    #
    # predefine some plausible parameters but not the scaling parameter
    log_mu = 0
    log_kappa = 1
    log_omega = -3
    log_nt_weights = numpy.zeros(4)
    #
    # get the rate matrix associated with the initial guess
    Q = get_Q(
            ts, tv, syn, nonsyn, compo, asym_compo,
            h,
            log_counts,
            log_mu, log_kappa, log_omega, log_nt_weights)
    #
    # get the minimum expected number of substitutions between codons
    mu_empirical = get_lb_expected_subs(ham, subs_counts)
    mu_implied = -numpy.sum(numpy.diag(Q) * v)
    log_mu = math.log(mu_empirical) - math.log(mu_implied)
    print 'lower bound on expected mutations per codon site:', mu_empirical
    print
    # construct the initial guess
    theta = numpy.array([
        log_mu,
        log_kappa,
        log_omega,
        0,
        0,
        0,
        ])
    #
    # get the log likelihood associated with the initial guess
    fmin_args = (
            subs_counts, log_counts, v,
            h,
            ts, tv, syn, nonsyn, compo, asym_compo,
            )
    initial_cost = minimize_me(theta, *fmin_args)
    print 'negative log likelihood of initial guess:', initial_cost
    print
    #
    # search for the minimum negative log likelihood over multiple parameters
    if args.fmin == 'simplex':
        results = scipy.optimize.fmin(
                minimize_me, theta, args=fmin_args,
                maxfun=10000,
                maxiter=10000,
                xtol=1e-8,
                ftol=1e-8,
                full_output=True)
    elif args.fmin == 'bfgs':
        results = scipy.optimize.fmin_bfgs(
                minimize_me, theta, args=fmin_args,
                maxiter=10000,
                full_output=True)
    elif args.fmin == 'jeffopt':
        results = jeffopt.fmin_jeff_unconstrained(
                minimize_me, theta, args=fmin_args,
                )
    else:
        raise Exception
    print 'results:', results
    xopt = results[0]
    print 'optimal solution vector:', xopt
    print 'exp optimal solution vector:', numpy.exp(xopt)
    print
    print 'entropy bound on negative log likelihood:'
    print get_lb_neg_ll(subs_counts)
    print

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fmin',
            choices=('simplex', 'bfgs', 'jeffopt'),
            default='simplex',
            help='black box multivariate optimization')
    parser.add_argument('--disease',
            choices=('genic', 'recessive', 'dominant'),
            default='genic',
            help='the mode of natural selection on unpreferred codons')
    parser.add_argument('--mtdna', action='store_true',
            help='read the mtdna file from the website of Ziheng Yang')
    parser.add_argument(
            '--infile',
            help='codon alignment input file using the format of Ziheng Yang',
            required=True)
    parser.add_argument(
            '--t1',
            default='mm8',
            help='name of first taxon')
    parser.add_argument(
            '--t2',
            default='rn4',
            help='name of second taxon')
    main(parser.parse_args())

