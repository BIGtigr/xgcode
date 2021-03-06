"""
Better approximate a figure from a publication by Kai Zeng 2010.

This approximation samples 10 alleles from a
fixed size population of diploid individuals.
The figure (fig. 2) in the publication may be for a large population limit.
Gamma for allele 4 is set to 0.
"""

from StringIO import StringIO
import time
import math

import numpy as np
from scipy import integrate

import Form
import FormOut
import MatrixUtil
import StatsUtil
import kaizeng
import wrightfisher
import Util
import RUtil
from RUtil import mk_call_str

def get_form():
    """
    @return: the body of a form
    """
    return [
            Form.Integer('N_big_diploid', 'diploid population size',
                100, low=5, high=200),
            Form.Float('gamma_0', 'gamma for allele 1', 0),
            Form.Float('gamma_1', 'gamma for allele 2', 1.5),
            Form.Float('gamma_2', 'gamma for allele 3', 1),
            Form.RadioGroup('options',
                'sample haplotypes from a finite population', [
                    Form.RadioItem(
                        'without_replacement', 'without replacement', True),
                    Form.RadioItem(
                        'with_replacement', 'with replacement'),
                    ]),
            Form.ImageFormat(),
            ]

def get_form_out():
    return FormOut.Image('plot')

def _approx(p0, g0, g1, n0, n1):
    """
    This is a large population approximation.
    @param p0: proportion of allele 0 at the site
    @param g0: scaled selection
    @param g1: scaled selection
    @param n0: count of allele 0 in sample from child population
    @param n1: count of allele 1 in sample from child population
    @return: probability of the (n0, n1) selection given an n0+n1 size sample
    """
    p1 = 1 - p0
    # approximate likelihood of p0 given the selection parameters
    likelihood = math.exp((g1 - g0) * p0) / (p0 * p1)
    # get a binomial probability
    p = Util.choose(n0+n1, n0) * (p0 ** n0) * (p1 ** n1)
    # return the scaled probability
    return likelihood * p

def diallelic_approximation(N_small, g0, g1):
    """
    This is a large population approximation.
    """
    hist = np.zeros(N_small+1)
    for n0 in range(1, N_small):
        n1 = N_small - n0
        hist[n0] = integrate.quad(_approx, 0, 1, args=(g0, g1, n0, n1))[0]
    return hist[1:-1] / np.sum(hist[1:-1])

def get_sample_pmf_without_replacement(n, v):
    """
    @param n: this is the size of the sample of haplotypes
    @param v: distribution over proportions of allele 0 at sites
    @return: distribution over counts of allele 0 in a sample of size n
    """
    accum = np.zeros(N_small + 1)
    denominator = Util.choose(N_big, N_small)
    for i, p_state in enumerate(v):
        for j in range(N_small + 1):
            numerator = Util.choose(i, j) * Util.choose(N_big - i, N_small - j)
            if not numerator:
                continue
            accum[j] += (p_state * numerator) / denominator
    return accum[1:-1] / np.sum(accum[1:-1])

def get_two_allele_distribution(N_big, N_small, f0, f1, f_subsample):
    """
    Assumes small genic selection.
    Assumes small mutation.
    The mutational bias does not affect the distribution.
    @param N_big: total number of alleles in the population
    @param N_small: number of alleles sampled from the population
    @param f0: fitness of allele 0
    @param f1: fitness of allele 1
    @param f_subsample: subsampling function
    @return: distribution over all non-fixed population states
    """
    # construct a transition matrix
    nstates = N_big + 1
    P = np.zeros((nstates, nstates))
    for i in range(nstates):
        p0, p1 = wrightfisher.genic_diallelic(f0, f1, i, N_big - i)
        if i == 0:
            P[i, 1] = 1.0
        elif i == N_big:
            P[i, N_big - 1] = 1.0
        else:
            for j in range(nstates):
                logp = StatsUtil.binomial_log_pmf(j, N_big, p0)
                P[i, j] = math.exp(logp)
    # find the stationary distribution
    v = MatrixUtil.get_stationary_distribution(P)
    MatrixUtil.assert_distribution(v)
    if not np.allclose(v, np.dot(v, P)):
        raise ValueError('expected a left eigenvector with eigenvalue 1')
    # return the stationary distribution conditional on dimorphism
    distn = f_subsample(v, N_small)
    return distn[1:-1] / np.sum(distn[1:-1])

