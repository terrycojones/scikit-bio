# ----------------------------------------------------------------------------
# Copyright (c) 2013--, scikit-bio development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

from __future__ import absolute_import, division, print_function

import functools

import scipy.spatial.distance
import pandas as pd

import skbio
from skbio.diversity.alpha._faith_pd import _faith_pd, _setup_faith_pd
from skbio.diversity.beta._unifrac import (
    _setup_multiple_unweighted_unifrac, _setup_multiple_weighted_unifrac,
    _normalize_weighted_unifrac_by_default)
from skbio.util._decorator import experimental
from skbio.stats.distance import DistanceMatrix
from skbio.diversity._util import (_validate_counts_matrix,
                                   _get_phylogenetic_kwargs)


def _get_alpha_diversity_metric_map():
    return {
        'ace': skbio.diversity.alpha.ace,
        'chao1': skbio.diversity.alpha.chao1,
        'chao1_ci': skbio.diversity.alpha.chao1_ci,
        'berger_parker_d': skbio.diversity.alpha.berger_parker_d,
        'brillouin_d': skbio.diversity.alpha.brillouin_d,
        'dominance': skbio.diversity.alpha.dominance,
        'doubles': skbio.diversity.alpha.doubles,
        'enspie': skbio.diversity.alpha.enspie,
        'esty_ci': skbio.diversity.alpha.esty_ci,
        'faith_pd': skbio.diversity.alpha.faith_pd,
        'fisher_alpha': skbio.diversity.alpha.fisher_alpha,
        'goods_coverage': skbio.diversity.alpha.goods_coverage,
        'heip_e': skbio.diversity.alpha.heip_e,
        'kempton_taylor_q': skbio.diversity.alpha.kempton_taylor_q,
        'margalef': skbio.diversity.alpha.margalef,
        'mcintosh_d': skbio.diversity.alpha.mcintosh_d,
        'mcintosh_e': skbio.diversity.alpha.mcintosh_e,
        'menhinick': skbio.diversity.alpha.menhinick,
        'michaelis_menten_fit': skbio.diversity.alpha.michaelis_menten_fit,
        'observed_otus': skbio.diversity.alpha.observed_otus,
        'osd': skbio.diversity.alpha.osd,
        'pielou_e': skbio.diversity.alpha.pielou_e,
        'robbins': skbio.diversity.alpha.robbins,
        'shannon': skbio.diversity.alpha.shannon,
        'simpson': skbio.diversity.alpha.simpson,
        'simpson_e': skbio.diversity.alpha.simpson_e,
        'singles': skbio.diversity.alpha.singles,
        'strong': skbio.diversity.alpha.strong,
        'gini_index': skbio.diversity.alpha.gini_index,
        'lladser_pe': skbio.diversity.alpha.lladser_pe,
        'lladser_ci': skbio.diversity.alpha.lladser_ci}


@experimental(as_of="0.4.0-dev")
def get_alpha_diversity_metrics():
    """ List scikit-bio's alpha diversity metrics

    The alpha diversity metrics listed here can be passed as metrics to
    ``skbio.diversity.alpha_diversity``.

    Returns
    -------
    list of str
        Alphabetically sorted list of alpha diversity metrics implemented in
        scikit-bio.

    See Also
    --------
    alpha_diversity
    get_beta_diversity_metrics

    """
    metrics = _get_alpha_diversity_metric_map()
    return sorted(metrics.keys())


@experimental(as_of="0.4.0-dev")
def get_beta_diversity_metrics():
    """ List scikit-bio's beta diversity metrics

    The beta diversity metrics listed here can be passed as metrics to
    ``skbio.diversity.beta_diversity``.

    Returns
    -------
    list of str
        Alphabetically sorted list of beta diversity metrics implemented in
        scikit-bio.

    See Also
    --------
    beta_diversity
    get_alpha_diversity_metrics
    scipy.spatial.distance.pdist

    Notes
    -----
    SciPy implements many additional beta diversity metrics that are not
    included in this list. See documentation for
    ``scipy.spatial.distance.pdist`` for more details.

    """
    return sorted(['unweighted_unifrac', 'weighted_unifrac'])


