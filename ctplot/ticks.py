# -*- coding: utf-8 -*-
#    pyplot - python based data plotting tools
#    created for DESY Zeuthen
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# This is a TickLocator implementation for matplotlib according to
# the extended Wilkinson’s Algorithm, see http://vis.stanford.edu/papers/tick-labels

from matplotlib.ticker import Locator
from matplotlib.axis import XAxis
from matplotlib import pyplot
import math
import numpy


def coverage(dmin, dmax, lmin, lmax):
    return 1. - 0.5 * ((dmax - lmax) ** 2 + (dmin - lmin) ** 2) / (0.1 * (dmax - dmin)) ** 2

def coverage_max(dmin, dmax, span):
    drange = dmax - dmin
    if span > drange:
        return 1. - (0.5 * (span - drange)) ** 2 / (0.1 * drange) ** 2
    else:
        return 1.

def density(k, m, dmin, dmax, lmin, lmax):
    r = (k - 1.) / (lmax - lmin)
    rt = (m - 1.) / (max(lmax, dmax) - min(lmin, dmin))
    return 2. - max(r / rt, rt / r)

def density_max(k, m):
    if k >= m:
        return 2. - (k - 1.0) / (m - 1.0)
    else:
        return 1.


def simplicity(q, Q, j, lmin, lmax, lstep):
    eps = 1e-10
    n = len(Q)
    i = Q.index(q) + 1
    v = 0
    if ((lmin % lstep) < eps) or ((((lstep - lmin) % lstep) < eps) and (lmin <= 0) and (lmax >= 0)):
        v = 1
    else:
        v = 0

    return (n - i) / (n - 1.0) + v - j

def simplicity_max(q, Q, j):
    n = len(Q)
    i = Q.index(q) + 1
    v = 1
    return (n - i) / (n - 1.0) + v - j

def legibility(lmin, lmax, lstep):
    return 1.

def score(weights, simplicity, coverage, density, legibility):
   return weights[0] * simplicity + weights[1] * coverage + weights[2] * density + weights[3] * legibility

def wilk_ext(dmin, dmax, m, only_inside = 0,
             Q = [1, 5, 2, 2.5, 4, 3],
             w = [0.2, 0.25, 0.5, 0.05]):

    if (dmin >= dmax) or (m < 1):
        return (dmin, dmax, dmax - dmin, 1, 0, 2, 0)

    n = float(len(Q))
    best_score = -1.0
    result = None

    j = 1.0
    while (j < numpy.inf):
        for q in map(float, Q):
            sm = simplicity_max(q, Q, j)

            if score(w, sm, 1, 1, 1) < best_score:
                j = numpy.inf
                break

            k = 2.
            while k < numpy.inf:
                dm = density_max(k, m)

                if score(w, sm, 1, dm, 1) < best_score:
                    break

                delta = (dmax - dmin) / (k + 1.) / j / q
                z = math.ceil(math.log10(delta))

                while z < numpy.inf:
                    step = j * q * 10.**z
                    cm = coverage_max(dmin, dmax, step * (k - 1.))

                    if score(w, sm, cm, dm, 1) < best_score:
                        break

                    min_start = math.floor(dmax / step) * j - (k - 1.) * j
                    max_start = math.ceil(dmin / step) * j

                    if min_start > max_start:
                        z += 1
                        break

                    for start in numpy.arange(min_start, max_start + 1):
                        lmin = start * (step / j)
                        lmax = lmin + step * (k - 1.0)
                        lstep = step

                        s = simplicity(q, Q, j, lmin, lmax, lstep)
                        c = coverage(dmin, dmax, lmin, lmax)
                        d = density(k, m, dmin, dmax, lmin, lmax)
                        l = legibility(lmin, lmax, lstep)
                        scr = score(w, s, c, d, l)

                        if (scr > best_score) and \
                           ((only_inside <= 0) or ((lmin >= dmin) and (lmax <= dmax))) and \
                           ((only_inside >= 0) or ((lmin <= dmin) and (lmax >= dmax))):
                            best_score = scr
                            # print "s: %5.2f c: %5.2f d: %5.2f l: %5.2f" % (s,c,d,l)
                            result = (lmin, lmax, lstep, j, q, k, scr)

                    z += 1
                # end of z-while-loop
                k += 1
            # end of k-while-loop
        j += 1
    # end of j-while-loop
    return result

def get_ticks(dmin, dmax, m, **kwargs):
    lmin, lmax, lstep, j, q, k, scr = wilk_ext(dmin, dmax, m, **kwargs)
    return numpy.arange(lmin, lmax + lstep, lstep)

class ExtendedWilkinsonTickLocator(Locator):
    """
        places the ticks according to the extended Wilkinson algorithm
        (http://vis.stanford.edu/files/2010-TickLabels-InfoVis.pdf)

        **Parameters:**
            *target_density* : [ float ]
                controls the number of ticks. The algorithm will try
                to put as many ticks on the axis but deviations are 
                allowed if another criterion is considered more important.
                
            *only_inside* : [ int ]
                controls if the first and last label include the data range.
                0  : doesn't matter
                >0 : label range must include data range
                <0 : data range must be larger than label range 

            *per_inch* : if per_inch=True then it specifies the number of ticks per
                inch instead of a fixed number, so the actual number of
                ticks depends on the size of the axis
                
            *Q* : [ list of numbers ]
                numbers that are considered as 'nice'. Ticks will be
                multiples of these
            
            *w* : [ list of numbers ]
                list of weights that control the importance of the four
                criteria: simplicity, coverage, density and legibility
            
                see the reference for details
    """
    def __init__(self, target_density, only_inside = 0, per_inch = False,
                 Q = [1, 5, 2, 2.5, 4, 3],
                 w = [0.2, 0.25, 0.5, 0.05]):


        self.target_density = target_density
        self.only_inside = only_inside
        self.Q = Q
        self.w = w
        self.per_inch = per_inch

    def __call__(self):
        vmin, vmax = self.axis.get_view_interval()
        if vmax < vmin:
            vmin, vmax = vmax, vmin

        # determine "physical" size of the axis and according # of ticks
        if self.per_inch:
            i = 0 if isinstance(self.axis, XAxis) else 1
            axes = self.axis.get_axes()
            pos = axes.get_position()
            size = axes.get_figure().get_size_inches()
            inches = size[i] * pos.bounds[i + 2]
            nticks = self.target_density * inches
        else:
            nticks = self.target_density

        return get_ticks(vmin, vmax, nticks, only_inside = self.only_inside, Q = self.Q, w = self.w)

def set_extended_locator(density = 1, per_inch = True, **kwargs):
    'set the ExtendedWilkinsonTickLocator on current x- and y-axis'
    ca = pyplot.gca()
    ca.xaxis.set_major_locator(ExtendedWilkinsonTickLocator(target_density = density, per_inch = per_inch, **kwargs))
    ca.yaxis.set_major_locator(ExtendedWilkinsonTickLocator(target_density = density, per_inch = per_inch, **kwargs))
