#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import utils
import datetime as dt
import dateutil.parser as dp
import os
import os.path as path
from collections import OrderedDict
import pytz
import re
import tables as t
from progressbar import ProgressBar, Bar, Percentage, ETA
import math
from utils import set_attrs
from pkg_resources import resource_stream


NaN = float('NaN')

def filescaniter(filename, validator = None):
    'returns iterator yielding tuples with data from each line'
    datafile = open(filename)

    try:
        scanner = utils.get_scanner()
        line_counter = 0
        for line in datafile:
            line_counter += 1
            line = line.strip()
            if line.startswith("#") or line == '':
                continue

            t = tuple(scanner.scan(line)[0])

            if validator is not None:
                validator(t)

            yield t

    except:
        print >> sys.stderr, "Error parsing line", line_counter, "in", datafile
        raise

    finally:
        datafile.close()

def fileiter(filename, linehandler, skip_on_assert = False, print_failures = True, ignore_errors = False):
    'returns iterator yielding objects created by linehandler from each line'
    if verbose > 1: print 'reading', filename
    with open(filename) as datafile:
        try:
            for i, line in enumerate(datafile, 1):
                try:
                    if verbose > 2: print 'line', i, ':', line.strip()
                    data = linehandler(line)
                    if verbose > 2: print 'data', i, ':', data, '\n'
                    if data is not None:
                        yield data

                except AssertionError as e:
                    if not skip_on_assert:
                        raise
                    elif print_failures:
                        print >> sys.stderr, "%s:%d '%s'" % (filename, i, e)

                except Exception as e:
                    if ignore_errors:
                        print >> sys.stderr, "%s:%d '%s'" % (filename, i, e)
                        print >> sys.stderr, "\tline: '%s'" % (line)
                    else:
                        raise

        except Exception as e:
            raise RuntimeError("Error parsing line %d in %s" % (i, filename), e)








#                          yyyy          mm                        dd          HH    MM    SS    .ss      TZname       TZoffset
datetime_re = re.compile(r"\d{4}[-./]?([A-Z][a-z]{2,}|\d{2})[-./]?\d{2}(\s+|T)\d{2}:\d{2}(:\d{2}(\.\d+)?)?(\s+[A-Z]{3,})?([+-]\d{1,2}:?(\d{2})?)?")
tz_re = re.compile('([A-Z]{3,})([+-]\d+)')
def repl(match):
    return match.group(1) + ' ' + match.group(2)

class LineHandler:
    description = '(description of the file format)'
    col_descriptor = property(lambda self: self._col_descriptor())
    col_units = property(lambda self: tuple(self.cols_and_units.values()))
    col_names = property(lambda self: tuple(self.cols_and_units.keys()))
    table_title = '(unnamed table)'

    def __init__(self):
        self.lastdt = None

    def _parse_time(self, line):
        'find a datetime stamp at the beginning of line, return (time as datetime, line with timestamp removed)'
        # find datetime stamp
        match = re.match(datetime_re, line)
        assert match
        dt = match.group(0)
        dt = re.sub(tz_re, repl, dt)
        time = dp.parse(dt, fuzzy = True)
        # remove datetime from beginning
        line = line[len(dt):]
        return (time, line)


    def __call__(self, line):
        'parse line and return tuple with data or None if line was skipped (comment/empty)'
        line = line.strip()
        # skip comments or empty lines
        if line.startswith('#') or line == '':
            return

        # extract the datetime stamp from line and put
        # it into time as datetime and return the rest of the line
        # with the datetime stamp removed
        time, line = self._parse_time(line)

        # list containing data from line, starting with datetime stamp
        data = [time]

        # add the remaining data as floats
        parts = line.split()
        for x in parts:
            try:
                data.append(float(x))
            except:  # skip everything that is not parsable as float
                pass

        self.sanitize(data)  # modify data (perform cleanup, transformations, etc.)
        data = tuple(data)  # freeze data (tuples are immutable)

        self.verify(data)  # verify that data fulfills certain criteria
        return data

    def _verify_time(self, time):
        'verify that time > last timestamp, i.e. that the records in the datafile are in ascending time order'
        if self.lastdt is not None:
            if not time > self.lastdt:
                raise AssertionError('time <= last time: %s <= %s' % (time.isoformat(), self.lastdt.isoformat()))
        if not time.tzinfo:
                raise AssertionError('time has no tzinfo: %s' % (time.isoformat(),))
        self.lastdt = time

    def sanitize(self, data):
        pass

    def verify(self, data):
        pass

