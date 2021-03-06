"""
Use explicit equality and inequality constraints with natural parameterization.

This is as opposed to manually eliminating constraints and redundant variables.
.
Well that did not work out so well.
Apparently matlab fmincon is better than the scipy slsqp optimization.
"""

import string
import math
import argparse
import functools
import warnings
import logging

import numpy
import scipy
import scipy.optimize
import scipy.special
import scipy.linalg
import algopy
import algopy.special

import jeffopt
import kimrecessive
import npcodon
import yangdata


# Precompute some ndarrays for quadrature.
g_quad_x, g_quad_w = kimrecessive.precompute_quadrature(0.0, 1.0, 101)


##########################################################################
# algopy stuff involving parameters

def get_fixation_knudsen(S):
    """
    This is +gwF = 1/2.
    """
    return 1. / kimrecessive.denom_knudsen(0.5*S)

def get_fixation_genic(S):
    return 1. / kimrecessive.denom_genic_a(0.5*S)

def get_fixation_recessive_disease(S):
    sign_S = algopy.sign(S)
    H = algopy.zeros_like(S)
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            H[i, j] = 1. / kimrecessive.denom_piecewise(
                    0.5*S[i, j], sign_S[i, j])
    return H

def get_fixation_dominant_disease(S):
    sign_S = algopy.sign(S)
    H = algopy.zeros_like(S)
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            H[i, j] = 1. / kimrecessive.denom_piecewise(
                    0.5*S[i, j], -sign_S[i, j])
    return H

def get_fixation_unconstrained_fquad_cython(S, d, mask):
    """
    This is not compatible with algopy.
    In this function name, fquad means "fixed quadrature."
    The S ndarray with ndim=2 depends on free parameters.
    The d parameter is itself a free parameter.
    The mask specifies which codon pairs are mutational neighbors.
    @param S: array of selection differences
    @param d: parameter that controls dominance vs. recessivity
    @param mask: only compute entries of neighboring codon pairs
    """
    H = 1. / kimrecessive.denom_fixed_quad_cython(0.5*S, d*numpy.sign(S), mask)
    return H

def get_fixation_unconstrained_fquad(S, d, x, w, codon_neighbor_mask):
    """
    In this function name, fquad means "fixed quadrature."
    The S ndarray with ndim=2 depends on free parameters.
    The d parameter is itself a free parameter.
    So both of those things are algopy objects carrying Taylor information.
    On the other hand, x and w are precomputed ndim=1 ndarrays
    which are not carrying around extra Taylor information.
    @param S: array of selection differences
    @param d: parameter that controls dominance vs. recessivity
    @param x: precomputed roots for quadrature
    @param w: precomputed weights for quadrature
    @param codon_neighbor_mask: only compute entries of neighboring codon pairs
    """
    #TODO: possibly use a mirror symmetry to double the speed
    sign_S = algopy.sign(S)
    D = d * sign_S
    H = algopy.zeros_like(S)
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            if codon_neighbor_mask[i, j]:
                H[i, j] = 1. / kimrecessive.denom_fixed_quad(
                        0.5*S[i, j], D[i, j], x, w)
    return H

def get_fixation_unconstrained(S, d):
    sign_S = algopy.sign(S)
    D = d * sign_S
    H = algopy.zeros_like(S)
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            H[i, j] = 1. / kimrecessive.denom_piecewise(
                    0.5*S[i, j], D[i, j])
    return H

def get_fixation_unconstrained_kb_fquad_cython(S, d, log_kb, mask):
    """
    This uses the Kacser and Burns effect instead of the sign function.
    """
    D = d * numpy.tanh(numpy.exp(log_kb) * S)
    H = 1. / kimrecessive.denom_fixed_quad_cython(0.5*S, D, mask)
    return H

def get_fixation_unconstrained_kb_fquad(
        S, d, log_kb, x, w, codon_neighbor_mask):
    """
    This uses the Kacser and Burns effect instead of the sign function.
    """
    #TODO: possibly use a mirror symmetry to double the speed
    soft_sign_S = algopy.tanh(algopy.exp(log_kb)*S)
    D = d * soft_sign_S
    H = algopy.zeros_like(S)
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            if codon_neighbor_mask[i, j]:
                H[i, j] = 1. / kimrecessive.denom_fixed_quad(
                        0.5*S[i, j], D[i, j], x, w)
    return H

