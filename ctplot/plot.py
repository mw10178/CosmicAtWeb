#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, re, json, tables, ticks, time, logging
from tempfile import gettempdir
from os import path
from collections import OrderedDict, namedtuple
from itertools import chain
import numpy as np
import numpy.ma as ma
from scipy.optimize import curve_fit
import matplotlib as mpl
import matplotlib.pyplot as plt
from utils import get_args_from, isseq, set_defaults, number_mathformat, number_format, hashargs, noop
from itertools import product
from locket import lock_file
from datetime import datetime
import dateutil.parser

from i18n import _
from safeeval import safeeval

logging.basicConfig(level = logging.DEBUG, format = '%(filename)s:%(funcName)s:%(lineno)d:%(message)s')

log = logging.getLogger('plot')

# override eval by safe version
eval = safeeval()


TableSpecs = namedtuple('TableSpecs', ('title', 'colnames', 'units', 'rows'))

# Helper function to format the timestamps in tables.
def format_time(timestamp):
    #return (datetime.fromtimestamp(starttime+timestamp).isoformat())
    starttime = dateutil.parser.parse("2004-01-01T00:00:00+0000")
    starttime = time.mktime(starttime.timetuple())
    return datetime.fromtimestamp(starttime+timestamp)

def available_tables(d = os.path.dirname(__file__) + '/data'):
    files = []
    dirlen = len(d)
    for p, d, f in os.walk(d):
        for ff in f:
            files.append(path.join(p, ff))
    files = map(lambda f:f.replace('\\', '/'), files)
    files = filter(lambda f:f.lower().endswith('.h5'), files)
    files.sort()

    tabs = OrderedDict()

    for f in files:
        try:
            h5 = tables.openFile(f, 'r')
            for n in h5.walkNodes(classname = 'Table'):
                tab = f[dirlen+1:] + ':' + n._v_pathname
                tabs[tab] = TableSpecs(n._v_title, n.colnames, json.loads(n.attrs.units), int(n.nrows))
            h5.close()
        except:
            pass

    return tabs


def _get(d, k, default = None):
    v = d.get(k)
    if v:
        return v.strip() if isinstance(v, str) else v
    else:
        return default

def get_binning(bins, data):
    if np.isscalar(bins):
        edges = np.linspace(np.nanmin(data), np.nanmax(data), bins + 1)
    elif isseq(bins) and len(bins) == 3:
        edges = np.linspace(bins[0], bins[1], bins[2] + 1)
    else:
        edges = np.array(bins)

    centers = (edges[1:] + edges[:-1]) / 2
    assert len(centers) == len(edges) - 1
    widths = np.diff(edges)
    return edges, centers, widths


def get_cumulative(bincontents, binerrors, cumulative = 0, binwidths = 1):
    cumulative = float(cumulative)
    if cumulative > 0:
        bincontents = np.cumsum(bincontents * binwidths)
        binerrors = np.sqrt(np.cumsum((binerrors * binwidths) ** 2))
    elif cumulative < 0:
        bincontents = np.sum(bincontents * binwidths) - np.cumsum(bincontents * binwidths)
        binerrors = np.sqrt(np.sum((binerrors * binwidths) ** 2) - np.cumsum((binerrors * binwidths) ** 2))

    return bincontents, binerrors


def get_density(bincontents, binerrors, binwidths):
    f = 1.0 / (np.sum(bincontents) * binwidths)
    bincontents = f * bincontents
    bincontents[np.logical_not(np.isfinite(bincontents))] = 0
    binerrors = f * binerrors
    return bincontents, binerrors


def get_density2d(bincontents, xwidths, ywidths):
    f = 1.0 / (np.sum(bincontents) * (xwidths * ywidths.reshape(len(ywidths), 1)))
    bincontents = f * bincontents
    bincontents[np.logical_not(np.isfinite(bincontents))] = 0
    return bincontents


def get_step_points(bincontents, binedges):
    assert len(bincontents) + 1 == len(binedges)
    x = np.zeros(2 * len(binedges), dtype = float)
    y = np.zeros(x.shape, dtype = float)
    x[::2] = binedges
    x[1::2] = binedges
    y[1:-1:2] = bincontents
    y[2:-1:2] = bincontents
    assert len(x) == len(y) == 2 * len(binedges)
    return x, y


def adjust_limits(xy, data, limits = None, marl = 0.05, maru = 0.05):
    assert xy in ('x', 'y')
    lim = getattr(plt, xy + 'lim')
    if limits is None:
        limits = lim()
    mi, ma = limits
    data = data[np.isfinite(data)]
    mind = np.min(data)
    maxd = np.max(data)
    span = maxd - mind
    lim(min(mi, min(data) - marl * span), max(ma, max(data) + maru * span))

def sproduct(a, b):
    for x, y in product(a, b):
        yield '{}{}'.format(x, y)





text_poss = map(np.array, [(1, -1), (-1, -1), (-1, 1), (1, 1), (0.5, -1), (-1, 0.5), (0.5, 1), (1, 0.5)])
text_algn = [('left', 'top'), ('right', 'top'), ('right', 'bottom'), ('left', 'bottom'), ('center', 'top'), ('right', 'center'), ('center', 'bottom'), ('left', 'center')]
stats_abrv = {'n':'N', 'u':'uflow', 'o':'oflow', 'm':'mean', 's':'std', 'p':'mode', 'e':'median', 'w':'skew', 'k':'kurtos', 'x':'excess', 'c':'cov'}




