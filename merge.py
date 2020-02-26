#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tables as t
from progressbar import ProgressBar, Bar, ETA, Percentage
from collections import OrderedDict
from utils import set_attrs, seconds2datetime
import dateutil.parser as dp
import sys, json, os


def _interpolate(t, w0, w1, idx):
    'interpolate w0 and w1 at t, using tw=w[idx]'
    assert len(w0) == len(w1)

    tw0 = w0[idx]  # time of w0
    tw1 = w1[idx]  # time of w1
    dt = tw1 - tw0  # time interval length

    # interpolate (if else to minimize roundoff error)
    a = (t - tw0) / dt
    if a > 0.5:
        return [w0 * (1.0 - a) + w1 * a for w0, w1 in zip(w0, w1)]
    else:
        b = (tw1 - t) / dt
        return [w0 * b + w1 * (1.0 - b) for w0, w1 in zip(w0, w1)]

def _printinfo(t):
    print '%s, %d rows, t0=%s, columns:' % (t.attrs['TITLE'], t.nrows, t.attrs['t0'])
#    for col, unit in zip(t.colnames, json.loads(t.attrs.units)):
#        print '%s [%s],' % (col, unit),
#    print '\n'



def merge(primary_file, secondary_file = None, outfile = None, primary_table = None, secondary_table = None, merge_on = 'time', max_inter = 4 * 3600, quiet = False):
    # open data file(s)
    if outfile is None:
        h5pri = h5out = t.openFile(primary_file, 'r+')
    else:
        h5pri = t.openFile(primary_file, 'r')
        h5out = t.openFile(outfile, 'w')

    if secondary_file is None or os.path.abspath(primary_file) == os.path.abspath(secondary_file):
        h5sec = h5pri
    else:
        h5sec = t.openFile(secondary_file, 'r')

    with h5pri, h5sec, h5out:

        # open event table and read t0
        pri_table = h5pri.getNode(primary_table)
        _printinfo(pri_table)
        t0e = dp.parse(pri_table.attrs.t0)
        eunits = list(json.loads(pri_table.attrs.units))
        assert pri_table.nrows > 1

        # open weather table and read t0
        sec_table = h5sec.getNode(secondary_table)
        _printinfo(sec_table)
        t0w = dp.parse(sec_table.attrs.t0)
        wunits = list(json.loads(sec_table.attrs.units))
        assert sec_table.nrows > 1

        # global t0 is the smaller one
        t0 = min(t0w, t0e)
        print "global reference time t0 =", t0

        # time offset for weather, to adjust for new global t0
        toffw = (t0w - t0).total_seconds()
        if toffw != 0:
            print "weather time offset =", toffw

        # time offset for events, to adjust for new global t0
        toffe = (t0e - t0).total_seconds()
        if toffe != 0:
            print "  event time offset =", toffe

        # get column index for 'time' in each table
        etime = pri_table.colnames.index(merge_on)
        wtime = sec_table.colnames.index(merge_on)

        # build column descriptors for table of merged data
        merged_descriptor = OrderedDict()  # keep the order
        for k in pri_table.colnames:
            merged_descriptor[k] = pri_table.coldescrs[k]

        # add cols of weather table
        weather_colnames = list(sec_table.colnames)  # work on copy
        weather_colnames.pop(wtime)  # remove 'time' column
        for k in weather_colnames:  # add remaining cols
            merged_descriptor[k] = sec_table.coldescrs[k].copy()

        # adjust position fields (column order in descriptors)
        for i, v in enumerate(merged_descriptor.values()):
            v._v_pos = i

        # merge unit description
        merged_units = eunits
        wunits.pop(wtime)
        merged_units.extend(wunits)

        # create table for merged data
        try:
            merged = h5out.getNode('/merged')
        except:
            merged = h5out.createGroup(h5out .root, 'merged', 'merged data')

        merged_table = h5out.createTable(merged, os.path.basename(primary_table), merged_descriptor,
                                       pri_table._v_title + ' merged with ' + sec_table._v_title ,
                                       expectedrows = pri_table.nrows)
        set_attrs(merged_table, t0, tuple(merged_units))  # store new global t0 with this table
        row = merged_table.row

        _printinfo(merged_table)

        # get the first TWO weather rows, i.e. the first weather interval
        weather_iterator = sec_table.iterrows()
        weather_0 = weather_iterator.next()[:]
        tw0 = weather_0[wtime] + toffw
        weather_1 = weather_iterator.next()[:]
        tw1 = weather_1[wtime] + toffw

        # start console progress bar
        print "merging data..."
        if not quiet:
            pb = ProgressBar(maxval = pri_table.nrows,
                             widgets = [Bar(), ' ', Percentage(), ' ', ETA()], fd = sys.stdout)
            pb.start()

        # loop over events
        event_counter = 0
        for event in pri_table:
            if not quiet:
                pb.update(pb.currval + 1)  # update progress bar

            # skip to next event if weather too new
            te = event[etime] + toffe  # adjust for global t0, apply offset
            if te < tw0:  # if eventime < start of weather interval...
                continue

            try:  # skip to next pair of weather data until the event is contained
                while not (tw0 <= te <= tw1):
                    weather_0 = weather_1  # shift 1 -> 0
                    tw0 = weather_0[wtime] + toffw  # adjust for global t0, apply offset
                    weather_1 = weather_iterator.next()[:]  # get next weather row as tuple (do [:])
                    tw1 = weather_1[wtime] + toffw  # adjust for global t0, apply offset

            except StopIteration:
                break  # exit event loop if there are no more weather rows

            # skip event if weather interval too long (weather regarded as invalid)
            if (tw1 - tw0) > max_inter:
                continue

            # interpolate weather data to event time
            winterp = _interpolate(te, weather_0, weather_1, wtime)
            winterp.pop(wtime)  # remove 'time' col from interpolated weather

            # merged data: event with weather data
            ew = list(event[:])  # copy event data
            ew[etime] = te;  # update event time (because of offset)
            ew.extend(winterp)  # add interpolated weather data

            assert len(merged_descriptor) == len(ew)  # length must match

            # write newly merged data into row
            for k, v in zip(merged_descriptor.keys(), ew):
                row[k] = v

            # append row
            row.append()
            event_counter += 1  # count merged events

        if not quiet:
            pb.finish()  # finish progress bar

        merged_table.flush()  # force writing the table

        # output status information
        print "merged %d of %d events, skipped %d" % (event_counter, pri_table.nrows, pri_table.nrows - event_counter)
        print "first merged record", seconds2datetime(t0, merged_table[0][etime])
        print " last merged record", seconds2datetime(t0, merged_table[-1][etime])