def get_fixation_unconstrained_kb(S, d, log_kb):
    """
    This uses the Kacser and Burns effect instead of the sign function.
    """
    soft_sign_S = algopy.tanh(algopy.exp(log_kb)*S)
    D = d * soft_sign_S
    H = algopy.zeros_like(S)
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            H[i, j] = 1. / kimrecessive.denom_piecewise(
                    0.5*S[i, j], D[i, j])
    return H

def get_fixation_unconstrained_quad(S, d):
    """
    Use numerical quadrature.
    Do not bother trying to use algopy for this.
    """
    sign_S = numpy.sign(S)
    D = d * sign_S
    H = numpy.zeros_like(S)
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            H[i, j] = 1. / kimrecessive.denom_quad(
                    0.5*S[i, j], D[i, j])
    return H

def get_fixation_unconstrained_kb_quad(S, d, log_kb):
    """
    Use numerical quadrature.
    Do not bother trying to use algopy for this.
    """
    soft_sign_S = numpy.tanh(numpy.exp(log_kb)*S)
    D = d * soft_sign_S
    H = numpy.zeros_like(S)
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            H[i, j] = 1. / kimrecessive.denom_quad(
                    0.5*S[i, j], D[i, j])
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

def get_Q_unconstrained(
        ts, tv, syn, nonsyn, compo, asym_compo,
        h,
        log_counts,
        log_mu, log_kappa, log_omega, d, log_nt_weights):
    """
    This adds a single parameter.
    """
    #FIXME: constructing this each time seems wasteful
    codon_neighbor_mask = ts + tv
    #FIXME: this is being hacked to use fixed-order quadrature
    #FIXME: and to disregard the h parameter
    mu = algopy.exp(log_mu)
    kappa = algopy.exp(log_kappa)
    omega = algopy.exp(log_omega)
    F = get_selection_F(log_counts, compo, log_nt_weights)
    S = get_selection_S(F)
    H = get_fixation_unconstrained_fquad(
            S, d, g_quad_x, g_quad_w, codon_neighbor_mask)
    #H = get_fixation_unconstrained_fquad_cython(
            #S, d, codon_neighbor_mask)
    pre_Q = mu * (kappa * ts + tv) * (omega * nonsyn + syn) * algopy.exp(
            algopy.dot(asym_compo, log_nt_weights)) * H
    Q = pre_Q - algopy.diag(algopy.sum(pre_Q, axis=1))
    return Q

def get_Q_unconstrained_kb(
        ts, tv, syn, nonsyn, compo, asym_compo,
        h,
        log_counts,
        log_mu, log_kappa, log_omega, d, log_kb, log_nt_weights):
    """
    This adds yet another parameter.
    """
    #FIXME: constructing this each time seems wasteful
    codon_neighbor_mask = ts + tv
    #FIXME: this is being hacked to use fixed-order quadrature
    #FIXME: and to disregard the h parameter
    mu = algopy.exp(log_mu)
    kappa = algopy.exp(log_kappa)
    omega = algopy.exp(log_omega)
    F = get_selection_F(log_counts, compo, log_nt_weights)
    S = get_selection_S(F)
    H = get_fixation_unconstrained_kb_fquad(
            S, d, log_kb, g_quad_x, g_quad_w, codon_neighbor_mask)
    #H = get_fixation_unconstrained_kb_fquad_cython(
            #S, d, log_kb, codon_neighbor_mask)
    pre_Q = mu * (kappa * ts + tv) * (omega * nonsyn + syn) * algopy.exp(
            algopy.dot(asym_compo, log_nt_weights)) * H
    Q = pre_Q - algopy.diag(algopy.sum(pre_Q, axis=1))
    return Q


def get_log_likelihood(P, v, subs_counts):
    """
    The stationary distribution of P is empirically derived.
    It is proportional to the codon counts by construction.
    @param P: a transition matrix using codon counts and free parameters
    @param v: stationary distribution proportional to observed codon counts
    @param subs_counts: observed substitution counts
    """
    score_matrix_transpose = P.T * v
    return algopy.sum(algopy.log(score_matrix_transpose) * subs_counts)