class Plot(object):
    def __init__(self, config , **kwargs):
        log.debug('config %s', json.dumps(config))
        log.debug('settings %s', json.dumps(kwargs))

        self.config = config

        # configure plot according too kwargs
        # all options are strings
        for N in xrange(10):
            n = str(N)

            # x, y, z, cut, mode, source, name
            # x = expression plotted on x-axis
            # y = expression plotted on y-axis
            # z = expression plotted on z-axis (as color of line/markers)
            # c = cut expression, discard data point for which this is False (if given)
            # s = HDF5 sourcefile and table
            # n = name of the plot, used in legend
            for v in 'xyzcmsn':
                self._append(v, _get(kwargs, v + n))

            # twin axes
            self._append('tw', _get(kwargs, 'tw' + n))

            # window, shift, condition for the rate calculation
            self._append('rw', _get(kwargs, 'rw' + n))
            self._append('rs', _get(kwargs, 'rs' + n, '1'))
            self._append('rc', _get(kwargs, 'rc' + n, '1'))

            # statsbox
            self._append('sb', _get(kwargs, 'sb' + n, 'nmsc'))

            # fit function
            self._append('ff', _get(kwargs, 'ff' + n))
            self._append('fp', _get(kwargs, 'fp' + n))
            self._append('fl', _get(kwargs, 'fl' + n))

            # x-, y- and z-adjustment expression
            for v, w in product('xyz', 'a'):
                self._append(v + w, _get(kwargs, v + n + w))

            # x- and y-binnings for histograms/profile
            for v, w in product('xy', 'b'):
                self._append(v + w, _get(kwargs, v + n + w))

            # plot options
            for k, v in kwargs.iteritems():
                if k.startswith('o' + n) and v:
                    a = 'o' + k[2:]
                    if not hasattr(self, a):
                        setattr(self, a, 10 * [None])
                    getattr(self, a)[N] = v.strip()

        # range, scale, label
        for v in sproduct('xyz', 'rsl'):
            setattr(self, v , _get(kwargs, v))
        for v in sproduct('xyz', 'rsl'):
            setattr(self, v + 'tw', _get(kwargs, v + 'tw'))


        # title, fontsize, width,height, grid, legend
        for v in 'tfwhgl':
            setattr(self, v, _get(kwargs, v))

        # source with rate averaging
        for i, s in enumerate(self.s):
            self._append('sr', '{}:{}:{}:{}'.format(path.join(config['datadir'], s), self.rw[i], self.rs[i], self.rc[i]) if s else None)

        self.legend = []
        self.textboxes = []
        self.fitboxes = []

        self.progress = 0  # reaching from 0 to 1

        self.axes = OrderedDict()




    def _append(self, varname, value):
        'append value to self.varname'
        try:
            getattr(self, varname).append(value)
        except AttributeError:
            setattr(self, varname, [value])


    def _get(self, var, default = None, dtype = lambda x:x):
        val = getattr(self, var)
        if val is None:
            return default
        else:
            return dtype(val)


    def _prepare_data(self):
        # create dict: source --> all expr for this source
        # prefilled with empty lists
        expr_data = {}
        expr_data_new = {}
        joined_cuts = {}  # OR of all cuts
        for n, s in enumerate(self.sr):
            if s:
                if s not in expr_data:
                    expr_data[s] = {}  #  add dict for every unique source s (plot n)
                for v in ['x', 'y', 'z', 'c', 'xa', 'ya', 'za']:
                    expr = getattr(self, v)[n]  # x/y/z/c expression for source s (plot n)
                    log.debug('{}{}, expr: {}'.format(v, n, expr))
                    if expr:
                        expr_data[s][expr] = []
                        expr_data_new[expr] = []
                    if v == 'c':
                        if s in joined_cuts:
                            joined_cuts[s] = '{} or ({})'.format(joined_cuts[s], expr)
                        else:
                            joined_cuts[s] = '({})'.format(expr)

        for s in joined_cuts.keys():
            if '(None)' in joined_cuts[s]: del joined_cuts[s]
        log.debug('joined_cuts = {}'.format(joined_cuts))



        # loop over tables and fill data lists in expr_data
        units = {}
        self._get_data(expr_data, joined_cuts, units)
        log.debug(units)


        # assing data arrays to x/y/z/c-data fields
        for v in ['x', 'y', 'z', 'c', 'xa', 'ya', 'za']:
            log.debug(getattr(self,v))
            for i, x in enumerate(getattr(self, v)):
                if (x):
                    log.debug(x)
                    if (x == "tsec"):
                        log.debug("expression is time!!")
                        log.debug("what's that1?: {}".format(expr_data[self.sr[i]]))
                        log.debug("what's that?: {}".format(expr_data[self.sr[i]][x]))
                        #for kk, k in enumerate(expr_data[self.sr[i]][x]):
                            #log.debug("data at {}: {}".format(kk, k))
                        starttime = 0
                        for j, timestamp in enumerate(expr_data[self.sr[i]][x]):
                            if not (np.isnan(timestamp)):
                                expr_data_new[x].append(format_time(timestamp))
                            else:
                                expr_data_new[x].append(nan)

            for i, x in enumerate(getattr(self, v)):
                if (x and self.sr[i]):
                    if (x == "tsec"):
                        log.debug('testtestestestse')
                        log.debug(expr_data_new[x])
                        setattr(self, v + 'data', [(expr_data_new[x])])
                    else:
                        setattr(self, v + 'data', [(expr_data[self.sr[i]][x])])
                if (all(v is None for v in getattr(self, v))):
                    setattr(self, v + 'data', [None])


                #if (x == "tsec"):
                #    setattr(self, v + 'data', [(expr_data_new[x] if x and self.sr[i] else None) for i, x in enumerate(getattr(self, v))])
                #else:
                #    setattr(self, v + 'data', [(expr_data[self.sr[i]][x] if x and self.sr[i] else None) for i, x in enumerate(getattr(self, v))])

            #setattr(self, v + 'data', [(expr_data_new[x] if x and self.sr[i] else None) for i, x in enumerate(getattr(self, v))])
            #setattr(self, v + 'data', np.array([(expr_data_new[x] if x and self.sr[i] else None) for i, x in enumerate(getattr(self, v))]))
            #setattr(self, v + 'data', [(expr_data[self.sr[i]][x] if x and self.sr[i] else None) for i, x in enumerate(getattr(self, v))])
            setattr(self, v + 'unit', [(units[self.sr[i]][x] if x and self.sr[i] else None) for i, x in enumerate(getattr(self, v))])

        log.debug('source={}'.format(self.s))
        log.debug('srcavg={}'.format(self.sr))
        for v in ['x', 'y', 'z', 'c', 'xa', 'ya', 'za']:
            log.debug(' {}data {}'.format(v, [len(x) if x is not None else None for x in getattr(self, v + 'data')]))
