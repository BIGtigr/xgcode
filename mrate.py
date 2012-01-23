"""
This module is about general finite-state continuous-time Markov processes.

The python packages numpy and scipy are used throughout.
At some point I should probably make separate modules
to emphasize the distinction between reversible and general
continuous-time Markov processes.
"""

import math
import unittest
import itertools

import numpy as np
import scipy
from scipy import linalg

from MatrixUtil import ndot

def get_dense_sequence_rate_matrix(nresidues, nsites):
    """
    Create an reversible rate matrix with uniform stationary distribution.
    Each sequences changes to each other sequence at the same rate.
    The matrix is normalized by expected rate.
    @param nresidues: for example 4 for DNA or 20 for amino acids
    @param nsites: jointly consider this many sites
    """
    nstates = nresidues**nsites
    R = np.ones((nstates, nstates))
    for i in range(nstates):
        R[i, i] = -(nstates - 1)
    uniform_pi = np.reciprocal(nstates * np.ones(nstates))
    expected_rate = -sum(uniform_pi[i] * R[i, i] for i in range(nstates))
    return R / expected_rate

def get_sparse_sequence_rate_matrix(nresidues, nsites):
    """
    Create an reversible rate matrix with uniform stationary distribution.
    Sites change change independently.
    The matrix is normalized by expected rate.
    @param nresidues: for example 4 for DNA or 20 for amino acids
    @param nsites: jointly consider this many sites
    """
    nstates = nresidues**nsites
    R = np.zeros((nstates, nstates))
    for alpha in itertools.product(range(nresidues), repeat=nsites):
        for beta in itertools.product(range(nresidues), repeat=nsites):
            alpha_index = sum(alpha[i]*(nresidues ** i) for i in range(nsites))
            beta_index = sum(beta[i]*(nresidues ** i) for i in range(nsites))
            hamming_dist = sum(1 for a, b in zip(alpha, beta) if a != b)
            if hamming_dist == 1:
                R[alpha_index, beta_index] = 1
    for i in range(nstates):
        R[i, i] = -np.sum(R[i])
    uniform_pi = np.reciprocal(nstates * np.ones(nstates))
    expected_rate = -sum(uniform_pi[i] * R[i, i] for i in range(nstates))
    return R / expected_rate

def expm_spectral(R, t):
    """
    This is for testing expm_diff_spectral only.
    You should use scipy.linalg.expm instead.
    """
    n = len(R)
    v = R_to_distn(R)
    S = symmetrized(R)
    w, U = np.linalg.eigh(S)
    P = np.zeros_like(R)
    for i in range(n):
        for j in range(n):
            for k in range(n):
                a = (v[j] / v[i])**0.5
                b = U[i, k] * U[j, k]
                c = math.exp(t * w[k])
                P[i, j] += a * b * c
    return P

def expm_diff_spectral(R, t):
    """
    Get the rates of change of transition probabilities at time t.
    Use the spectral representation.
    @return: entrywise derivative of transition matrix at time t
    """
    n = len(R)
    v = R_to_distn(R)
    S = symmetrized(R)
    w, U = np.linalg.eigh(S)
    P_diff = np.zeros_like(R)
    for i in range(n):
        for j in range(n):
            for k in range(n):
                a = (v[j] / v[i])**0.5
                b = U[i, k] * U[j, k]
                c = w[k] * math.exp(t * w[k])
                P_diff[i, j] += a * b * c
    return P_diff

def _R_to_eigenpair(R):
    n = len(R)
    Wl, Vl = scipy.linalg.eig(R, left=True, right=False)
    val_vec_pairs = [(abs(Wl[i]), Vl[:,i]) for i in range(n)]
    r_recip, fiedler = sorted(val_vec_pairs)[1]
    return r_recip, fiedler

def R_to_fiedler(R):
    r_recip, fiedler = _R_to_eigenpair(R)
    return fiedler

def R_to_relaxation_time_obsolete(R):
    """
    This fails when the corresponding eigenvalue is indistinct.
    """
    r_recip, fiedler = _R_to_eigenpair(R)
    return 1 / r_recip

def R_to_relaxation_time(R):
    """
    This assumes a reversible irreducible rate matrix.
    """
    W = np.linalg.eigvalsh(R)
    abs_eigenvalue = sorted(abs(w) for w in W)[1]
    return 1 / abs_eigenvalue

def R_to_distn(R):
    """
    @param R: rate matrix
    @return: stationary distribution
    """
    n = len(R)
    Wl, Vl = scipy.linalg.eig(R, left=True, right=False)
    val_vec_pairs = [(abs(Wl[i]), Vl[:,i]) for i in range(n)]
    dummy, pi_eigenvector = min(val_vec_pairs)
    total = np.sum(pi_eigenvector)
    pi_arr = np.array([v/total for v in pi_eigenvector])
    return pi_arr

def R_to_total_rate(R):
    #TODO: the jargon should be 'expected rate' rather than 'total rate'
    n = len(R)
    distn = R_to_distn(R)
    total_rate = 0.0
    for i in range(n):
        total_rate -= distn[i] * R[i, i]
    return total_rate

def symmetrized(R):
    """
    Get the symmetrized matrix of a reversible markov process.
    This returns a symmetric matrix that is not a rate matrix
    because rows do not sum to zero.
    """
    v = R_to_distn(R)
    lam = np.diag(np.sqrt(v))
    rlam = np.diag(np.reciprocal(np.sqrt(v)))
    return ndot(lam, R, rlam)

class TestMrate(unittest.TestCase):

    def test_expm(self):
        M = np.array([
            [-1.55273124,  0.40323905,  0.90129456,  0.24819763],
            [ 2.41191856, -5.14753325,  2.29550348,  0.44011122],
            [ 0.82711917,  0.3521918,  -1.44057109,  0.26126012],
            [ 3.01693453,  0.89439764,  3.46050956, -7.37184173]])
        t = 0.3
        observed = scipy.linalg.expm(M * t)
        expected = expm_spectral(M, t)
        self.assertTrue(np.allclose(observed, expected))

if __name__ == '__main__':
    unittest.main()