def eval_f(
        theta,
        subs_counts, log_counts, v,
        h,
        ts, tv, syn, nonsyn, compo, asym_compo,
        ):
    """
    The function formerly known as minimize-me.
    @param theta: length six unconstrained vector of free variables
    """
    # unpack theta
    log_mu = theta[0]
    log_kappa = theta[1]
    log_omega = theta[2]
    log_nt_weights = algopy.zeros(4, dtype=theta)
    log_nt_weights[0] = theta[3]
    log_nt_weights[1] = theta[4]
    log_nt_weights[2] = theta[5]
    log_nt_weights[3] = 0
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
    return -get_log_likelihood(P, v, subs_counts)

def eval_f_unconstrained(
        theta,
        subs_counts, log_counts, v,
        h,
        ts, tv, syn, nonsyn, compo, asym_compo,
        ):
    """
    No dominance/recessivity constraint.
    @param theta: length seven unconstrained vector of free variables
    """
    # unpack theta
    log_mu = theta[0]
    log_kappa = theta[1]
    log_omega = theta[2]
    d = theta[3]
    log_nt_weights = algopy.zeros(4, dtype=theta)
    log_nt_weights[0] = theta[4]
    log_nt_weights[1] = theta[5]
    log_nt_weights[2] = theta[6]
    log_nt_weights[3] = 0
    #
    # construct the transition matrix
    Q = get_Q_unconstrained(
            ts, tv, syn, nonsyn, compo, asym_compo,
            h,
            log_counts,
            log_mu, log_kappa, log_omega, d, log_nt_weights)
    P = algopy.expm(Q)
    #
    # return the neg log likelihood
    neg_log_likelihood = -get_log_likelihood(P, v, subs_counts)
    print neg_log_likelihood
    return neg_log_likelihood

def eval_f_unconstrained_kb(
        theta,
        subs_counts, log_counts, v,
        h,
        ts, tv, syn, nonsyn, compo, asym_compo,
        ):
    """
    No dominance/recessivity constraint.
    @param theta: length seven unconstrained vector of free variables
    """
    # unpack theta
    log_mu = theta[0]
    log_kappa = theta[1]
    log_omega = theta[2]
    d = theta[3]
    log_kb = theta[4]
    log_nt_weights = algopy.zeros(4, dtype=theta)
    log_nt_weights[0] = theta[5]
    log_nt_weights[1] = theta[6]
    log_nt_weights[2] = theta[7]
    log_nt_weights[3] = 0
    #
    # construct the transition matrix
    Q = get_Q_unconstrained_kb(
            ts, tv, syn, nonsyn, compo, asym_compo,
            h,
            log_counts,
            log_mu, log_kappa, log_omega, d, log_kb, log_nt_weights)
    P = algopy.expm(Q)
    #
    # return the neg log likelihood
    neg_log_likelihood = -get_log_likelihood(P, v, subs_counts)
    print neg_log_likelihood
    return neg_log_likelihood

