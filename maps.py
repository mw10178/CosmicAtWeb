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
import matplotlib.pyplot as plt
import dateutil.parser as dp
import ticks
import mpl_toolkits.basemap as bm
import sys

def drawmap(lat = None, lon = None, margin = 0.05, width = 1e6, height = None, boundarylat = 40,
         projection = 'cyl', drawcoastline = 1, drawcountries = 0, drawgrid = 1, drawspecgrid = 1, bluemarble = 0, nightshade = None,
         places = [('Neumayer-St.'    , -70.6666      , -8.2666),
                   ('Amundsen-Scott-St.'   , -90.     , 0.),
                   ('DESY Zeuthen'  , 52.346142    , 13.633432)]):

    sys.stdout = sys.__stderr__

    minlat, maxlat = np.nanmin(lat), np.nanmax(lat)
    lat0 = (minlat + maxlat) / 2
    minlat, maxlat = minlat - margin * (maxlat - minlat), maxlat + margin * (maxlat - minlat)
    minlat, maxlat = max(-90, minlat), min(90, maxlat)

    minlon, maxlon = np.nanmin(lon), np.nanmax(lon)
    lon0 = (minlon + maxlon) / 2
    minlon, maxlon = minlon - margin * (maxlon - minlon), maxlon + margin * (maxlon - minlon)
    #minlon, maxlon = max(-90,minlon), min(90,maxlon)

    if projection in ('ortho', 'robin'):
        map_options = { 'lat_0' : lat0, 'lon_0' : lon0, 'resolution':'l'}
        latlabels = [1, 0, 0, 0] # left, right, top, bottom
        lonlabels = [0, 0, 0, 1]
    elif projection in ('npaeqd', 'nplaea', 'npstere', 'spaeqd', 'splaea', 'spstere'): # polar
        if projection.startswith('s'):
            boundarylat = -abs(boundarylat)
        else:
            boundarylat = abs(boundarylat)
        map_options = { 'lat_0' : lat0, 'lon_0' : lon0, 'boundinglat' :boundarylat, 'resolution':'l'}
        latlabels = [0, 0, 1, 1]
        lonlabels = [1, 1, 0, 0]
    elif projection in ('cyl', 'merc'):
        map_options = { 'llcrnrlon' : minlon, 'llcrnrlat' : minlat, 'urcrnrlon' : maxlon, 'urcrnrlat' : maxlat, 'resolution':'i'}
        latlabels = [1, 0, 0, 0]
        lonlabels = [0, 0, 0, 1]
    elif projection in ('aeqd', 'laea', 'stere'):
        if height is None:
            height = width / np.sqrt(2)
        map_options = { 'lat_0' : lat0, 'lon_0' : lon0, 'width':width, 'height':height , 'resolution':'i'}
        latlabels = [1, 0, 0, 0]
        lonlabels = [0, 0, 0, 1]
    else:
        raise ValueError('unknow projection: ' + projection)

    #print map_options

    m = bm.Basemap(projection = projection, **map_options)

    if bluemarble:
        m.bluemarble(scale = 0.5)
        #m.warpimage(image = 'c:/Program Files (x86)/Python27/Lib/site-packages/mpl_toolkits/basemap/data/etopo1.jpg', scale = 0.5)
        #m.warpimage(image = 'c:/Users/al/Downloads/bluemarble/Earthlights_2002-5400x2700.jpg', scale = 0.5)
    elif drawcoastline:
        m.drawcoastlines(color = 'k')
        if drawcountries:
            m.drawcountries(color = 'k')
        #m.drawrivers(color = 'b')
        if projection in ('ortho'):
            m.drawlsmask(land_color = '#f7d081', lakes = True)
        else:
            m.fillcontinents(color = '#f7d081')

    if nightshade is not None:
        if isinstance(nightshade, basestring):
            datetime = dp.parse(nightshade)
        m.nightshade(datetime, color = 'k', delta = 0.25, alpha = 0.7)

    if drawgrid:
        if projection in ('ortho', 'robin', 'npaeqd', 'nplaea', 'npstere', 'spaeqd', 'splaea', 'spstere'):
            parallels, meridians = np.arange(-90, 90, 10), np.arange(-180, 180, 20)
        else:
            parallels, meridians = ticks.get_ticks(m.llcrnrlat, m.urcrnrlat, 6), ticks.get_ticks(m.llcrnrlon, m.urcrnrlon, 6)

        pmc = '0.6' if bluemarble else 'k'
        m.drawparallels(parallels, labels = latlabels, linewidth = 0.5, color = pmc)
        m.drawmeridians(meridians, labels = lonlabels, linewidth = 0.5, color = pmc)

    if drawspecgrid:
        ecl = 23.44 # ecliptic
        m.drawparallels([-90 + ecl, -ecl, ecl, 90 - ecl], dashes = [2, 2], linewidth = 0.5, color = pmc)
        m.drawparallels([0], dashes = [4,4], linewidth = 0.5, color = pmc)
        m.drawmeridians([0], dashes = [4,4], linewidth = 0.5, color = pmc)


    m.drawmapboundary(linewidth = 1.5, fill_color = 'white')

    for name, la, lo in places:
        x, y = m(lo, la)
        m.plot(x, y, 'rs', markersize = 4)
        plt.annotate(name, (x, y), textcoords = 'offset points', xytext = (5, 2))

    sys.stdout = sys.__stdout__

    return m