@experimental(as_of="0.4.0-dev")
def alpha_diversity(metric, counts, ids=None, validate=True, **kwargs):
    """ Compute alpha diversity for one or more samples

    Parameters
    ----------
    metric : str, callable
        The alpha diversity metric to apply to the sample(s). Passing metric as
        a string is preferable as this often results in an optimized version of
        the metric being used.
    counts : 1D or 2D array_like of ints or floats
        Vector or matrix containing count/abundance data. If a matrix, each row
        should contain counts of OTUs in a given sample.
    ids : iterable of strs, optional
        Identifiers for each sample in ``counts``. By default, samples will be
        assigned integer identifiers in the order that they were provided.
    validate: bool, optional
        If `False`, validation of the input won't be performed. This step can
        be slow, so if validation is run elsewhere it can be disabled here.
        However, invalid input data can lead to invalid results or error
        messages that are hard to interpret, so this step should not be
        bypassed if you're not certain that your input data are valid. See
        Notes for the description of what validation entails so you can
        determine if you can safely disable validation.
    kwargs : kwargs, optional
        Metric-specific parameters.

    Returns
    -------
    pd.Series
        Values of ``metric`` for all vectors provided in ``counts``. The index
        will be ``ids``, if provided.

    Raises
    ------
    ValueError, MissingNodeError, DuplicateNodeError
        If validation fails (see description of validation in Notes). Exact
        error will depend on what was invalid.
    TypeError
        If invalid method-specific parameters are provided.

    See Also
    --------
    skbio.diversity.alpha
    skbio.diversity.beta_diversity

    Notes
    -----
    The value that you provide for ``metric`` can be either a string (e.g.,
    ``"faith_pd"``) or a function (e.g., ``skbio.diversity.alpha.faith_pd``).
    The metric should generally be passed as a string, as this often uses an
    optimized version of the metric. For example, passing  ``"faith_pd"`` (a
    string) will be tens of times faster than passing the function
    ``skbio.diversity.alpha.faith_pd``. The latter may be faster if computing
    alpha diversity for only one or a few samples, but in these cases the
    difference in runtime is negligible, so it's safer to just err on the side
    of passing ``metric`` as a string.

    Validation of input data confirms the following:
     * ``counts`` data can be safely cast to integers
     * there are no negative values in ``counts``
     * ``counts`` has the correct number of dimensions
     * if ``counts`` is 2-D, all vectors are of equal length
     * the correct number of ``ids`` is provided (if any are provided)

    For phylogenetic diversity metrics, validation additional confirms that:
     * ``otu_ids`` does not contain duplicate values
     * the length of each ``counts`` vector is equal to ``len(otu_ids)``
     * ``tree`` is rooted
     * ``tree`` has more than one node
     * all nodes in ``tree`` except for the root node have branch lengths
     * all tip names in ``tree`` are unique
     * all ``otu_ids`` correspond to tip names in ``tree``

    """
    metric_map = _get_alpha_diversity_metric_map()

    if validate:
        counts = _validate_counts_matrix(counts, ids=ids)

    if metric == 'faith_pd':
        otu_ids, tree, kwargs = _get_phylogenetic_kwargs(counts, **kwargs)
        counts_by_node, branch_lengths = _setup_faith_pd(
            counts, otu_ids, tree, validate, single_sample=False)
        counts = counts_by_node
        metric = functools.partial(_faith_pd, branch_lengths=branch_lengths)
    elif callable(metric):
        metric = functools.partial(metric, **kwargs)
    elif metric in metric_map:
        metric = functools.partial(metric_map[metric], **kwargs)
    else:
        raise ValueError('Unknown metric provided: %r.' % metric)

    results = [metric(c) for c in counts]
    return pd.Series(results, index=ids)