nan = float('nan')
inf = float('inf')

def verifyrange(name, value, lower = -inf, upper = +inf, nan_allowed = False):
    if not (lower <= value <= upper or (nan_allowed and math.isnan(value))):
        raise AssertionError('%s out of range: %s' % (name, value))



class WeatherHandler(LineHandler):
    description = 'Zeuthen weather data [example: 2011-01-01 07:00:00+01:00 16.6 1.5 0.0 33 90 0.7 22.5 NNE -1.0 1.5 0.0 1006.9]'
    table_name = 'zeuthen_weather'
    table_title = 'Zeuthen weather data'
    cols_and_units = OrderedDict([('time', 's'), ('T_i', '°C'), ('T_a', '°C'), ('T_dew', '°C'),
                                  ('H_i', '%'), ('H_a', '%'), ('v_wind', 'm/s'), ('d_wind', '°'),
                                  ('gust', '?'), ('chill', '?'), ('rain', 'mm'), ('p', 'hPa'), ('clouds', '?')])

    start06 = dp.parse('2006-01-01 00:00:00 +0100')

    def sanitize(self, data):
        time = data[0]
        data.append(nan)  # clouds, only present in pre 2006 weather data

        # replace -1 by nan, -1 means 'no data'
        for i in [4, 5, 6, 7, 8, 9, 10, 11]:
            if data[i] == -1.0:
                data[i] = nan

        # check for T_a < 0 in summer
        if 4 < time.month < 10 and data[2] == -1.0:
            data[2] = nan

        # check for invalid T_dew
        if not data[3] < data[2] and data[3] == -1.0:
            data[3] = nan

        # transform data in pre 2006 weather
        if time < WeatherHandler.start06:
            # replace -1 by nan, -1 means 'no data'
            for i in [1, 3]:
                if data[i] == -1.0:
                    data[i] = nan
            data[12] = data[5]  # set clouds if < 2006
            data[4] = data[5] = nan  # clear humidity

    def verify(self, data):
        # 0    1    2     3     4    5      6       7     8      9     10   11   12
        time, T_i, T_a, T_dew, H_i, H_a, v_wind, d_wind, gust, chill, rain, p, clouds = data
        self._verify_time(time)

        # there may be nan values in pre 2006 weather
        allow_nan = time < WeatherHandler.start06

        verifyrange('T_i', T_i, -50 , 50, allow_nan)
        verifyrange('T_a', T_a, -50 , 50)
        verifyrange('T_dew', T_dew, -50 , T_a - 1e-15, allow_nan)
        verifyrange('H_i', H_i, 0 , 100, True)
        verifyrange('H_a', H_a, 0 , 100, True)
        verifyrange('v_wind', v_wind, 0 , 60, True)
        verifyrange('d_wind', d_wind , 0, 360, True)
        verifyrange('gust', gust, 0 , 120, True)
        verifyrange('rain', rain, 0, nan_allowed = True)
        verifyrange('p', p , 800, 1200)
        verifyrange('clouds', clouds, 1 , 6, True)


    def _col_descriptor(self):
        return OrderedDict([(k, t.FloatCol(dflt = nan, pos = i)) for i, k in enumerate(self.col_names)])



class CTEventHandler(LineHandler):
    description = 'Cosmic Trigger event data [example: 2004-05-22 00:00:25.92+02:00   0 1 0 0   0 1 0 0   1 0 0 0]'
    table_name = 'CT_events'
    table_title = 'Cosmic Trigger events'
    cols_and_units = OrderedDict([('time', 's'), ('a1', ''), ('a2', ''), ('a3', ''), ('a4', ''),
                                  ('b1', ''), ('b2', ''), ('b3', ''), ('b4', ''),
                                  ('c1', ''), ('c2', ''), ('c3', ''), ('c4', '')])

    def verify(self, data):
        time = data[0]
        self._verify_time(time)
        triggered = data[1:]
        verifyrange('number of detector segments', len(triggered), 12 , 12)
        verifyrange('multiplicity', sum(triggered) , 3 , 12)
        verifyrange('multiplicity in level a', sum(triggered[0:4]) , 1 , 4)
        verifyrange('multiplicity in level b', sum(triggered[4:8]) , 1 , 4)
        verifyrange('multiplicity in level c', sum(triggered[8:12]) , 1 , 4)

    def _col_descriptor(self):
        descriptor = OrderedDict([(k, t.BoolCol(dflt = False, pos = i)) for i, k in enumerate(self.col_names)])
        descriptor['time'] = t.FloatCol(dflt = nan, pos = self.col_names.index('time'))
        return descriptor