#            log.debug(' {}unit {}'.format(v, [x for x in getattr(self, v + 'unit')]))





    def _get_data(self, expr_data, filters, units = {}):
        # evaluate expressions for each source
        for s, exprs in expr_data.iteritems():
            log.debug('processing source {}'.format(s))
            log.debug('      expressions {}'.format(exprs.keys()))
            log.debug('           filter {}'.format(filters[s] if s in filters else None))
            progr_prev = self.progress

            # source s has form 'filename:/path/to/table'
            # open HDF5 table
            ss = s.strip().split(':')
            with tables.openFile(ss[0], 'r') as h5:
                table = h5.getNode(ss[1])
                window = float(eval(ss[2])) if ss[2] != 'None' else None
                shift = float(ss[3]) if ss[3] != 'None' else 1
                weight = ss[4] if ss[4] != 'None' else None

                progr_factor = 1.0 / table.nrows / len(expr_data)

                table_units = tuple(json.loads(table.attrs.units))

                def unit(var):
                    try:
                        return table_units[table.colnames.index(var.strip())]
                    except:
                        return '?'

                units[s] = dict([(e, unit(e)) for e in exprs.keys()])


                def compile_function(x):
                    fields = set(table.colnames)
                    fields.add('rate')
                    fields.add('count')
                    fields.add('weight')
                    for v in fields:  # map T_a --> row['T_a'], etc.
                        x = re.sub('(?<!\\w)' + re.escape(v) + '(?!\\w)',
                                    'row["' + v + '"]', x)
                    return eval('lambda row: ({})'.format(x))


                # compile the expressions
                exprs = dict([(compile_function(e), d) for e, d in exprs.iteritems()])

                def average():
                    # look if there is data for this source in the cache
                    cachedir = self.config['cachedir'] or gettempdir()
                    cachefile = os.path.join(cachedir, 'avg{}.h5'.format(hashargs(s)))
                    cachefile = os.path.abspath(cachefile)
                    log.debug('cachefile %s', cachefile)


                    def average_cached():
                        if not self.config['cachedir']:
                            raise  # always fail it cache is disabled
                        with tables.openFile(cachefile) as cacheh5:
                            cachetable = cacheh5.getNode('/data')
                            progr_factor = 1.0 / cachetable.nrows / len(expr_data)
                            log.info('reading averaged data from cache')
                            for row in cachetable.iterrows():
                                self.progress = progr_prev + row.nrow * progr_factor
                                yield row


                    def average_computed():
                        try:
                            log.debug('creating averaged data cachefile')
                            cacheh5 = tables.openFile(cachefile, 'w')
                        except:
                            log.exception('failed opening %s', cachefile)
                            raise RuntimeError('cache for {} in use or corrupt, try again in a few seconds'.format(s))

                        with cacheh5:
                            # use tables col descriptor and append fields rate and count
                            log.debug('caching averaged data')
                            coldesc = OrderedDict()  # keep the order
                            for k in table.colnames:
                                d = table.coldescrs[k]
                                if isinstance(d, tables.BoolCol):  # make bool to float for averaging
                                    coldesc[k] = tables.FloatCol(pos = len(coldesc))
                                else:
                                    coldesc[k] = d
                            coldesc['count'] = tables.IntCol(pos = len(coldesc))
                            coldesc['weight'] = tables.FloatCol(pos = len(coldesc))
                            coldesc['rate'] = tables.FloatCol(pos = len(coldesc))
                            cachetable = cacheh5.createTable('/', 'data', coldesc, 'cached data')
                            cachetable.attrs.source = s
                            cacherow = cachetable.row

                            assert 0 < shift <= 1
                            it = table.colnames.index('time')  # index of time column
                            ta = table[0][it]  # window left edge
                            tb = ta + window  # window right edge
                            wd = []  # window data
                            cols = table.colnames
                            wdlen = len(cols) + 1
                            fweight = compile_function(weight)

                            def append(r):
                                wd.append(np.fromiter(chain(r[:], [fweight(r)]), dtype = np.float, count = wdlen))

                            progr_factor = 1.0 / table.nrows / len(expr_data)

                            for row in table.iterrows():
                                if row[it] < tb:  # add row if in window
                                    append(row)
                                else:  # calculate av and shift window
                                    n = len(wd)
                                    if n > 0:
                                        wdsum = reduce(lambda a, b: a + b, wd)
                                        for i, c in enumerate(cols):
                                            cacherow[c] = wdsum[i] / n
                                        cacherow['time'] = (ta + tb) * 0.5  # overwrite with interval center
                                        cacherow['count'] = n
                                        cacherow['weight'] = wdsum[-1] / n
                                        cacherow['rate'] = n / window
                                        self.progress = progr_prev + row.nrow * progr_factor
                                        yield cacherow
                                        cacherow.append()

                                    ta += shift * window  # shift window
                                    tb = ta + window
                                    if row[it] >= tb:
                                        ta = row[it]  # shift window
                                        tb = ta + window

                                    if shift == 1:  # windows must be empty
                                        wd = []
                                    else:  # remove data outside new window
                                        wd = filter(lambda x: ta <= x[it] < tb, wd)
                                    append(row)

                        if not self.config['cachedir']:
                            log.debug('removing averaged data cachefile')
                            os.remove(cachefile)



                    try:  # try using data from cache
                        for x in average_cached(): yield x
                    except:  # if cache fails
                        with lock_file(cachefile + '.lock'):
                            try:  # try cache again (maybe it was populated while waiting for the lock)
                                for x in average_cached(): yield x
                            except:  # if it fails again, compute the data
                                for x in average_computed(): yield x



                def prefilter(data, filterexpr):
                    filterexpr = compile_function(filterexpr)
                    for row in data:
                        if filterexpr(row):
                            yield row


                def updateProgress(row, fac):
                    self.progress = progr_prev + row.nrow * fac

                if window:
                    tableiter = average()
                    updateProgress = noop  # progress update is done inside average()
                else:
                    tableiter = table.iterrows()

                if s in filters:
                    tableiter = prefilter(tableiter, filters[s])

                for row in tableiter:
                    for expr, data in exprs.iteritems():
                        data.append(expr(row))
                    if row.nrow % 10000 == 0: updateProgress(row, progr_factor)

                # convert data lists to numpy arrays
                d = expr_data[s]
                for k in d.keys():
                    d[k] = np.array(d[k])

        # done with getting data
        self.progress = 1


    __tick_density = 1.5


    def _configure_pre(self):
        # configure plotlib
        plt.clf()
        plt.close('all')
        self.f = self._get('f', 10, float)
        if 'map' in self.m: self.f *= 0.8  # smaller font if plotting map
        plt.rc('font', **{'family':'sans-serif', 'sans-serif':['Dejavu Sans'], 'size':self.f})
        # plt.rc('axes', grid = True)
        plt.rc('lines', markeredgewidth = 0)
        w = self._get('w', 25, float)
        h = self._get('h', w / np.sqrt(2), float)
        # convert cm to inches
        w = w / 2.54
        h = h / 2.54
        self.w = w
        self.h = h
        plt.gcf().set_size_inches([w, h], forward = True);