def submain_unconstrained_dominance_kb(args):
    #
    # Precompute some ndarrays
    # according to properties of DNA and the genetic code.
    if args.mtdna or args.force_mtcode:
        code = npcodon.g_code_mito
        stop = npcodon.g_stop_mito
    else:
        code = npcodon.g_code
        stop = npcodon.g_stop
    #
    all_codons = npcodon.enum_codons(stop)
    codons = all_codons[:-len(stop)]
    ts, tv = npcodon.get_ts_tv(codons)
    syn, nonsyn = npcodon.get_syn_nonsyn(code, codons)
    compo = npcodon.get_compo(codons)
    asym_compo = npcodon.get_asym_compo(codons)
    ham = npcodon.get_hamming(codons)
    #
    subs_counts = yangdata.get_subs_counts_from_data_files(args)
    codon_counts = (
            numpy.sum(subs_counts, axis=0) + numpy.sum(subs_counts, axis=1))
    for a, b in zip(codons, codon_counts):
        print a, ':', b
    print 'raw codon total:', numpy.sum(codon_counts)
    print 'raw codon counts:', codon_counts
    codon_counts = codon_counts[:len(codons)]
    print 'non-stop codon total:', numpy.sum(codon_counts)
    subs_counts = subs_counts[:len(codons), :len(codons)]
    v = codon_counts / float(numpy.sum(codon_counts))
    log_counts = numpy.log(codon_counts)
    #
    """
    if args.disease == 'kacser':
        if args.integrate == 'quadrature':
            h = get_fixation_unconstrained_kb_quad
        elif args.integrate == 'special':
            h = get_fixation_unconstrained_kb
        else:
            raise Exception
    else:
        raise Exception
    """
    h = None
    #
    # predefine some plausible parameters but not the scaling parameter
    log_mu = 0
    log_kappa = 1
    log_omega = -3
    d = 1.6
    #d = 0.5
    log_kb = 0
    log_nt_weights = numpy.zeros(4)
    #
    # get the rate matrix associated with the initial guess
    Q = get_Q_unconstrained_kb(
            ts, tv, syn, nonsyn, compo, asym_compo,
            h,
            log_counts,
            log_mu, log_kappa, log_omega, d, log_kb, log_nt_weights)
    #
    # get the minimum expected number of substitutions between codons
    mu_empirical = npcodon.get_lb_expected_subs(ham, subs_counts)
    mu_implied = -numpy.sum(numpy.diag(Q) * v)
    log_mu = math.log(mu_empirical) - math.log(mu_implied)
    print 'lower bound on expected mutations per codon site:', mu_empirical
    print
    # construct the initial guess
    theta = numpy.array([
        log_mu,
        log_kappa,
        log_omega,
        d,
        log_kb,
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
    initial_cost = eval_f_unconstrained_kb(theta, *fmin_args)
    print 'negative log likelihood of initial guess:',
    print initial_cost
    print
    print 'entropy bound on negative log likelihood:',
    print npcodon.get_lb_neg_ll(subs_counts)
    print
    do_opt(args, eval_f_unconstrained_kb, theta, fmin_args)


def submain_unconstrained_dominance(args):
    #
    # Precompute some ndarrays
    # according to properties of DNA and the genetic code.
    if args.mtdna or args.force_mtcode:
        code = npcodon.g_code_mito
        stop = npcodon.g_stop_mito
    else:
        code = npcodon.g_code
        stop = npcodon.g_stop
    #
    all_codons = npcodon.enum_codons(stop)
    codons = all_codons[:-len(stop)]
    ts, tv = npcodon.get_ts_tv(codons)
    syn, nonsyn = npcodon.get_syn_nonsyn(code, codons)
    compo = npcodon.get_compo(codons)
    asym_compo = npcodon.get_asym_compo(codons)
    ham = npcodon.get_hamming(codons)
    #
    subs_counts = yangdata.get_subs_counts_from_data_files(args)
    codon_counts = (
            numpy.sum(subs_counts, axis=0) + numpy.sum(subs_counts, axis=1))
    for a, b in zip(codons, codon_counts):
        print a, ':', b
    print 'raw codon total:', numpy.sum(codon_counts)
    print 'raw codon counts:', codon_counts
    codon_counts = codon_counts[:len(codons)]
    print 'non-stop codon total:', numpy.sum(codon_counts)
    subs_counts = subs_counts[:len(codons), :len(codons)]
    v = codon_counts / float(numpy.sum(codon_counts))
    log_counts = numpy.log(codon_counts)
    #
    """
    if args.disease == 'unconstrained':
        if args.integrate == 'quadrature':
            h = get_fixation_unconstrained_quad
        elif args.integrate == 'special':
            h = get_fixation_unconstrained
        else:
            raise Exception
    else:
        raise Exception
    """
    #FIXME: the h parameter is becoming obsolete
    h = None
    # predefine some plausible parameters but not the scaling parameter
    log_mu = 0
    log_kappa = 1
    log_omega = -3
    d = 1.6
    #d = 0.5
    #d = -1.2
    log_nt_weights = numpy.zeros(4)
    #
    # get the rate matrix associated with the initial guess
    Q = get_Q_unconstrained(
            ts, tv, syn, nonsyn, compo, asym_compo,
            h,
            log_counts,
            log_mu, log_kappa, log_omega, d, log_nt_weights)
    #
    # get the minimum expected number of substitutions between codons
    mu_empirical = npcodon.get_lb_expected_subs(ham, subs_counts)
    mu_implied = -numpy.sum(numpy.diag(Q) * v)
    log_mu = math.log(mu_empirical) - math.log(mu_implied)
    print 'lower bound on expected mutations per codon site:', mu_empirical
    print
    # construct the initial guess
    theta = numpy.array([
        log_mu,
        log_kappa,
        log_omega,
        d,
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
    initial_cost = eval_f_unconstrained(theta, *fmin_args)
    print 'negative log likelihood of initial guess:',
    print initial_cost
    print
    print 'entropy bound on negative log likelihood:',
    print npcodon.get_lb_neg_ll(subs_counts)
    print
    do_opt(args, eval_f_unconstrained, theta, fmin_args)



def submain_constrained_dominance(args):
    #
    # Precompute some ndarrays
    # according to properties of DNA and the genetic code.
    if args.mtdna or args.force_mtcode:
        code = npcodon.g_code_mito
        stop = npcodon.g_stop_mito
    else:
        code = npcodon.g_code
        stop = npcodon.g_stop
    #
    all_codons = npcodon.enum_codons(stop)
    codons = all_codons[:-len(stop)]
    ts, tv = npcodon.get_ts_tv(codons)
    syn, nonsyn = npcodon.get_syn_nonsyn(code, codons)
    compo = npcodon.get_compo(codons)
    asym_compo = npcodon.get_asym_compo(codons)
    ham = npcodon.get_hamming(codons)
    #
    subs_counts = yangdata.get_subs_counts_from_data_files(args)
    codon_counts = numpy.sum(subs_counts, axis=0) + numpy.sum(
            subs_counts, axis=1)
    for a, b in zip(codons, codon_counts):
        print a, ':', b
    print 'raw codon total:', numpy.sum(codon_counts)
    print 'raw codon counts:', codon_counts
    codon_counts = codon_counts[:len(codons)]
    print 'non-stop codon total:', numpy.sum(codon_counts)
    subs_counts = subs_counts[:len(codons), :len(codons)]
    v = codon_counts / float(numpy.sum(codon_counts))
    log_counts = numpy.log(codon_counts)
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
    # initialize parameter values
    mu_r = 1.0
    kappa = 2.0
    omega = 0.1
    #pA = 0.25
    #pC = 0.25
    #pG = 0.25
    #pT = 0.25
    theta = numpy.array([mu_r, kappa, omega, 0, 0, 0, 0])
    #
    # adjust the expected rate parameter
    Q = get_Q_slsqp(
            ts, tv, syn, nonsyn, compo, asym_compo,
            h,
            log_counts, v,
            theta)
    expected_rate = -algopy.dot(algopy.diag(Q), v)
    mu_n = 1. / expected_rate
    mu_r = npcodon.get_lb_expected_subs(ham, subs_counts)
    theta = numpy.array([mu_r, kappa, omega, 0, 0, 0, 0])
    #
    # get the log likelihood associated with the initial guess
    fmin_args = (
            subs_counts, log_counts, v,
            h,
            ts, tv, syn, nonsyn, compo, asym_compo,
            )
    initial_cost = eval_f(theta, *fmin_args)
    print 'negative log likelihood of initial guess:',
    print initial_cost
    print
    print 'entropy bound on negative log likelihood:',
    print npcodon.get_lb_neg_ll(subs_counts)
    print
    do_opt(args, eval_f, theta, fmin_args)


def eval_grad(f, theta, *args):
    """
    Compute the gradient of f in the forward mode of automatic differentiation.
    """
    theta = algopy.UTPM.init_jacobian(theta)
    retval = f(theta, *args)
    return algopy.UTPM.extract_jacobian(retval)

def eval_hess(f, theta, *args):
    """
    Compute the hessian of f in the forward mode of automatic differentiation.
    """
    theta = algopy.UTPM.init_hessian(theta)
    retval = f(theta, *args)
    return algopy.UTPM.extract_hessian(len(theta), retval)

def get_Q_slsqp(
        ts, tv, syn, nonsyn, compo, asym_compo,
        h,
        log_counts, v,
        theta):
    #FIXME: hardcoded for selection without recessivity parameters
    #
    # unpack theta
    branch_length = theta[0]
    kappa = theta[1]
    omega = theta[2]
    """
    nt_probs = algopy.zeros(4, dtype=theta)
    nt_probs[0] = theta[3]
    nt_probs[1] = theta[4]
    nt_probs[2] = theta[5]
    nt_probs[3] = 1.0 - algopy.sum(nt_probs)
    print nt_probs
    log_nt_weights = algopy.log(nt_probs)
    """
    log_nt_weights = theta[-4:]
    #
    F = get_selection_F(log_counts, compo, log_nt_weights)
    S = get_selection_S(F)
    pre_Q_exch = (kappa * ts + tv) * (omega * nonsyn + syn)
    pre_Q = pre_Q_exch * algopy.exp(
            algopy.dot(asym_compo, log_nt_weights)) * h(S)
    rates = algopy.sum(pre_Q, axis=1)
    Q = pre_Q - algopy.diag(rates)
    Q *= branch_length / algopy.dot(rates, v)
    return Q

def f_eqcons(
        theta,
        subs_counts, log_counts, v,
        h,
        ts, tv, syn, nonsyn, compo, asym_compo,
        ):
    #FIXME: obsolete
    #FIXME: hardcoded for selection without recessivity parameters
    #
    # Init the array of values that should be zero when the equality
    # constraints are satisfied.
    equality_violations = algopy.zeros(2, dtype=theta)
    """
    #
    # Add the equality constraint for the expected rate.
    # This is easily computed through the rate matrix.
    Q = get_Q_slsqp(
            ts, tv, syn, nonsyn, compo, asym_compo,
            h,
            log_counts, v,
            theta)
    expected_rate = -algopy.dot(algopy.diag(Q), v)
    equality_violations[0] = theta[0] - expected_rate
    """
    #
    # Add the equality constraint for the mutational process
    # nucleotide equilibrium distribution.
    equality_violations[0] = algopy.sum(theta[-4:])
    #
    return equality_violations

def eval_f(
        theta,
        subs_counts, log_counts, v,
        h,
        ts, tv, syn, nonsyn, compo, asym_compo,
        ):
    """
    The function formerly known as minimize-me.
    @param theta: length six unconstrained vector of free variables
    """
    #
    # construct the rate matrix and the transition matrix
    Q = get_Q_slsqp(
            ts, tv, syn, nonsyn, compo, asym_compo,
            h,
            log_counts, v,
            theta)
    P = algopy.expm(Q)
    #
    # return the neg log likelihood
    neg_log_likelihood = -get_log_likelihood(P, v, subs_counts)
    return neg_log_likelihood

def do_opt(args, f, theta, fmin_args):
    """
    @param args: directly parsed from the command line
    @param f: function to minimize
    @param theta: initial guess of parameter values
    @param fmin_args: data and other precomputed things independent of theta
    """
    #FIXME: this is currently hardcoded for genic selection
    # 0: expected number of substitutions per site
    #XXX# 1: normalizing rate constant
    # 2: kappa transition/transversion ratio
    # 3: omega synonymous/nonsynonymous ratio
    # 4: mutational process equilibrium frequency of A
    # 5: mutational process equilibrium frequency of C
    # 6: mutational process equilibrium frequency of G
    #XXX# 7: mutational process equilibrium frequency of T
    results = scipy.optimize.fmin_slsqp(
            f,
            theta,
            f_eqcons=f_eqcons,
            bounds = [
                (1e-5, 1e1),
                (1e-5, 1e3),
                (1e-5, 1e3),
                #(0.0, 1.0),
                #(0.0, 1.0),
                #(0.0, 1.0),
                #(0.0, 1.0),
                (-numpy.inf, numpy.inf),
                (-numpy.inf, numpy.inf),
                (-numpy.inf, numpy.inf),
                (-numpy.inf, numpy.inf),
                ],
            fprime=functools.partial(eval_grad, f),
            fprime_eqcons=functools.partial(eval_grad, f_eqcons),
            args=fmin_args,
            iter=10000,
            disp=2,
            full_output=True,
            )
    print 'results:', results


def main(args):
    if args.disease == 'unconstrained':
        return submain_unconstrained_dominance(args)
    elif args.disease == 'kacser':
        return submain_unconstrained_dominance_kb(args)
    else:
        return submain_constrained_dominance(args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
            '--disease',
            choices=(
                'genic', 'recessive', 'dominant',
                'unconstrained', 'kacser'),
            default='genic',
            help='the mode of natural selection on unpreferred codons')
    parser.add_argument(
            '--mtdna',
            action='store_true',
            help='read the mtdna file from the website of Ziheng Yang')
    parser.add_argument(
            '--force-mtcode',
            action='store_true',
            help='use the mitochondrial genetic code and stop codons')
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