class ITTEventHandler(LineHandler):
    description = 'IceTop Tank event data [example: 5 2011/10/24 09:25:54.346  V265[0]        40    16]'
    table_name = 'ITT_events'
    table_title = 'IceTop Tank events'
    cols_and_units = OrderedDict([('time', 's'), ('dom1', ''), ('dom2', ''), ('run', ''), ('time2', 's'),
                                  ('a1', ''), ('a2', ''), ('a3', ''), ('a4', ''),
                                  ('b1', ''), ('b2', ''), ('b3', ''), ('b4', '')])

    _leading_int = re.compile('(^[+-]?\\d+)\\s+(.*)')

    def __init__(self):
        LineHandler.__init__(self)
        self.expecting_second_part = False

    def __call__(self, line):
        'parse line and return tuple with data or None if line was skipped (comment/empty)'
        line = line.strip()
        # skip comments or empty lines
        if line.startswith('#') or line == '':
            return

        # extract leading int
        m = self._leading_int.match(line)
        i = int(m.group(1))
        line = m.group(2)  # line w/o leading int
        if i <= 0:
            if i == 0:
                parts = line.split()
                if len(parts) == 4 and parts[0] == 'Run':
                    self.run = int(parts[1])
            return

        # extract the datetime stamp from line and put
        # it into time as datetime and return the rest of the line
        # with the datetime stamp removed
        time, line = self._parse_time(line)

        # list containing data from line, starting with datetime stamp
        data = [time]

        # add the remaining data as floats
        parts = line.split()
        for x in parts:
            try:
                data.append(float(x))
            except:  # skip everything that is not parsable as float
                pass

        if self.expecting_second_part:
            self.expecting_second_part = False
            assert self.i == i
#            assert self.data[0] == data[0]
            assert len(data) == 9
            self.data.extend(data)
            data = self.data
        else:
            self.expecting_second_part = True
            assert len(data) == 3
            self.i = i
            data.append(self.run)
            self.data = data
            return


        self.sanitize(data)  # modify data (perform cleanup, transformations, etc.)
        data = tuple(data)  # freeze data (tuples are immutable)

        self.verify(data)  # verify that data fulfills certain criteria
        return data

    _timezone = pytz.timezone('Europe/Berlin')

    def sanitize(self, data):
        for i in (0, 4):
            data[i] = self._timezone.localize(data[i])


    def _verify_time(self, time):
        if self.lastdt is not None:
            if time < self.lastdt:
                raise AssertionError('time <= last time: %s <= %s' % (time.isoformat(), self.lastdt.isoformat()))
        if not time.tzinfo:
                raise AssertionError('time has no tzinfo: %s' % (time.isoformat(),))
        self.lastdt = time

    def verify(self, data):
        time, dom1, dom2, run, time2, a1, a2, a3, a4, b1, b2, b3, b4 = data
        self._verify_time(time)
        self._verify_time(time2)
        verifyrange('dom1', dom1, 0)
        verifyrange('dom2', dom2, 0)
        verifyrange('run', run, 1)
        verifyrange('a1', a1, 0)
        verifyrange('a2', a2, 0)
        verifyrange('a3', a3, 0)
        verifyrange('a4', a4, 0)
        verifyrange('b1', b1, 0)
        verifyrange('b2', b2, 0)
        verifyrange('b3', b3, 0)
        verifyrange('b4', b4, 0)

    def _col_descriptor(self):
        return OrderedDict([(k, t.FloatCol(dflt = nan, pos = i)) for i, k in enumerate(self.col_names)])

def stations():
    p = re.compile("(\\d{5})\\s+(\\d{5})\\s+(.+)\\s+(\\d+)\\s+(\\d+)°\\s+(\\d+)'?\\s+(\\d+)°\\s+(\\d+)'?.*")

    f = resource_stream(__name__, 'stationsliste.txt')

    stats = {}
    for line in f:
        line = line.strip()
        if line.startswith('#'):
            continue
        m = p.match(line)
        g = m.groups()
        #       height       lat                             lon                      klimakennung name
        data = [float(g[3]), float(g[4]) + float(g[5]) / 60, float(g[6]) + float(g[7]) / 60, g[1], g[2]]
        #     station ID
        stats[int(g[0])] = data
    f.close()

    return stats

