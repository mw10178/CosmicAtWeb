# -*- coding: utf-8 -*-
#    pyplot - python based data plotting tools
#    created for DESY Zeuthen
#    Copyright (C) 2012  Adam Lucke  software@louisenhof2.de
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
import pytz, json, time, re, os
import dateutil.parser as dp
import datetime as dt
from datetime import timedelta
import safeeval
from math import  floor, log10
import numpy as np
import subprocess

class AttrDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__

def get_args_from(kwargs, **defaults):
    'return dict with default_kwargs and remove default_kwarsg from kwargs'
    copy = AttrDict()
    for k, v in defaults.iteritems():
        copy[k] = kwargs.pop(k, v)
    return copy

def set_defaults(kwargs, **default_kwargs):
    copy = default_kwargs.copy()
    copy.update(kwargs)
    return copy


def get_scanner():
    """
    return a Scanner that can identify:
    float, int, datetime, compass direction values
    """

    def repl(match):
        return match.group(1) + ' ' + match.group(2)

    tz = re.compile('([A-Z]{3,})([+-]\d+)')

    def date_handler(scanner, token):
#        print token,
        token = re.sub(tz, repl, token)
#        print "-->", token,
        date = dp.parse(token, fuzzy = True)
#        print "-->", date
        return date

    def int_handler(scanner, token):
        return int(token)

    def float_handler(scanner, token):
        return float(token)

    def bool_handler(scanner, token):
        return (token)

    def direction_handler(scanner, token):
        return token

    scanner = re.Scanner([
        (r"\d{4}[-.]?([A-Z][a-z]{2,}|\d{2})[-.]?\d{2}(\s+|T)\d{2}:\d{2}:\d{2}(\.\d+)?(\s+[A-Z]{3,})?[+-]\d{1,2}:?(\d{2})?", date_handler),
        (r"[+-]?(\d+\.\d*([eE][+-]?\d+)?|nan|inf)", float_handler),
        (r"[+-]?\d+", int_handler),
        (r"true|false|yes|no", bool_handler),
        (r"[NSEWO?]{1,3}", direction_handler),
        (r"\s+", None),
        ])

    return scanner

def set_attrs(table, t0, units):
    table.attrs.creationdate = dt.datetime.now(pytz.utc).isoformat()
    table.attrs.time_info = "time contains the number of seconds since t0"
    table.attrs.t0 = t0.isoformat()
    assert len(table.colnames) == len(units)
    table.attrs.units = json.dumps(units)

def seconds2datetime(t0, seconds):
    return t0 + timedelta(seconds = seconds)

_eval = safeeval.safeeval()

def evalifstr(s):
    if isinstance(s, basestring):
        return _eval(s)
    else:
        return s


def isseq(x):
    return not isinstance(x, basestring) and hasattr(x, '__getitem__') and hasattr(x, '__len__')

def isiter(x):
    return hasattr(x, '__iter__')

def number_format(value, precision = 4):
    if isinstance(value, tuple) or  isinstance(value, list):
        s = '('
        for i, v in enumerate(value):
            if i > 0:
                s += ', '
            s += number_format(v, precision)
        s += ')'
        return s

    else:
        if value == 0:
            return '0'
        elif np.isnan(value):
            return 'nan'

        a = abs(value)

        e = log10(a)

        digits = max(precision - int(floor(e) + 1), 1)

        def clean(s):
            tup = s.split('e')
            if len(tup) == 2:
                mantissa = tup[0].rstrip('0').rstrip('.')
                sign = tup[1][0].replace('+', '')
                exponent = tup[1][1:].lstrip('0')
                s = '%se%s%s' % (mantissa, sign, exponent)
            else:
                s = s.rstrip('0').rstrip('.')
            return s


        ff = '%%.%df' % (digits,)
        sf = ff % value
        sf = clean(sf)

        fe = '%%.%de' % (precision - 1,)
        se = fe % value
        se = clean(se)

        if len(sf) < len(se):
            return sf
        else:
            return se

def number_mathformat(value, precision = 4):
    s = re.sub('[eE](.*)', '*10^{\\1}', number_format(value, precision))
    s = re.sub('^1[ .]*x', '', s)
    return '$\mathdefault{' + s + '}$'


def hashargs(*args, **kwargs):
    return hash(json.dumps((args, kwargs), separators = (',', ':'), sort_keys = True))


def noop(*args, **kwargs):
    pass


def getStatCpu():
    with open('/proc/stat') as stat:
        for line in stat:
            line = line.strip()
            if line.startswith('cpu'):
                cpu = map(int, line.split()[1:])
                return cpu

def getCpuUsage():
    c1 = getStatCpu()
    time.sleep(1)
    c2 = getStatCpu()
    t = sum(c2) - sum(c1)
    d = map(lambda x: float(x[1] - x[0]) / t, zip(c1, c2))
    return dict(zip(['user', 'nice', 'system', 'idle', 'iowait', 'irq', 'softirq'], d))


def getCpuLoad():
    if os.name == 'posix':
        usage = getCpuUsage()
        del usage['idle']
        return sum(usage.values())
    else:
        return 0

def getRunning(name):
    if os.name == 'posix':
        p = subprocess.Popen(['ps', 'auxr'], stdout = subprocess.PIPE)
        n = 0
        for l in p.stdout:
            if name in l: n += 1
        return n
    else:
        return 0

