"""
Preprocessing functions.
Functions to preprocess the data before running any method. 
"""

import numpy as np
from scipy.sparse import csr_matrix, lil_matrix
import pandas as pd

from anndata import AnnData


def extract(mat, use_raw=True, dtype=np.float32):
    """
    Processes different input types so that they can be used downstream. 
    
    Parameters
    ----------
    mat : list, pd.DataFrame or AnnData
        List of [matrix, samples, features], dataframe (samples x features) or an AnnData
        instance.
    use_raw : bool
        Use `raw` attribute of `adata` if present.
    dtype : type
        Type of float used.
    
    Returns
    -------
    m : sparse matrix
    r : array of samples
    c : array of features
    """
    
    if type(mat) is list:
        m, r, c = mat
        m = csr_matrix(m)
        r = np.array(r)
        c = np.array(c)
    elif type(mat) is pd.DataFrame:
        m = csr_matrix(mat.values)
        r = mat.index.values
        c = mat.columns.values
    elif type(mat) is AnnData:
        if use_raw:
            if mat.raw is None:
                raise ValueError("Received `use_raw=True`, but `mat.raw` is empty.")
            m = mat.raw.X
            c = mat.raw.var.index.values
        else:
            m = csr_matrix(mat.X)
            c = mat.var.index.values
        r = mat.obs.index.values
            
    else:
        raise ValueError("""mat must be a list of [matrix, samples, features], 
        dataframe (samples x features) or an AnnData instance.""")
    
    # Sort genes
    msk = np.argsort(c)
    
    return m[:,msk].astype(dtype), r, c[msk]


def filt_min_n(c, net, min_n=5):
    """
    Filter sources of a net with less than min_n targets.
    
    Parameters
    ----------
    c : narray
        Column names of `mat`.
    net : pd.DataFrame
        Network in long format.
    min_n : int
        Minimum of targets per source. If less, sources are removed.
    
    Returns
    -------
    net : Filtered net.
    """
    
    # Find shared targets between mat and net
    msk = np.isin(net['target'], c)
    
    # Count unique sources
    sources, counts = np.unique(net[msk]['source'].values, return_counts=True)
    
    # Find sources with more than min_n targets
    msk = np.isin(net['source'], sources[counts >= min_n])
    
    return net[msk]


def match(mat, c, r, net):
    """
    Match expression matrix with a regulatory adjacency matrix.
    
    Parameters
    ----------
    mat : csr_matrix
        Gene expression matrix.
    c : narray
        Column names of `mat`.
    r : narray
        Row  names of `net`.
    net : csr_matrix
        Regulatory adjacency matrix.
    
    Returns
    -------
    regX : Matching regulatory adjacency matrix.
    """
    
    # Init empty regX
    regX = lil_matrix((c.shape[0], net.shape[1]))
    
    # Match genes from mat, else are 0s
    for i in range(c.shape[0]):
        for j in range(r.shape[0]):
            if c[i] == r[j]:
                regX[i] = net[j]
                break
    
    return csr_matrix(regX)


def rename_net(net, source='source', target='target', weight='weight'):
    """
    Renames input network to match decoupleR's format (source, target, weight).
    
    Parameters
    ----------
    net : pd.DataFrame
        Network in long format.
    source : str
        Column name where to extract source features.
    target : str
        Column name where to extract target features.
    weight : str
        Column name where to extract features' weights. 
    
    Returns
    -------
    net : Renamed pd.DataFrame network.
    """
    
    # Check if names are in columns
    msg = 'Column name "{0}" not found in net. Please specify a valid column.'
    assert source in net.columns, msg.format(source)
    assert target in net.columns, msg.format(target)
    if weight is not None:
        assert weight in net.columns, msg.format(weight)
    else:
        import sys
        print("weight column not provided, will be set to 1s.", file=sys.stderr) 
        net = net.copy()
        net['weight'] = 1.0
        weight = 'weight'
    
    # Rename
    net = net.rename(columns={source: 'source', target: 'target', weight: 'weight'})
    # Sort
    net = net.reindex(columns=['source', 'target', 'weight'])
    
    return net


def get_net_mat(net):
    """
    Transforms a given network to an adjacency matrix (target x source).
    
    Parameters
    ----------
    net : pd.DataFrame
        Network in long format.
    
    Returns
    -------
    sources : Array of source names.
    targets : Array of target names.
    X : Matrix of interactions bewteen sources and targets (target x source).
    """

    # Pivot df to a wider format
    X = net.pivot(columns='source', index='target', values='weight')
    X[np.isnan(X)] = 0

    # Store node names and weights
    sources = X.columns.values
    targets = X.index.values
    X = X.values
    
    return sources, targets, X