class DWDTageswerteHandler(LineHandler):
    description = 'Klimadaten Tageswerte of the DWD (http://www.dwd.de) [example: 10004 20111028  1          12.0   12.9   13.9   85.7    4.0   12.1    3.0               1020.6]'
    table_name = 'dwd_daily_weather'
    table_title = 'DWD Tageswerte'
    cols_and_units = OrderedDict([('time', ''), ('stat', ''), ('qn', ''), ('tg', ''), ('tn', ''), ('tm', ''), ('tx', ''),
                                  ('rfm', ''), ('fm', ''), ('fx', ''), ('so', ''), ('nm', ''), ('rr', ''), ('pm', ''), ('h', ''), ('lat', ''), ('lon', '')])
#   (pos,len) time    stat    qn       tg       tn       tm       tx       rfm      fm       fx       so       nm       rr       pm
    fields = [(7, 8), (1, 5), (16, 2), (19, 6), (26, 6), (33, 6), (40, 6), (47, 6), (54, 6), (61, 6), (68, 6), (75, 6), (82, 6), (89, 6)]

    def __init__(self):
        self.stations = stations()

    def __call__(self, line):
        'parse line and return tuple with data or None if line was skipped (comment/empty)'
        line = line.strip()
        # skip comments or empty lines
        if line.startswith('<') or line.startswith('Tageswerte') or line.startswith('-----') or line == '':
            return
        if line.startswith('STAT'):
            assert line == 'STAT JJJJMMDD QN     TG     TN     TM     TX    RFM     FM     FX     SO     NM     RR     PM'
            return

        data = []
        for i, f in enumerate(self.fields):
            a = f[0] - 1
            b = a + f[1]
            field = line[a:b]
            if i == 0:
                data.append(dp.parse(field))
            elif 1 <= i <= 2:
                data.append(int(field))
            elif field.strip() == '':
                data.append(nan)
            else:
                data.append(float(field))

        stat = data[1]
        pos = self.stations[stat][0:3] if stat in self.stations else 3 * [nan]
        data.extend(pos)  # append height, lat, lon


        self.sanitize(data)  # modify data (perform cleanup, transformations, etc.)
        data = tuple(data)  # freeze data (tuples are immutable)

        self.verify(data)  # verify that data fulfills certain criteria
        return data

    _timezone = pytz.timezone('Europe/Berlin')

    def sanitize(self, data):
        data[0] = self._timezone.localize(data[0])
        data[0] += dt.timedelta(hours = 12)


    def _verify_time(self, time):
        if self.lastdt is not None:
            if time < self.lastdt:
                raise AssertionError('time <= last time: %s <= %s' % (time.isoformat(), self.lastdt.isoformat()))
        if not time.tzinfo:
                raise AssertionError('time has no tzinfo: %s' % (time.isoformat(),))
        self.lastdt = time

    def verify(self, data):
        pass

    def _col_descriptor(self):
        descriptor = OrderedDict([(k, t.FloatCol(dflt = nan, pos = i)) for i, k in enumerate(self.col_names)])
        descriptor['stat'] = t.IntCol(dflt = -1, pos = self.col_names.index('stat'))
        descriptor['qn'] = t.IntCol(dflt = -1, pos = self.col_names.index('qn'))
        return descriptor

class PolarsternHandler(LineHandler):
    description = 'Polarstern myon rate data [example: 2010 10 26  0 53 56.07 N 4  9.26 E 1025.7 10.1 39539 0 -1 63.5 12051 10000 1537]'
    table_name = 'polarstern_events'
    table_title = 'Polarstern myon rate data'
    cols_and_units = OrderedDict([('time', 's'), ('lat', '°'), ('lon', '°'),
                                  ('p', 'hPa'), ('T', '°C'), ('H', '%'), ('rate', '1/h')])

    def __call__(self, line):
        'parse line and return tuple with data or None if line was skipped (comment/empty)'
        line = line.strip()
        # skip comments or empty lines
        if line.startswith('#') or line == '':
            return

        fields = line.split()

        yy, mm, dd, hh = map(int, fields[:4])
        time = dt.datetime(yy, mm, dd, hh)

        deg, mins = map(float, fields[4:6])
        lat = (deg + mins / 60.) * (-1 if fields[6] == 'S' else 1)
        deg, mins = map(float, fields[7:9])
        lon = (deg + mins / 60.) * (-1 if fields[9] == 'W' else 1)

        ff = map(float, fields[10:])

        data = [time, lat, lon, ff[0], ff[1], ff[5], ff[8]]

        self.sanitize(data)  # modify data (perform cleanup, transformations, etc.)
        data = tuple(data)  # freeze data (tuples are immutable)

        self.verify(data)  # verify that data fulfills certain criteria
        return data

    _timezone = pytz.timezone('UTC')

    def sanitize(self, data):
        data[0] = self._timezone.localize(data[0])

    def verify(self, data):
        time, lat, lon, p, T, H, rate = data
        self._verify_time(time)
        verifyrange('lat', lat, -90, 90)
        verifyrange('lon', lon, -180, 180)
        verifyrange('T', T, -50 , 50)
        verifyrange('H', H, 0 , 100)
        verifyrange('p', p , 800, 1200)
        verifyrange('rate', rate, 0, 5000)

    def _col_descriptor(self):
        descriptor = OrderedDict([(k, t.FloatCol(dflt = nan, pos = i)) for i, k in enumerate(self.col_names)])
        return descriptor