#        f = 0.09
#        if 'map' in self.m: f = 0.06 # more margin if plotting map
#        plt.gca().set_position([f, f, 1 - 2 * f, 1 - 2 * f])
#        plt.subplots_adjust(left = f, bottom = f, right = 1 - f, top = 1 - f, wspace = 0, hspace = 0)
        ticks.set_extended_locator(self.__tick_density)
        if (getattr(self, "xunit")[0] == 's'):
            myFmt = mpl.dates.DateFormatter('%H:%M %d.%m.%Y')
            plt.gca().xaxis.set_major_formatter(myFmt)
        self.axes[''] = plt.gca()



    def _configure_post(self):
        plt.axes(self.axes[''])  # activate main axes

        # title
        if self.t: plt.title(self.t, fontsize = 1.4 * self.f)

        if 'map' in self.m: return

        # settings for main and twin axes
        for v, ax in self.axes.iteritems():
            # rotating the x labels for better readability
            plt.setp(ax.get_xticklabels(), rotation=30, horizontalalignment="right")
            plt.axes(ax)

            # grid
            plt.grid(which = 'major', axis = v or 'both', linestyle = '--' if v else '-', color = 'k', alpha = 0.4)
            plt.grid(which = 'minor', axis = v or 'both', linestyle = '-.' if v else ':', color = 'k', alpha = 0.4)

            # set labels, scales and ranges
            for a in 'xy':
                if v and a != v: continue  # on twins, set only axis
                getattr(plt, '{}label'.format(a))(self.alabel(a, v))  # label
                s = getattr(self, a + 's' + ('tw' if a == v else ''))
                if s:  # scale
                    getattr(plt, '{}scale'.format(a))(s)
                r = getattr(self, a + 'r' + ('tw' if a == v else ''))
                if r:  # range (limits)
                    rmin, rmax = r.split(',')
                    rlim = getattr(plt, '{}lim'.format(a))
                    # defaults
                    rmind, rmaxd = rlim()
                    # set range
                    try:
                        rmin = rmind if rmin == '' else float(rmin)
                        rmax = rmaxd if rmax == '' else float(rmax)
                        log.debug('rmin={}, rmax={}'.format(rmin, rmax))
                        rlim(rmin, rmax)
                    except ValueError:
                        # ignore if input is no float
                        pass

        # legend
        plt.axes(self.axes.values()[-1])  # activate last added axes
        if self.l != 'none' and 'map' not in self.m :
            lines = [v[0] for v in self.legend]
            labels = [v[1] for v in self.legend]
            leg = plt.legend(lines, labels, loc = self.l or 'best', fancybox = True, numpoints = 1)
            plt.setp(leg.get_texts(), fontsize = self.f)
            leg.get_frame().set_alpha(0.8)

        # get plot size to position textboxes
        fig = plt.gcf()
        sx, sy = fig.get_size_inches() * fig.dpi

        # draw textboxes
        cxw = 0
        cx = sx

        # add offset if we have a second y-axis
        for tw in self.tw:
            if tw == 'y':
                cx += 50
                break

        # add offset if we have a z-axis
        # only if offset hasn't been added yet
        if cx == sx:
            for z in self.z:
                if z != None:
                    cx += 50
                    break

        cy = sy
        for i, t in enumerate(self.textboxes):
            label = plt.annotate(t, (cx, cy), xycoords = 'axes pixels',
                family = 'monospace', size = 'small',
                horizontalalignment = 'left', verticalalignment = 'top',
                bbox = dict(facecolor = 'w', alpha = 0.8, boxstyle = "round,pad=0.5"),
                annotation_clip = False)
            extents = label.get_window_extent(fig.canvas.get_renderer()).extents
            w = extents[2] - extents[0]
            if w > cxw:
                cxw = w
            cy -= sy * 0.25

        # draw fitboxes
        cx = cxw + cx + 50 if len(self.textboxes) else cx
        cy = sy
        for i, t in enumerate(self.fitboxes):
            plt.annotate(t, (cx, cy), xycoords = 'axes pixels',
                family = 'monospace', size = 'small',
                horizontalalignment = 'left', verticalalignment = 'top',
                bbox = dict(facecolor = 'w', alpha = 0.8, boxstyle = "round,pad=0.5"),
                annotation_clip = False)
            cy -= sy * 0.25


    def data(self, i):
        x, y, z, c = self.xdata[i], self.ydata[i], self.zdata[i], self.cdata[i]
        xa, ya, za = self.xadata[i], self.yadata[i], self.zadata[i]

        if xa is not None:
            x = xa
        if ya is not None:
            y = ya
        if za is not None:
            z = za
        if c is not None and len(c) > 0:
            if x is not None: x = x[c]
            if y is not None: y = y[c]
            if z is not None: z = z[c]
        return x, y, z


    def opts(self, i):
        o = {}
        for k, v in self.__dict__.iteritems():
            if k.startswith('o') and v[i] is not None:
                log.debug('v[{}]={}'.format(i, v[i]))
                log.debug('k[]={}'.format(k))
                try:
                    o[k[1:]] = float(v[i])
                except:
                    o[k[1:]] = v[i]
        return o


    def bins(self, i, a):
        try:
            b = getattr(self, a + 'b')[i]
            if b:
                bn = b.split(',')
                if len(bn) == 1:
                    return float(bn[0])
                return tuple([float(x) for x in bn])
            else:
                raise
        except:
            return 0



    def llabel(self, i):
        l = self.n[i]
        if l: return l
        l = ''
        for v in 'xyzc':
            w = getattr(self, v)[i]
            if w: l += u':{}'.format(w)
        return l[1:]


    def alabel(self, a, t = ''):
        l = getattr(self, a + ('ltw' if t == a else 'l'))
        if l:
            return l

        l = u''
        exprs = getattr(self, a)
        units = getattr(self, a + 'unit')
        adjust_funcs = getattr(self, a + 'a')
        for i, x in enumerate(exprs):
            if t and self.tw[i] != a: continue
            if not t and self.tw[i] == a: continue
            if x:
                if x not in l:
                    l += u', {} [{}]'.format(x, units[i])
                if adjust_funcs[i]:
                    l += u' ({})'.format(adjust_funcs[i])

        return l[2:]


    def plot(self):
        self._prepare_data()
        self._configure_pre()
        for i, m in enumerate(self.m):
            if m and self.s[i]:
                self.selectAxes(i)
                if m == 'xy':
                    self._xy(i)
                elif m == 'h1':
                    self._hist1d(i)
                elif m == 'h2':
                    self._hist2d(i)
                elif m == 'p':
                    self._profile(i)
                elif m == 'map':
                    self._map(i)
                else:
                    raise RuntimeError('unknow mode ' + m)
        self._configure_post()


    def show(self):
        log.debug('showing plot in interactive mode')
        if not any(self.legend):
            self.plot()
        plt.show()


    def save(self, name = 'fig', extensions = ('png', 'pdf')):
        plt.ioff()
        if not any(self.legend):
            self.plot()
        names = []
        for ext in extensions:
            n = name + '.' + ext
            log.debug('saving plot to %s', n)
            plt.savefig(n, bbox_inches = 'tight', pad_inches = 0.5 if 'map' in self.m else 0.1, transparent = False)
            names.append(n)

        return dict(zip(extensions, names))


    __twin = {'x':plt.twiny, 'y':plt.twinx}

    def selectAxes(self, i):
        plt.axes(self.axes[''])  # activate main axes
        v = self.tw[i]
        if v and v in 'xy':
            if v in self.axes:
                plt.axes(self.axes[v])  # activate twin x/y axes
            else:
                self.axes[v] = self.__twin[v]()  # create twin x/y axes
                ticks.set_extended_locator(self.__tick_density)  # add tick locator
            return



    def fit(self, i, x, y, yerr = None):
        ff = self.ff[i]
        if ff:
            ff = ff.replace(' ', '')
            log.info('fitting function {}'.format(ff))
            fitfunc = eval('lambda x,*p:' + ff)
            x, y = np.array(x), np.array(y)
            m = np.logical_and(np.isfinite(x), np.isfinite(y))
            if yerr is not None:
                yerr = np.array(yerr)
                m = np.logical_and(m, np.isfinite(yerr))
                yerr = yerr[m]
            x , y = x[m], y[m]

            # gather fit parameters
            p = tuple([float(fp) for fp in self.fp[i].split(',')])
            try:
                p, c = curve_fit(fitfunc, x, y, p, yerr)
                log.info('parameters = {}'.format(p))
                log.info('covariance = {}'.format(c))
                fit_status = ''
            except Exception as e:
                fit_status = ' (failed: {})'.format(e)
                c = None
                log.exception('fit failed')

            # plot fit result
            xfit = np.linspace(np.nanmin(x), np.nanmax(x), 1000)
            yfit = fitfunc(xfit, *p)
            args = [xfit, yfit]
            if self.fl[i]: args.append(self.fl[i])
            l, = plt.plot(*args)

            N = len(x)
            chi2 = fitfunc(x, *p) - y
            if yerr is not None:
                chi2 = chi2 / yerr
            chi2 = (chi2 ** 2).sum()

            # add textbox
            t = 'y=' + ff
            t += '\n$\\chi^2$/N = {}/{}'.format(number_mathformat(chi2), number_mathformat(N))
            for k, v in enumerate(p):
                try:
                    t += '\np[{}] = {}$\\pm${}'.format(k, number_mathformat(v), number_mathformat(np.sqrt(c[k, k])))
                except:
                    t += '\np[{}] = {}$\\pm${}'.format(k, v, c)
            self.fitboxes.append(t)
            ll = ('Fit' + fit_status + ' y=' + ff)
            for k, v in  enumerate(p):
                ll = ll.replace('p[{}]'.format(k), number_mathformat(v, 3))
            self.legend.append((l, ll))





    def _xy(self, i):
        log.debug('xy plot of {}'.format([getattr(self, v)[i] for v in 'sxyzc']))
        kwargs = self.opts(i)
        x, y, z = self.data(i)

        if x is not None:
            args = (x, y)
        else:
            args = (y,)

        if z is None:
            if 'linestyle' in kwargs:
                kwargs['linestyle'] = 'none'
            else:
                kwargs.update({'linestyle':'none'})

            if 'marker' in kwargs:
                kwargs['marker'] = '.'
            else:
                kwargs.update({'marker':'.'})

            l, = plt.plot(*args, **kwargs)
        else:
            # linestyle must not be 'none' when plotting 3D
            if 'linestyle' in kwargs and kwargs['linestyle'] == 'none':
                kwargs['linestyle'] = ':'

            o = get_args_from(kwargs, markersize = 2, cbfrac = 0.04, cblabel = self.alabel('z'))
            l = plt.scatter(x, y, c = z, s = o.markersize ** 2, edgecolor = 'none', **kwargs)

            m = 6.0
            dmin, dmax = np.nanmin(z), np.nanmax(z)
            cticks = ticks.get_ticks(dmin, dmax, m, only_inside = 1)
            formatter = mpl.ticker.FuncFormatter(func = lambda x, i:number_mathformat(x))
            cb = plt.colorbar(fraction = o.cbfrac, pad = 0.01, aspect = 40, ticks = cticks, format = formatter)
            cb.set_label(o.cblabel)

        self.legend.append((l, self.llabel(i)))

        # fit
        self.fit(i, x, y)

    def _hist1d(self, i):
        self.plotted_lines = []
        log.debug('1D histogram of {}'.format([getattr(self, v)[i] for v in 'sxyzc']))
        kwargs = self.opts(i)
        x, y, z = self.data(i)

        o = get_args_from(kwargs, density = False, cumulative = 0)
        o.update(get_args_from(kwargs, style = 'histline' if o.density else 'hist'))
        err = 0  # o.style.startswith('s')
        o.update(get_args_from(kwargs, xerr = err, yerr = err, capsize = 3 if err else 0))

        bins = self.bins(i, 'x')
        if  bins == 0:
            bins = int(1 + np.log2(len(x)))
        binedges, bincenters, binwidths = get_binning(bins, x)

        bincontents, _d1 = np.histogram(x, binedges)
        assert np.all(binedges == _d1)
        binerrors = np.sqrt(bincontents)
        binerrors[binerrors == 0] = 1

        # statsbox
        self.stats_fields1d(i, x, bincontents, binerrors, binedges)

        if o.density:
            bincontents, binerrors = get_density(bincontents, binerrors, binwidths)

        if o.cumulative:
            bincontents, binerrors = get_cumulative(bincontents, binerrors, o.cumulative, binwidths if o.density else 1)

        if 'line' in o.style:
            x = bincenters
            y = bincontents
        else:
            x, y = get_step_points(bincontents, binedges)

        if 'fill' in o.style:
            l, = plt.fill(x, y, **kwargs)

        elif 'hist' in o.style:
            l, = plt.plot(x, y, **kwargs)

        elif 'scat' in o.style:
            pargs = set_defaults(kwargs, linestyle = '', marker = '.')
            l, = plt.plot(bincenters, bincontents, **pargs)

        else:
            raise ValueError('unknown style: ' + o.style)

        if o.xerr or o.yerr:
            pargs = set_defaults(kwargs, capsize = o.capsize, ecolor = 'k' if 'fill' in o.style else l.get_c())
            xerr = 0.5 * binwidths if o.xerr else None
            yerr = binerrors if o.yerr else None
            plt.errorbar(bincenters, bincontents, yerr, xerr, fmt = None, **pargs)


        adjust_limits('x', binedges)
        adjust_limits('y', bincontents + binerrors, marl = 0)

        self.legend.append((l, self.llabel(i)))

        self.fit(i, bincenters, bincontents, binerrors)

    def _hist2d(self, i):
        log.debug('2D histogram of {}'.format([getattr(self, v)[i] for v in 'sxyzc']))
        kwargs = self.opts(i)
        x, y, z = self.data(i)
        o = get_args_from(kwargs, style = 'color', density = False, log = False, cbfrac = 0.04, cblabel = 'bincontent', levels = 10)
        filled = 'color' in o.style or ('fill' in o.style)
        o.update(get_args_from(kwargs, hidezero = o.log or filled, colorbar = filled, clabels = not filled))

        # make binnings
        bins = self.bins(i, 'x')
        if  bins == 0:
            bins = int(1 + np.log2(len(x)))
        xedges, xcenters, xwidths = get_binning(bins, x)

        bins = self.bins(i, 'y')
        if  bins == 0:
            bins = int(1 + np.log2(len(y)))
        yedges, ycenters, ywidths = get_binning(bins, y)

        bincontents, _d1, _d2 = np.histogram2d(x, y, [xedges, yedges])
        bincontents = np.transpose(bincontents)
        assert np.all(_d1 == xedges)
        assert np.all(_d2 == yedges)

        # statsbox
        self.stats_fields2d(i, bincontents, xcenters, ycenters)

        if o.density:
            bincontents = get_density2d(bincontents, xwidths, ywidths)

        if o.hidezero:
            bincontents[bincontents == 0] = np.nan

        if o.log:
            bincontents = np.log10(bincontents)
            formatter = mpl.ticker.FuncFormatter(func = lambda x, i:number_mathformat(np.power(10, x)))
        else:
            formatter = mpl.ticker.FuncFormatter(func = lambda x, i:number_mathformat(x))

        if 'color' in o.style:
            pargs = set_defaults(kwargs, cmap = 'jet', edgecolor = 'none')
            plt.pcolor(xedges, yedges, ma.array(bincontents, mask = np.isnan(bincontents)), **kwargs)

        elif 'box' in o.style:
            pargs = set_defaults(kwargs, color = (1, 1, 1, 0), marker = 's', edgecolor = 'k')
            n = bincontents.size
            s = bincontents.reshape(n)
            s = s / np.nanmax(s) * (72. / 2. * self.w / max(len(xcenters), len(ycenters))) ** 2
            xcenters, ycenters = np.meshgrid(xcenters, ycenters)
            plt.scatter(xcenters.reshape(n), ycenters.reshape(n), s = s, **pargs)

        elif 'contour' in o.style:
            pargs = set_defaults(kwargs, cmap = 'jet')
            if not isinstance(pargs['cmap'], mpl.colors.Colormap):
                pargs['cmap'] = mpl.cm.get_cmap(pargs['cmap'])

            if filled:
                cs = plt.contourf(xcenters, ycenters, bincontents, o.levels, **pargs)
            else:
                cs = plt.contour(xcenters, ycenters, bincontents, o.levels, **pargs)
                if o.clabels:
                    plt.clabel(cs, inline = 1)

        else:
            raise ValueError('unknown style ' + o.style)

        if o.colorbar:
            m = 6.0
            dmin, dmax = np.nanmin(bincontents), np.nanmax(bincontents)
            if o.log:
                dmin, dmax = np.ceil(dmin), np.floor(dmax) + 1
                step = max(1, np.floor((dmax - dmin) / m))
                cticks = np.arange(dmin, dmax, step)
            else:
                cticks = ticks.get_ticks(dmin, dmax, m, only_inside = 1)

            cb = plt.colorbar(fraction = o.cbfrac, pad = 0.01, aspect = 40, ticks = cticks, format = formatter)
            cb.set_label(o.cblabel)


    def _profile(self, i):
        log.debug('profile of {}'.format([getattr(self, v)[i] for v in 'sxyzc']))
        kwargs = self.opts(i)
        x, y, z = self.data(i)
        o = get_args_from(kwargs, xerr = 0, yerr = 0)

        # make x binning
        xedges, xcenters, xwidths = get_binning(self.bins(i, 'x'), x)

        # compute avg and std for each x bin
        xx = xcenters
        xerr = 0.5 * xwidths if o.xerr else None
        yy = []
        yerr = []
        for l, u in zip(xedges[:-1], xedges[1:]):
            bindata = y[(l <= x) & (x < u)]
            yy.append(np.mean(bindata))
            yerr.append(np.std(bindata))
        if not o.yerr:
            yerr = None

        pargs = set_defaults(kwargs, capsize = 3, marker = '.', linestyle = 'none')
        l, _d, _d = plt.errorbar(xx, yy, yerr, xerr, **pargs)

        self.legend.append((l, self.llabel(i)))

        self.fit(i, xx, yy, yerr)


    def _map(self, i):
        import maps
        log.debug('map of {}'.format([getattr(self, v)[i] for v in 'sxyzc']))
        kwargs = self.opts(i)
        x, y, z = self.data(i)
        o = get_args_from(kwargs, margin = 0.05, width = 10e6, height = None, boundarylat = 50, projection = 'cyl',
                          drawcoastline = 1, drawgrid = 1, drawspecgrid = 1, drawcountries = 0, bluemarble = 0, nightshade = None)

        m = maps.drawmap(y, x, **o)
        x, y = m(x, y)

        if z is None:
            l, = plt.plot(x, y, **kwargs)
        else:
            # linestyle must not be 'none' when plotting 3D
            if 'linestyle' in kwargs and kwargs['linestyle'] == 'none':
                kwargs['linestyle'] = ':'

            o = get_args_from(kwargs, markersize = 6, cbfrac = 0.04, cblabel = self.alabel('z'))
            p = set_defaults(kwargs, zorder = 100)
            l = plt.scatter(x, y, c = z, s = o.markersize ** 2, edgecolor = 'none', **p)

            m = 6.0
            dmin, dmax = np.nanmin(z), np.nanmax(z)
            cticks = ticks.get_ticks(dmin, dmax, m, only_inside = 1)
            formatter = mpl.ticker.FuncFormatter(func = lambda x, i:number_mathformat(x))
            cb = plt.colorbar(fraction = o.cbfrac, pad = 0.01, aspect = 40, ticks = cticks, format = formatter)
            cb.set_label(o.cblabel)

        self.legend.append((l, self.llabel(i)))


    def stats_fields1d(self, i, data, contents, errors, edges):
        centers = (edges[1:] + edges[:-1]) / 2
        widths = np.diff(edges)

        stats = {}
        stats['N'] = N = np.sum(contents)
        stats['uflow'] = np.sum(data < edges[0])
        stats['oflow'] = np.sum(edges[-1] < data)
        stats['mean'] = mean = np.sum(centers * contents) / N
        stats['std'] = std = np.sqrt(np.sum((centers - mean) ** 2 * contents) / N)
        stats['mode'] = centers[np.argmax(contents)]
        bc, be = get_density(contents, errors, widths)
        bc, be = get_cumulative(bc, be, 1, widths)
        median_i = np.minimum(len(centers)-1, np.searchsorted(bc, 0.5, side = 'right'))
        stats['median'] = median = centers[median_i]
        if len(centers) % 2 == 0:  # even # of s
            stats['median'] = median = (median + centers[median_i - 1]) / 2
        stats['skew'] = np.sum(((centers - mean) / std) ** 3 * contents) / N
        stats['kurtos'] = kurtosis = np.sum(((centers - mean) / std) ** 4 * contents) / N
        stats['excess'] = kurtosis - 3
        log.debug(stats)

        text = '{:6} {}'.format('hist', self.llabel(i))
        sb = self.sb[i]
        if 'a' in sb: sb = 'nmscpewx'
        if 'uflow' in stats and stats['uflow']: sb += 'u'
        if 'oflow' in stats and stats['oflow']: sb += 'o'
        for k in sb:
            k = stats_abrv[k]
            if k in stats:
                text += '\n{:6} {}'.format(_(k), number_mathformat(stats[k]))
        self.textboxes.append(text)

    def stats_fields2d(self, i, contents, xcenters, ycenters):
        stats = {}
        stats['N'] = N = contents.sum()
        stats['mean'] = mean = np.array([ (contents.sum(axis = 0) * xcenters).sum(),
                         (contents.sum(axis = 1) * ycenters).sum()]) / N
        stats['std'] = np.sqrt(np.array([(contents.sum(axis = 0) * (xcenters - mean[0]) ** 2).sum(),
                                  (contents.sum(axis = 1) * (ycenters - mean[1]) ** 2).sum()]) / N)
        cov = 0
        for k, l in product(xrange(contents.shape[1]), xrange(contents.shape[0])):
            cov += contents[l, k] * (xcenters[k] - mean[0]) * (ycenters[l] - mean[1])
        stats['cov'] = cov / N
        log.debug(stats)

        text = '{:6} {}'.format('hist', self.llabel(i))
        sb = self.sb[i]
        if 'a' in sb: sb = 'nmscpewx'
        if 'uflow' in stats and stats['uflow']: sb += 'u'
        if 'oflow' in stats and stats['oflow']: sb += 'o'
        for k in sb:
            k = stats_abrv[k]
            if k in stats:
                v = stats[k]
                try:
                    v = number_mathformat(v)
                except:
                    v = '({})'.format(','.join(map(number_mathformat, v)))
                text += '\n{:6} {}'.format(_(k), v)
        self.textboxes.append(text)