if __name__ == '__main__':
    import tables
    import matplotlib.mlab as mlab

    plt.rc('font', **{'family':'sans-serif', 'sans-serif':['Dejavu Sans'], 'size':10})
    plt.rc('axes', grid = True)
    plt.rc('lines', markeredgewidth = 0)
    ticks.set_extended_locator(1)
    plotwidth = 12
    plt.gcf().set_size_inches((plotwidth, plotwidth / np.sqrt(2)));
    f = 0.09
    plt.gca().set_position([f, f, 1 - 2 * f, 1 - 2 * f])

    f = tables.openFile('data/x-dwd.h5', 'r')

    zvalue = 'tm'
    time = set()
    zmin = np.inf
    zmax = -np.inf
    data_table = f.root.raw.weather
    for row in data_table:
        time.add(row['time'])
        zmin, zmax = min(zmin, row[zvalue]), max(zmax, row[zvalue])
    time = np.array(list(time))
    time = np.sort(time)
    print time

    for t in time:
        lat = []
        lon = []
        z = []

        for row in data_table.where('time=={}'.format(t)):
            lat.append(row['lat'])
            lon.append(row['lon'])
            z.append(row[zvalue])

        lat = np.array(lat)
        lon = np.array(lon)
        z = np.array(z)

#        ok = np.isfinite(lat) & np.isfinite(lon) & np.isfinite(z)
#        lat = lat[ok]
#        lon = lon[ok]
#        z = z[ok]

        map = drawmap(lat, lon, projection = 'cyl', drawcountries = 1)

        n = 300
        lone, late = np.meshgrid(np.linspace(lon.min() , lon.max() , n + 1), np.linspace(lat.min() , lat.max() , n + 1))
        lonc = (lone[1:, 1:] + lone[1:, :-1] + lone[:-1, 1:] + lone[:-1, :-1]) / 4
        latc = (late[1:, 1:] + late[1:, :-1] + late[:-1, 1:] + late[:-1, :-1]) / 4
        zg = mlab.griddata(lon, lat, z, lonc, latc)
#        zg[np.isnan(zg)] = -100

        x, y = map(lon, lat)
        xe, ye = map(lone, late)
        xc, yc = map(lonc, latc)
#        plt.pcolor(xe, ye, zg, edgecolor = 'none', zorder = 100, alpha = 0.7)
#        plt.contourf(xc, yc, zg, 20, vmin = -10, vmax = 10, zorder = 100, alpha = 0.8)
        plt.tricontourf(x, y, z, 20, zorder = 100, alpha = 0.7)
#        plt.tripcolor(x, y, z, edgecolor = 'none', zorder = 100, alpha = 0.7)
        plt.clim(zmin, zmax)

        plt.scatter(x, y, c = z, edgecolor = 'none', zorder = 50)
        plt.clim(zmin, zmax)

        plt.colorbar()
        plt.show()

    f.close()