mjd_epoch = dt.datetime(1858, 11, 17, tzinfo = pytz.timezone('UTC'))

class PolarsternHandler2(LineHandler):
    description = 'Polarstern myon rate data [example: 2010 10 26 04 55495.1667 -2144.4 1044.9 53.3298333333  N  3.46916666667  E  1025.8  9.3  14910  -1.0  0.00  59.9  10000 1550]'
    table_name = 'polarstern_events2'
    table_title = 'Polarstern myon rate data'
    cols_and_units = OrderedDict([('time', 's'), ('T_s', '°C'), ('p_s', 'mbar'), ('lat', '°'), ('lon', '°'),
                                  ('p', 'mbar'), ('T', '°C'), ('ceil', 'ft'), ('radi', 'W/m²'), ('rain', 'mm/min'),
                                  ('H', '%'), ('visi', 'm'), ('rate', '1/h')])

    def __call__(self, line):
        'parse line and return tuple with data or None if line was skipped (comment/empty)'
        line = line.strip()
        # skip comments or empty lines
        if line.startswith('#') or line == '':
            return

        fields = line.split()
        # assert len(fields) == 19, 'invalid number of fields'

        yy, mm, dd, hh = map(int, fields[:4])
        time = dt.datetime(yy, mm, dd, hh)

        mjd, Ts, ps = map(float, fields[4:7])

        lat = float(fields[7]) * (-1 if fields[8] == 'S' else 1)
        lon = float(fields[9]) * (-1 if fields[10] == 'W' else 1)

        data = [time, mjd, Ts, ps, lat, lon]
        data.extend(map(float, fields[11:]))

        self.sanitize(data)  # modify data (perform cleanup, transformations, etc.)
        self.verify(data)  # verify that data fulfills certain criteria
        data.pop(1)  # pop MJD
        data = tuple(data)  # freeze data (tuples are immutable)

        return data

    _timezone = pytz.timezone('UTC')

    def sanitize(self, data):
        # 0    1   2   3    4    5    6  7   8     9     10   11  12    13
        time, mjd, Ts, ps , lat, lon, p, T, ceil, radi, rain, H, visi, events = data
        data[0] = self._timezone.localize(time)
        if not (-50 <= Ts <= 50): data[2] = NaN
        if not (800 <= ps <= 1200): data[3] = NaN

        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            data[4] = data[5] = NaN

        if not (800 <= p <= 1200): data[6] = NaN
        if not (-50 <= T <= 50): data[7] = NaN
        if not (0 <= ceil <= 99999): data[8] = NaN
        if not (0 <= radi <= 9999): data[9] = NaN
        if not (0 <= rain <= 9999): data[10] = NaN
        if not (0 <= H <= 100): data[11] = NaN
        if not (0 <= visi <= 999999999): data[12] = NaN

    def verify(self, data):
        # 0    1   2   3    4    5    6  7   8     9     10   11  12    13
        time, mjd, Ts, ps , lat, lon, p, T, ceil, radi, rain, H, visi, events = data
        assert abs((time - mjd_epoch).total_seconds() / 3600 - 24 * mjd) < 1. / 60, "MJD does not match time"  # mjd-time < 1 minute
        self._verify_time(time)
        verifyrange('lat', lat, -90, 90, True)
        verifyrange('lon', lon, -180, 180, True)
        verifyrange('T', T, -50 , 50, True)
        verifyrange('H', H, 0 , 100, True)
        verifyrange('p', p , 800, 1200, True)
        verifyrange('events', events, 0, 10000)

    def _col_descriptor(self):
        descriptor = OrderedDict([(k, t.FloatCol(dflt = nan, pos = i)) for i, k in enumerate(self.col_names)])
        return descriptor


