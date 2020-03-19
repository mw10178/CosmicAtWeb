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
import numpy as np
import dateutil.parser as dp

_safe_globals = { "__builtins__": None, "__import__": None }
_safe_locals = {}

#add any needed builtins back in.
for k in []:
    _safe_locals[k] = eval(k)

# numpy functions
for k, v in np.__dict__.iteritems():
    # do not numpy's financial rate function to safe locals, as it may clash
    # with ctplot's 'rate' parameter
    if k != 'rate':
        _safe_locals[k] = getattr(np, k)

_safe_locals['logbins'] = lambda start, stop, count: [np.exp(x) for x in np.linspace(np.log(start), np.log(stop), count)]
_safe_locals['since04'] = lambda s: (dp.parse(s) - dp.parse('2004-01-01 00:00 +01')).total_seconds()

class safeeval:
    def __init__(self, safe_globals = _safe_globals, safe_locals = _safe_locals):
        self.globals = safe_globals.copy()
        self.globals.update(safe_locals)
        self.locals = {}

    def __setitem__(self, key, value):
        self.locals[key] = value

    def __getitem__(self, key):
        return self.locals[key]

    def __delitem__(self, key):
        del self.locals[key]

    def __call__(self, expr):
#        print 'safeval', expr
        return eval(expr, self.globals, self.locals)

if __name__ == '__main__':
    for k, v in _safe_locals.iteritems():
        print k, v