def display_progress(p):
    "display a progressbar on stdout by reading p.progress"

    from threading import Thread
    from progressbar import ProgressBar, Bar, Percentage, ETA

    def progressUpdate():
        pb = ProgressBar(maxval = 1, widgets = [Bar(), ' ', Percentage(), ' ', ETA()], fd = sys.stdout)
        while p.progress < 1:
            pb.update(p.progress)
            time.sleep(0.5)
        pb.finish()

    t = Thread(target = progressUpdate)
    t.daemon = True
    t.start()


def display_settings_help():
    print '''available plot settings
===========================

Settings containing a # may appear multiple times, once per graph.
The # is to be replaced by an integer starting with 0.

t
w
h
s#
m#
n#
rw#
rs#
rc#
x#
x#b
o#xerr
y#
o#yerr
c#
ff#
fp#
fl#
o#color
o#alpha
o#linestyle
o#linewidth
o#marker
o#markersize
o#zorder
xl
xr
xs
xrtw
l
'''
    exit()


def main():
    from argparse import ArgumentParser
    import ctplot

    def key_value_pair(s):
        k, v = s.split('=', 1)
        return k, v

    parser = ArgumentParser(description = 'analyse and plot HDF5 table data', epilog = ctplot.__epilog__)
    parser.add_argument('-H', '--help-settings', action = 'store_true', help = 'display help for settings')
    parser.add_argument('-V', '--version', action = 'version', version = '%(prog)s {} build {}'.format(ctplot.__version__, ctplot.__build_date__))
    parser.add_argument('-o', '--output', metavar = 'file', help = 'name of output file, show window if omitted')
    parser.add_argument('-v', '--verbose', action = 'store_true', help = 'set logging level to DEBUG')
    parser.add_argument('-q', '--quiet', action = 'store_true', help = 'set logging level to ERROR')
    parser.add_argument('-c', '--cache', metavar = 'dir', help = 'dir where to store cached HDF5 tables, cache is deactivated if not set')
    parser.add_argument('settings', metavar = 'K=V', nargs = '+', type = key_value_pair, help = 'plot settings, given as key value pairs')

    settings = {"t":"", "w":"", "h":"", "experiment0":"neutron-mon-neumayer",
                "s0":"../data/2013_NEUMAYER-nm-my.h5:/raw/PS_mu_nm_data", "m0":"p",
                "n0":"", "rw0":"3600", "rs0":"", "rc0":"", "x0":"p", "x0b":"30", "o0xerr":"true", "y0":"log10(mu_rate)",
                "o0yerr":"true", "c0":"time<7.65e7 and mu_rate==mu_rate", "ff0":"p[0]+p[1]*x", "fp0":"1.5, 0", "fl0":"b",
                "o0color":"r", "o0alpha":"", "o0linestyle":"", "o0linewidth":"", "o0marker":"", "o0markersize":"12", "o0zorder":"",
                "xl":"", "xr-min":"", "xr-max":"", "xr":"", "xs":"", "xrtw":"", "yl":"", "yr-min":"", "yr-max":"", "yr":"", "ys":"",
                "yrtw":"", "zl":"", "zr-min":"", "zr-max":"", "zr":"", "zs":"", "l":"lower left", "a":"plot", "plots":1}

    ss = ['{}={}'.format(k, v) for k, v in settings.items()]
    ss.append('-h')
    ss.append('-c..')


    args = parser.parse_args()

    if args.help_settings:
        display_settings_help()

    log.setLevel(logging.INFO)

    if args.verbose:
        log.setLevel(logging.DEBUG)

    if args.quiet:
        log.setLevel(logging.ERROR)

    args.settings = dict(args.settings)

    log.debug(args)


    config = {'cachedir':''}
    if args.cache:
        config['cachedir'] = args.cache

    p = Plot(config, **args.settings)

    if not args.quiet:
        display_progress(p)


    if args.output:
        p.save(args.output)
    else:
        p.show()


if __name__ == '__main__':
    main()
