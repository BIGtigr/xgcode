r"""
Plot max mutual information for several selection models and their limits.

The mutation process is site-independent 3-site 2-state-per-site.
"""

from StringIO import StringIO
import math
from itertools import product

import numpy as np
import scipy

import Form
import FormOut
import ctmcmi
import evozoo
import RUtil
from RUtil import mk_call_str

# variable name, description, python object
g_process_triples = [
        ('cube', '3d cube',
            evozoo.Hypercube_2_3_0()),
        ('cycle', 'maximal induced cycle',
            evozoo.Coil_2_3_0()),
        ('path', 'maximal induced path',
            evozoo.Snake_2_3_0()),
        ]

def get_form():
    """
    @return: the body of a form
    """
    check_items = [Form.CheckItem(a, b, True) for a, b, c in g_process_triples]
    return [
            Form.CheckGroup('logs', 'plot process reducibility limits', [
                Form.CheckItem(
                    'log4', 'log(4) cube limit', True),
                Form.CheckItem(
                    'log3', 'log(3) cycle and path limit', True)]),
            Form.CheckGroup(
                'processes', 'plot mutual information', check_items),
            Form.FloatInterval(
                'start_time', 'stop_time', 'divtime interval',
                '0.04', '0.1', low_exclusive=0),
            Form.ImageFormat(),
            ]

def get_form_out():
    return FormOut.Image('plot')

class OptDep:
    def __init__(self, zoo_obj, t, f_info):
        """
        @param zoo_obj: an object from the evozoo module
        @param t: divergence time
        @param f_info: info function that takes a rate matrix and a time
        """
        self.zoo_obj = zoo_obj
        self.t = t
        self.f_info = f_info
    def __call__(self, X):
        """
        @param X: some log ratio probabilities
        @return: neg info value for minimization
        """
        distn = self.zoo_obj.get_distn(X)
        Q = self.zoo_obj.get_rate_matrix(X)
        return -self.f_info(Q, distn, self.t)

def get_response_content(fs):
    f_info = ctmcmi.get_mutual_info_known_distn
    requested_triples = []
    for triple in g_process_triples:
        name, desc, zoo_obj = triple
        if getattr(fs, name):
            requested_triples.append(triple)
    if not requested_triples:
        raise ValueError('nothing to plot')
    # define the R table headers
    headers = ['t']
    if fs.log4:
        headers.append('log.4')
    if fs.log3:
        headers.append('log.3')
    r_names = [a.replace('_', '.') for a, b, c in requested_triples]
    headers.extend(r_names)
    # Spend a lot of time doing the optimizations
    # to construct the points for the R table.
    times = np.linspace(fs.start_time, fs.stop_time, 101)
    arr = []
    for t in times:
        row = [t]
        if fs.log4:
            row.append(math.log(4))
        if fs.log3:
            row.append(math.log(3))
        for python_name, desc, zoo_obj in requested_triples:
            X = np.array([])
            info_value = f_info(
                    zoo_obj.get_rate_matrix(X),
                    zoo_obj.get_distn(X),
                    t)
            row.append(info_value)
        arr.append(row)
    # create the R table string and scripts
    # get the R table
    table_string = RUtil.get_table_string(arr, headers)
    # get the R script
    script = get_ggplot()
    # create the R plot image
    device_name = Form.g_imageformat_to_r_function[fs.imageformat]
    retcode, r_out, r_err, image_data = RUtil.run_plotter(
            table_string, script, device_name)
    if retcode:
        raise RUtil.RError(r_err)
    return image_data

def get_ggplot():
    out = StringIO()
    print >> out, mk_call_str('require', '"reshape"')
    print >> out, mk_call_str('require', '"ggplot2"')
    print >> out, 'my.table.long <-',
    print >> out, mk_call_str('melt', 'my.table', id='"t"')
    print >> out, 'ggplot(data=my.table.long,'
    print >> out, mk_call_str('aes', x='t', y='value', colour='variable')
    print >> out, ') + geom_line()',
    return out.getvalue()