def main():
    from argparse import ArgumentParser
    import ctplot

    parser = ArgumentParser(description = 'merge two tables in a HDF5 file', epilog = ctplot.__epilog__)

    parser.add_argument('-V', '--version', action = 'version', version = '%(prog)s {} build {}'.format(ctplot.__version__, ctplot.__build_date__))
    parser.add_argument('-m', '--merge', metavar = 'column', default = 'time', help = 'column to merge on (default: time)')
    parser.add_argument('-x', '--maxint', metavar = 'seconds', type = float, default = 4 * 3600, help = 'max. interval length in secondary table (default: 4h)')
    parser.add_argument('-o', '--out', metavar = 'file', help = 'HDF5 output file (default: write to file_1)')
    parser.add_argument('-f', '--force', action = 'store_true', help = 'overwrite existing file')
#    parser.add_argument('-a', '--append', action = 'store_true', help = 'append new data to existing file/table')
    parser.add_argument('-q', '--quiet', action = 'store_true', help = 'do not show progressbar, just print error messages')
    parser.add_argument('file_1', help = 'HDF5 file with primary table')
    parser.add_argument('table_1', help = 'name of primary table (event table)')
    parser.add_argument('file_2', help = 'HDF5 file with secondary table (may be the same as file_1)')
    parser.add_argument('table_2', help = 'name of secondary table (weather table)')


    opts = parser.parse_args()

    out = opts.out
    if out:
        if not out.endswith('.h5'):
            out = out + '.h5'

        if not opts.force and os.path.exists(out):
            raise RuntimeError('file \'{}\' already exists'.format(out))

    merge(opts.file_1, opts.file_2, outfile = out, primary_table = opts.table_1, secondary_table = opts.table_2,
          merge_on = opts.merge, max_inter = opts.maxint, quiet = opts.quiet)


if __name__ == '__main__':
    main()