def get_response_content(fs):
    N_small = 10
    N_big_diploid = fs.N_big_diploid
    N_big_haploid = N_big_diploid * 2
    if N_big_haploid < N_small:
        raise ValueError('use a larger diploid population size')
    if fs.with_replacement:
        f_subsample = StatsUtil.subsample_pmf_with_replacement
    elif fs.without_replacement:
        f_subsample = StatsUtil.subsample_pmf_without_replacement
    else:
        raise ValueError('subsampling option error')
    k = 4
    gamma = fs.gamma_1
    params_list = [
            (0.008, 1, 1, fs.gamma_0, fs.gamma_1, fs.gamma_2),
            (0.008, 2, 1, fs.gamma_0, fs.gamma_1, fs.gamma_2)]
    allele_histograms = np.zeros((2, N_big_haploid + 1))
    for i, params in enumerate(params_list):
        mutation, selection = kaizeng.params_to_mutation_fitness(
                N_big_haploid, params)
        P = kaizeng.get_transition_matrix(
                N_big_diploid, k, mutation, selection)
        v = MatrixUtil.get_stationary_distribution(P)
        for state_index, counts in enumerate(kaizeng.gen_states(
            N_big_haploid, k)):
            if counts[0] and counts[1]:
                allele_histograms[i, counts[0]] += v[state_index]
    # Define the r table.
    # There are nine columns each corresponding to an allele frequency.
    # There are three rows each corresponding to a configuration.
    arr = []
    # Use the two allele approximation
    # from mcvean and charlesworth 1999 referred to by zeng 2011.
    # I'm not sure if I am using the right equation.
    g0 = fs.gamma_0
    g1 = fs.gamma_1
    """
    s_0 = -gamma_0 / float(N_big)
    s_1 = -gamma_1 / float(N_big)
    hist = np.zeros(N_small+1)
    for i in range(1, N_small):
        x = i / float(N_small)
        hist[i] = math.exp(1*N_big*(s_0 - s_1)*x) / (x*(1-x))
    h = hist[1:-1]
    h /= np.sum(h)
    arr.append(h.tolist())
    """
    arr.append(diallelic_approximation(N_small, g0, g1).tolist())
    # Use the exact two allele distribution.
    # Well, it is exact if I understand the right scaling
    # of the population size and fitnesses.
    f0 = 1.0
    f1 = 1.0 - gamma / N_big_haploid
    #f0 = 1.0 + gamma / N
    #f1 = 1.0
    #f0 = 1.0 + 1.5 / (4*N)
    #f1 = 1.0 - 1.5 / (4*N)
    h = get_two_allele_distribution(
            N_big_haploid, N_small, f0, f1, f_subsample)
    arr.append(h.tolist())
    # Get frequencies for the other two configurations
    for hist in allele_histograms:
        # Get probabilities conditional on dimorphism.
        hist[0] = 0
        hist[-1] = 0
        hist /= np.sum(hist)
        # Get the subsampled pmf.
        distn = f_subsample(hist, N_small)
        MatrixUtil.assert_distribution(distn)
        # Get probabiities conditional on dimorphism of the sample.
        distn[0] = 0
        distn[-1] = 0
        distn /= np.sum(distn)
        # Add to the table of densities.
        arr.append(distn[1:-1].tolist())
    # Get a large population approximation
    # when there is mutational bias.
    params = (0.008, 2, 1, fs.gamma_0, fs.gamma_1, fs.gamma_2)
    mutation, fitness = kaizeng.params_to_mutation_fitness(
            N_big_haploid, params)
    gammas = np.array([fs.gamma_0, fs.gamma_1, fs.gamma_2, 0])
    h = kaizeng.get_large_population_approximation(N_small, k, gammas, mutation)
    arr.append(h.tolist())
    # define the r script
    out = StringIO()
    print >> out, 'title.string <- "allele 1 vs allele 2"'
    print >> out, 'mdat <-', RUtil.matrix_to_R_string(arr)
    print >> out, mk_call_str(
            'barplot',
            'mdat',
            'legend.text=' + mk_call_str(
                'c',
                '"two-allele large N limit"',
                '"two-allele"',
                '"four-allele without mutational bias"',
                '"four-allele with mutational bias (kappa_{1,2}=2)"',
                '"four-allele with mutational bias, large N limit"',
                ),
            'args.legend = list(x="topleft", bty="n")',
            'names.arg = c(1,2,3,4,5,6,7,8,9)',
            main='title.string',
            xlab='"frequency of allele 1"',
            ylab='"frequency"',
            col=mk_call_str(
                'c',
                '"red"',
                '"white"',
                '"black"',
                '"gray"',
                '"blue"',
                ),
            beside='TRUE',
            )
    #print >> out, 'box()'
    script = out.getvalue().rstrip()
    # create the R plot image
    device_name = Form.g_imageformat_to_r_function[fs.imageformat]
    retcode, r_out, r_err, image_data = RUtil.run_plotter_no_table(
            script, device_name)
    if retcode:
        raise RUtil.RError(r_err)
    return image_data
