"""
Compute the Tracy-Widom statistic given a .hud file.

Following Patterson et al. each row of the input .hud file
gives an OTU name followed by presence or absence of each SNP.
"""

from StringIO import StringIO
import math
import os
import argparse

import numpy as np

from SnippetUtil import HandlingError
import Form
import FormOut
import hud
import EigUtil

g_tags = ['pca:compute']


g_default_hud_string = """
IC31 1 1 0 0
IC32 1 1 1 0
IC33 1 0 1 1
IC34 0 0 1 0
""".strip()

def get_corrected_structure(crit, eigenvalues, m, n_prime):
    """
    @param crit: critical value of the Tracy-Widom statistic
    @param eigenvalues: all eigenvalues sorted in descending order
    @param m: the number of OTUs
    @param n_prime: the effective number of SNPs
    @return: significant statistics, one insignificant statistic
    """
    if len(eigenvalues) != m:
        msg_a = 'expected the number of eigenvalues to equal '
        msg_b = 'the number of OTUs'
        raise ValueError(msg_a + msg_b)
    w = eigenvalues[:]
    significant_xs = []
    insignificant_x = None
    while insignificant_x is None:
        m_curr = len(w)
        proportion = w[0] / w.sum()
        L_prime = (m_curr-1)*proportion
        x_prime = get_tracy_widom_statistic(m_curr, n_prime, L_prime)
        if x_prime > crit:
            significant_xs.append(x_prime)
        else:
            insignificant_x = x_prime
        w = w[1:]
    return significant_xs, insignificant_x

def get_tracy_widom_statistic(m, n, L):
    """
    The interpretation of the parameters is purposely vague.
    It depends on whether you are doing linkage correction.
    @param m: like the number of OTUs
    @param n: like the number of SNPs
    @param L: like a normalized principal eigenvalue
    @return: the Tracy-Widom statistic
    """
    alpha = math.sqrt(n-1) + math.sqrt(m)
    mu = (alpha*alpha) / n
    sigma = (alpha / n) * (1/math.sqrt(n-1) + 1/math.sqrt(m))**(1./3.)
    return (L - mu) / sigma

def process(args, hud_lines):
    """
    @param hud_lines: lines of a .hud file
    @return: results in convenient text form
    """
    out = StringIO()
    # get the ordered names from the .hud file
    names, data = hud.decode(hud_lines)
    # create the floating point count matrix
    C_full = np.array(data)
    m_full, n_full = C_full.shape
    # remove invariant columns
    C = np.vstack([v for v in C_full.T if len(set(v))>1]).T
    # get the shape of the matrix
    m, n = C.shape
    # get the column means
    u = C.mean(axis=0)
    # get the centered and normalized counts matrix
    M = (C - u) / np.sqrt(u * (1 - u))
    # construct the sample covariance matrix
    X = np.dot(M, M.T) / n
    # get the eigendecomposition of the covariance matrix
    evals, evecs = EigUtil.eigh(X)
    L1 = evals.sum()
    L2 = np.dot(evals, evals)
    proportion = evals[0] / L1
    # compute the relative size of the first eigenvalue
    L = m*proportion
    # compute the Tracy-Widom statistic
    x = get_tracy_widom_statistic(m, n, L)
    # do linkage correction
    n_prime = ((m+1)*L1*L1) / ((m-1)*L2 - L1*L1)
    # detect additional structure using alpha level of 0.05
    crit = 0.9794
    if n_prime < n:
        L_prime = (m-1)*proportion
        x_prime = get_tracy_widom_statistic(m, n_prime, L_prime)
        sigs, insig = get_corrected_structure(crit, evals, m, n_prime)
    else:
        sigs, insig = get_corrected_structure(crit, evals, m, n)
    # print some infos
    print >> out, 'number of isolates:'
    print >> out, m_full
    print >> out
    print >> out, 'total number of SNPs:'
    print >> out, n_full
    print >> out
    print >> out, 'number of informative SNPs:'
    print >> out, n
    print >> out
    print >> out, 'effective number of linkage-corrected SNPs:'
    if n_prime < n:
        print >> out, n_prime
    else:
        print >> out, '[sample is too degenerate for estimation]'
    print >> out
    print >> out, 'Tracy-Widom statistic (linkage-naive):'
    print >> out, x
    print >> out
    print >> out, 'Tracy-Widom statistic (linkage-corrected):'
    if n_prime < n:
        print >> out, x_prime
    else:
        print >> out, '[sample is too degenerate for estimation]'
    print >> out
    print >> out, 'proportion of variance explained by principal axis:'
    print >> out, proportion
    print >> out
    print >> out, 'number of significant axes of variation:'
    print >> out, len(sigs)
    print >> out
    print >> out, 'significant Tracy-Widom statistics:'
    for sig in sigs:
        print >> out, sig
    print >> out
    print >> out, 'first insignificant Tracy-Widom statistic:'
    print >> out, insig
    print >> out
    print >> out, 'principal axis projection:'
    for loading, name in sorted(zip(evecs[0] * evals[0], names)):
        print >> out, '\t'.join([name, str(loading)])
    print >> out
    # evals should sum to the number of OTUs
    evals_sum = sum(evals)
    if args.sum_to_n:
        print >> out, 'eigenvalues normalized to sum to the number of OTUs:'
        for w in evals:
            print >> out, m_full * w / float(evals_sum)
    elif args.sum_to_1:
        print >> out, 'eigenvalues normalized to sum to 1.0:'
        for w in evals:
            print >> out, w / float(evals_sum)
    return out.getvalue().rstrip()

def get_form():
    """
    @return: the body of a form
    """
    form_objects = [
            Form.MultiLine('hud',
                'contents of a .hud file',
                g_default_hud_string),
            Form.RadioGroup('normalization', 'eigenvalue normalization', [
                Form.RadioItem('sum_to_1', 'sum to 1.0', True),
                Form.RadioItem('sum_to_n', 'sum to the number of OTUs')])]
    return form_objects

def get_form_out():
    return FormOut.Report('out')

def get_response_content(fs):
    return process(fs, fs.hud.splitlines()) + '\n'