@experimental(as_of="0.4.0")
def beta_diversity(metric, counts, ids=None, validate=True, **kwargs):
    """Compute distances between all pairs of samples

    Parameters
    ----------
    metric : str, callable
        The pairwise distance function to apply. See the scipy ``pdist`` docs
        and the scikit-bio functions linked under *See Also* for available
        metrics. Passing metrics as a strings is preferable as this often
        results in an optimized version of the metric being used.
    counts : 2D array_like of ints or floats
        Matrix containing count/abundance data where each row contains counts
        of OTUs in a given sample.
    ids : iterable of strs, optional
        Identifiers for each sample in ``counts``. By default, samples will be
        assigned integer identifiers in the order that they were provided
        (where the type of the identifiers will be ``str``).
    validate: bool, optional
        If `False`, validation of the input won't be performed. This step can
        be slow, so if validation is run elsewhere it can be disabled here.
        However, invalid input data can lead to invalid results or error
        messages that are hard to interpret, so this step should not be
        bypassed if you're not certain that your input data are valid. See
        Notes for the description of what validation entails so you can
        determine if you can safely disable validation.
    kwargs : kwargs, optional
        Metric-specific parameters.

    Returns
    -------
    skbio.DistanceMatrix
        Distances between all pairs of samples (i.e., rows). The number of
        rows and columns will be equal to the number of rows in ``counts``.

    Raises
    ------
    ValueError, MissingNodeError, DuplicateNodeError
        If validation fails (see description of validation in Notes). Exact
        error will depend on what was invalid.
    TypeError
        If invalid method-specific parameters are provided.

    See Also
    --------
    skbio.diversity.beta
    skbio.diversity.alpha_diversity
    scipy.spatial.distance.pdist

    Notes
    -----
    The value that you provide for ``metric`` can be either a string (e.g.,
    ``"unweighted_unifrac"``) or a function
    (e.g., ``skbio.diversity.beta.unweighted_unifrac``). The metric should
    generally be passed as a string, as this often uses an optimized version
    of the metric. For example, passing  ``"unweighted_unifrac"`` (a string)
    will be hundreds of times faster than passing the function
    ``skbio.diversity.beta.unweighted_unifrac``. The latter is faster if
    computing only one or a few distances, but in these cases the difference in
    runtime is negligible, so it's safer to just err on the side of passing
    ``metric`` as a string.

    Validation of input data confirms the following:
     * ``counts`` data can be safely cast to integers
     * there are no negative values in ``counts``
     * ``counts`` has the correct number of dimensions
     * all vectors in ``counts`` are of equal length
     * the correct number of ``ids`` is provided (if any are provided)

    For phylogenetic diversity metrics, validation additional confirms that:
     * ``otu_ids`` does not contain duplicate values
     * the length of each ``counts`` vector is equal to ``len(otu_ids)``
     * ``tree`` is rooted
     * ``tree`` has more than one node
     * all nodes in ``tree`` except for the root node have branch lengths
     * all tip names in ``tree`` are unique
     * all ``otu_ids`` correspond to tip names in ``tree``

    """
    if validate:
        counts = _validate_counts_matrix(counts, ids=ids)

    if metric == 'unweighted_unifrac':
        otu_ids, tree, kwargs = _get_phylogenetic_kwargs(counts, **kwargs)
        metric, counts_by_node = _setup_multiple_unweighted_unifrac(
                counts, otu_ids=otu_ids, tree=tree, validate=validate)
        counts = counts_by_node
    elif metric == 'weighted_unifrac':
        # get the value for normalized. if it was not provided, it will fall
        # back to the default value inside of _weighted_unifrac_pdist_f
        normalized = kwargs.pop('normalized',
                                _normalize_weighted_unifrac_by_default)
        otu_ids, tree, kwargs = _get_phylogenetic_kwargs(counts, **kwargs)
        metric, counts_by_node = _setup_multiple_weighted_unifrac(
                counts, otu_ids=otu_ids, tree=tree, normalized=normalized,
                validate=validate)
        counts = counts_by_node
    elif callable(metric):
        metric = functools.partial(metric, **kwargs)
        # remove all values from kwargs, since they have already been provided
        # through the partial
        kwargs = {}
    else:
        # metric is a string that scikit-bio doesn't know about, for
        # example one of the SciPy metrics
        pass

    distances = scipy.spatial.distance.pdist(counts, metric, **kwargs)
    return DistanceMatrix(distances, ids)