class NeutronHandler(LineHandler):
    description = 'Neutron Monitor Data [00:00:00 00004 01469  21.30 1014.680 5334.01351N 00833.41845E]'
    table_name = 'neutron_events'
    table_title = 'Neutron Monitor Data'
    cols_and_units = OrderedDict([('time', 's'), ('N', ''), ('HV', 'V'), ('T', '°C'),
                                  ('p', 'mbar'), ('lat', ''), ('lon', '')])

    def __call__(self, line):
        'parse line and return tuple with data or None if line was skipped (comment/empty)'
        line = line.strip()
        # skip comments or empty lines
        if line.startswith('#') or line == '':
            return

        match = re.match(r'(?i)Day\s*=\s*\d+\s*(.*)', line)
        if match:
            self.day = dp.parse(match.group(1))
            self.day = dt.datetime(self.day.year, self.day.month, self.day.day)
            self.day = self._timezone.localize(self.day)
            return


        if re.match(r'\d{2}:\d{2}:\d{2}\s+', line):
            time, N, HV, T, p, lat, lon = line.split()

            hh, mm, ss = map(int, time.split(':'))
            timeoffset = dt.timedelta(hours = hh, minutes = mm, seconds = ss)
            time = self.day + timeoffset

            lat = (float(lat[:2]) + float(lat[2:-1]) / 60) * (1 if lat[-1].lower() == 'e' else -1)
            lon = (float(lon[:3]) + float(lon[3:-1]) / 60) * (1 if lon[-1].lower() == 'n' else -1)

            data = [time, int(N), float(HV), float(T), float(p), lat, lon]

            self.sanitize(data)  # modify data (perform cleanup, transformations, etc.)
            self.verify(data)  # verify that data fulfills certain criteria
            data = tuple(data)  # freeze data (tuples are immutable)

            return data

    _timezone = pytz.timezone('UTC')

    def sanitize(self, data):
        # 0   1  2   3  4   5    6
        time, N, HV, T, p, lat, lon = data
        if not (1 <= HV <= 1e4): data[2] = NaN
        if not (-50 <= T <= 50): data[3] = NaN
        if not (800 <= p <= 1200): data[4] = NaN
        if not (-90 <= lat <= 90): data[5] = NaN
        if not (-180 <= lon <= 180): data[6] = NaN

    def verify(self, data):
        # 0   1  2   3  4   5    6
        time, N, HV, T, p, lat, lon = data
        self._verify_time(time)
        verifyrange('count', N, 0, 500)
        verifyrange('HV', HV, 1, 1e4, True)
        verifyrange('T', T, -50 , 50, True)
        verifyrange('p', p , 800, 1200, True)
        verifyrange('lat', lat, -90, 90, True)
        verifyrange('lon', lon, -180, 180, True)

    def _col_descriptor(self):
        descriptor = OrderedDict([(k, t.FloatCol(dflt = nan, pos = i)) for i, k in enumerate(self.col_names)])
        descriptor['N'] = t.IntCol(dflt = 0, pos = self.col_names.index('N'))
        return descriptor


class NeutronHandler2(LineHandler):
    description = 'Neutron Monitor Data 2 [00:00:00 00004 01469  21.30 1014.680 5334.01351N 00833.41845E]'
    table_name = 'neutron_events2'
    table_title = 'Neutron Monitor Data 2'
    cols_and_units = OrderedDict([('time', 's'), ('N', ''), ('T', '°C'), ('HV', 'V'), ('p', 'mbar')])

    def __call__(self, line):
        'parse line and return tuple with data or None if line was skipped (comment/empty)'
        line = line.strip()
        # skip comments or empty lines
        if line.startswith('#') or line == '':
            return

        match = re.match(r'(?i)Day\s*=\s*\d+\s*(.*)', line)
        if match:
            self.day = dp.parse(match.group(1))
            self.day = dt.datetime(self.day.year, self.day.month, self.day.day)
            self.day = self._timezone.localize(self.day)
            return


        if re.match(r'\d{2}:\d{2}:\d{2}\s+', line):
            fields = line.split()
            assert len(fields) > 31

            hh, mm, ss = map(int, fields[0].split(':'))
            timeoffset = dt.timedelta(hours = hh, minutes = mm, seconds = ss)
            time = self.day + timeoffset

            #             count           temperature        highvoltage        pressure
            data = [time, int(fields[1]), float(fields[13]), float(fields[16]), float(fields[31])]

            self.sanitize(data)  # modify data (perform cleanup, transformations, etc.)
            self.verify(data)  # verify that data fulfills certain criteria
            data = tuple(data)  # freeze data (tuples are immutable)

            return data

    _timezone = pytz.timezone('UTC')

    def sanitize(self, data):
        # 0   1  2   3  4
        time, N, T, HV, p = data
        if not (1 <= HV <= 1e4): data[2] = NaN
        if not (-50 <= T <= 50): data[3] = NaN
        if not (800 <= p <= 1200): data[4] = NaN

    def verify(self, data):
        # 0   1  2   3  4
        time, N, T, HV, p = data
        self._verify_time(time)
        verifyrange('count', N, 0, 5000)
        verifyrange('HV', HV, 1, 1e4, True)
        verifyrange('T', T, -50 , 50, True)
        verifyrange('p', p , 800, 1200, True)

    def _col_descriptor(self):
        descriptor = OrderedDict([(k, t.FloatCol(dflt = nan, pos = i)) for i, k in enumerate(self.col_names)])
        descriptor['N'] = t.IntCol(dflt = 0, pos = self.col_names.index('N'))
        return descriptor


available_handlers = (WeatherHandler, CTEventHandler, ITTEventHandler, DWDTageswerteHandler, PolarsternHandler, PolarsternHandler2, NeutronHandler, NeutronHandler2)


def autodetect(filename, handlers = available_handlers):
    """
    try to parse file (filename) with the given handlers (types, not instances).
    if the first 10 lines of the file can be parsed by a handler
    without error and there is only one handler that successfully
    parses the file (unique match) return this handler (type, not instance), 
    else raise RuntimeError
    """
    matched_handlers = []
    # try each handler
    for h in handlers:
        try:  # try to parse the file
            if verbose > 0:
                print 'trying', h
            datalines = []
            for i, data in enumerate(fileiter(filename, h())):
                datalines.append(data)
                if i > 10: break  # stop after 10 lines

            # if parsing was successful (no exception), add this handler
            if len(datalines) > 5:  # require at least 5 table rows to be read
                matched_handlers.append(h)

        except Exception as e:  # ignore errors, try next handler
            if verbose > 0:
                print '{0} failed to read {1}'.format(h, filename)
                print e
            pass

    # return a unique match...
    if len(matched_handlers) == 1:
        return matched_handlers[0]
    else:  # ...or raise
        raise RuntimeError(('could not autodetect handler for {} \nmatching handlers: \n{}'.format(filename, matched_handlers)))


def starttime(filename, handler):
    """
    get the first time stamp in the file using the given LineHandler,
    assuming the handler produces a 'time' column
    """
    time_idx = handler.col_names.index('time')

    first_record = fileiter(filename, handler).next()
    return first_record[time_idx]


def detect_and_sort(filenames, skip_unhandled):
    """
    detect files types (handlers) and sort the files 'time' ascending,
    return dict(LineHandler --> tuple(time sorted filenames))
    """
    sorted_files = {}

    # map files to auto detected handlers
    for filename in filenames:
        try:
            handler = autodetect(filename)
        except:
            if skip_unhandled:
                if verbose > 0:
                    print 'no handler for', filename, ' skipping'
                continue
            else:
                raise

        if handler in sorted_files:
            sorted_files[handler].append(filename)
        else:
            sorted_files[handler] = [filename]

    # time sort files and freeze file lists
    for h, files in sorted_files.iteritems():
        files.sort(key = lambda x: starttime(x, h()))
        sorted_files[h] = tuple(files)

    return sorted_files


def raw_to_h5(filenames, out = "out.h5", handlers = available_handlers,
              t0 = dp.parse('2004-01-01 00:00:00 +0000'), skip_on_assert = False, show_progress = True, ignore_errors = False, skip_unhandled = False):
    """
    converts ASCII data to HDF5 tables
        filenames : iterable, filenames of all data files (events, weather, etc.) in any order
              out : string, filename of outputfile (default='out.h5')
         handlers : iterable of LineHandlers for parsing the data files (default=available_handlers)
               t0 : datetime, reference time for 'time' column,
                    time is stored as 'time since t0' (default='2004-01-01 00:00:00 +0100')
    skip_on_assert: if True, skip lines that are invalid (if LineHandler.verify() raises AssertionError)
                    (default=False, exception is raised)
    """

    _filenames = []
    for f in filenames:
        if path.exists(f):
            if path.isdir(f):
                for dn, dns, fns in os.walk(f):
                    for fn in fns:
                        _filenames.append(path.join(dn, fn))
            else:
                _filenames.append(f)
    filenames = _filenames
    if verbose > 0:
        print 'files to process:'
        for fn in filenames:
            print '   ', fn

    assert len(filenames) > 0, 'no input files'

    if show_progress:
        pb = ProgressBar(maxval = len(filenames), widgets = [Bar(), ' ', Percentage(), ' ', ETA()], fd = sys.stdout)
        print "reference time t0 =", t0
        print 'autodetecting file types...'

    def read_files(files, row, handler):
        for f in files:
            for entry in fileiter(f, handler, skip_on_assert, show_progress, ignore_errors):
                try:
                    for k, v in zip(handler.col_names, entry):
                        if isinstance(v, dt.datetime):
                            row[k] = (v - t0).total_seconds()
                        else:
                            row[k] = v

                    row.append()

                except StopIteration:
                    pass

            if show_progress:
                pb.update(pb.currval + 1)

    # autodetect handlers and time sort files
    files_dict = detect_and_sort(filenames, skip_unhandled)

    if show_progress:
        print 'detected file types:', ['{} ({})'.format(k.table_name, len(v)) for k, v in files_dict.iteritems()]
        print "processing data... (%d files)" % (len(filenames),)
        pb.start()

    # create HDF5 file
    filters = t.Filters(complevel = 1, complib = 'zlib')
    with t.openFile(out, 'w', 'datafile created with raw_to_h5', filters = filters) as h5:
        h5.root._v_attrs.creationdate = dt.datetime.now(pytz.utc).isoformat()
        raw = h5.createGroup(h5.root, 'raw', 'raw data')

        # create and fill raw data tables
        for handler, files in files_dict.iteritems():
            handler = handler()  # instanciate the LineHandler
            title = handler.table_title
            if show_progress:
                print 'creating table: %s (%s)' % (handler.table_name, title)
            table = h5.createTable(raw, handler.table_name, handler.col_descriptor,
                                   title, expectedrows = 10000 * len(files))
            set_attrs(table, t0, handler.col_units)
            read_files(files, table.row, handler)
            table.flush()

    if show_progress:
        pb.finish()

verbose = 0

def main():
    from argparse import ArgumentParser
    import ctplot

    formats = ''
    for i, h in enumerate(available_handlers):
        if i > 0:
            formats += ', '
        formats += h.description

    parser = ArgumentParser(description = 'convert raw ASCII data tables into tables in one HDF5 file',
                               epilog = ctplot.__epilog__ + ', raw data can be in the following formats: ' + formats +
                               '. The program tries to autodetect the file format and sorts the input files by time automatically. ' +
                               'Times are stored as double as seconds since reference time t0.')

    parser.add_argument('-V', '--version', action = 'version', version = '%(prog)s {} build {}'.format(ctplot.__version__, ctplot.__build_date__))
    parser.add_argument('-o', '--out', metavar = 'file', default = 'out.h5', help = 'HDF5 output file (default: out.h5)')
    parser.add_argument('-f', '--force', action = 'store_true', help = 'overwrite existing file')
#    parser.add_argument('-a', '--append', action = 'store_true', help = 'append new data to existing file')
    parser.add_argument('-t', '--reftime', metavar = 'datetime', default = '2004-01-01T00:00:00+0000', type = dp.parse,
                        help = 'reference time t0 (default: 2004-01-01T00:00:00+0000)')
    parser.add_argument('-s', '--noskip', action = 'store_true', help = 'do not skip invalid lines, stop on error')
    parser.add_argument('-q', '--quiet', action = 'store_true', help = 'do not show progressbar, just print error messages')
    parser.add_argument('-v', '--verbose', action = 'count', help = 'show additional processing information')
    parser.add_argument('-k', '--keepgoing', action = 'store_true', help = 'keep going, do not stop on errors')
    parser.add_argument('-x', '--skip-unhandled', action = 'store_true', help = 'skip files with no handler')
    parser.add_argument('infiles', nargs = '+', help = 'input files, if a directory is given, all files in it and in its subdirectories are used')

    args = parser.parse_args()

    verbose = args.verbose

    if not args.out.endswith('.h5'):
        out = args.out + '.h5'
    else:
        out = args.out;

    if not args.force and path.exists(out):
        raise RuntimeError('file \'{}\' already exists'.format(out))


    raw_to_h5(args.infiles, out = out, skip_on_assert = not args.noskip, show_progress = not args.quiet,
              t0 = args.reftime, ignore_errors = args.keepgoing, skip_unhandled = args.skip_unhandled)


if __name__ == '__main__':
    main()

