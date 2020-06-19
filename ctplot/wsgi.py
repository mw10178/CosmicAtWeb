#!/usr/bin/env python
# coding: utf8

from i18n import _
from utils import hashargs
import validation
import plot
import os
import json
import random
import string
import logging
from numbers import Number
from os.path import join, abspath, basename
from mimetypes import guess_type
from time import time
from cgi import FieldStorage
from threading import Lock
from pkg_resources import resource_string, resource_exists, resource_isdir, resource_listdir
from itertools import product

import matplotlib
matplotlib.use('Agg')  # headless backend


logging.basicConfig(level=logging.DEBUG,
                    format='%(filename)s:%(funcName)s:%(lineno)d:%(message)s')

log = logging.getLogger('wsgi')

_config = None


def get_config():
    global _config

    if _config:
        return _config

    env = os.environ
    prefix = 'ctplot_'
    basekey = (prefix + 'basedir').upper()
    basedir = abspath(env[basekey] if basekey in env else 'data')

    _config = {'cachedir': join(basedir, 'cache'),
               'datadir': join(basedir, 'data'),
               'plotdir': join(basedir, 'plots'),
               'sessiondir': join(basedir, 'sessions'),
               'ex_sessiondir': join(basedir, 'ex_sessions')}

    for k in _config.keys():
        ek = prefix + k.upper()
        if ek in env:
            _config[k] = env[ek]

    _config['debug'] = True if (prefix + 'debug').upper() in env else False

    log.debug('config: {}'.format(_config))

    return _config


def getpath(environ):
    return environ['PATH_INFO'] if 'PATH_INFO' in environ else ''


# This is our application object. It could have any name,
# except when using mod_wsgi where it must be "application"
# see http://webpython.codepoint.net/wsgi_application_interface
def application(environ, start_response):
    path = getpath(environ)
    if path == '/webplot.py' or path.startswith('/plot'):
        return dynamic_content(environ, start_response)
    else:
        return static_content(environ, start_response)


# http://www.mobify.com/blog/beginners-guide-to-http-cache-headers/
# http://www.mnot.net/cache_docs/
# http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html
cc_nocache = 'Cache-Control', 'no-cache, max-age=0'
cc_cache = 'Cache-Control', 'public, max-age=86400'


def content_type(path=''):
    mime_type = None

    if path:
        mime_type = guess_type(path)[0]

    if not mime_type:
        mime_type = 'text/plain'

    return 'Content-Type', mime_type


def static_content(environ, start_response):
    path = getpath(environ)

    if not path:  # redirect
        start_response('301 Redirect', [content_type(
        ), ('Location', environ['REQUEST_URI'] + '/')])
        return []

    if path == '/':
        path = 'web/index.html'  # map / to index.html
    else:
        path = ('web/' + path).replace('//', '/')

    if path == 'web/js':  # combined java scripts
        scripts = {}
        for s in resource_listdir('ctplot', 'web/js'):
            scripts[s] = '\n// {}\n\n'.format(s) + \
                resource_string('ctplot', 'web/js/' + s)
        start_response('200 OK', [content_type('combined.js'), cc_cache])
        return [scripts[k] for k in sorted(scripts.keys())]

    if not resource_exists('ctplot', path):  # 404
        start_response('404 Not Found', [content_type()])
        return ['404\n', '{} not found!'.format(path)]

    elif resource_isdir('ctplot', path):  # 403
        start_response('403 Forbidden', [content_type()])
        return ['403 Forbidden']
    else:
        start_response('200 OK', [content_type(path), cc_cache])
        return resource_string('ctplot', path)


def dynamic_content(environ, start_response):
    path = getpath(environ)
    config = get_config()

    if path.startswith('/plots'):
        return serve_plot(path, start_response, config)
    else:
        return handle_action(environ, start_response, config)


def serve_plot(path, start_response, config):
    with open(join(config['plotdir'], basename(path))) as f:
        start_response('200 OK', [content_type(path), cc_cache])
        return [f.read()]


def serve_json(data, start_response):
    start_response('200 OK', [content_type(), cc_nocache])
    return [json.dumps(data)]


def serve_plain(data, start_response):
    start_response('200 OK', [content_type(), cc_nocache])
    return [data]


available_tables = None


def validate_settings(settings):
    global available_tables

    errors = {'global': [], 'diagrams': {}}
    valid = True

    try:
        pc = int(settings['plots'])
        if pc < 1:
            raise Exception
    except Exception:
        pc = 0
        for k in settings.keys():
            if k.startswith('experiment'):
                pc += 1

        if pc == 0:
            errors['global'].append(_('no plots detected'))
            return [False, errors]

    if not available_tables or time() - available_tables[0] > 86400:
        available_tables = time(), plot.available_tables(
            get_config()['datadir'])

    log.debug('settings to validate: {}'.format(settings))

    m0 = settings['m0']

    for N in xrange(pc):
        n = str(N)

        v = validation.FormDataValidator(settings)

        # experiment
        v.add('experiment' + n, validation.NotEmpty(),
              stop_on_error=True,
              title=_('experiment'))

        # diagram type
        v.add('m' + n, validation.Regexp('^' + m0 + '$',
                                         regexp_desc=_("diagram type of the first dataset")),
              stop_on_error=True,
              title=_('diagram type'))

        diagram_type = settings['m' + n]

        # dataset
        v.add('s' + n, validation.NotEmpty(),
              stop_on_error=True,
              title=_('dataset'))

        # x axis
        v.add('x' + n, validation.NotEmpty(),
              title=_('x-variable'))

        # y axis
        if diagram_type in ['xy', 'h2']:
            v.add('y' + n, validation.NotEmpty(),
                  title=_('y-variable'))

        # map only works on valid geo coords
        if diagram_type == 'map':
            v.add('x' + n, [validation.NotEmpty(),
                            validation.Regexp('^(lat|lon)',
                                              regexp_desc=_("latitude or longitude"))
                            ],
                  title=_('x-variable'))

            v.add('y' + n, [validation.NotEmpty(),
                            validation.Regexp('^(lat|lon)',
                                              regexp_desc=_('latitude or longitude'))
                            ],
                  title=_('y-variable'))

        # binning
        if diagram_type in ['h1', 'p']:
            # x-bins
            v.add('x' + n + 'b',
                  validation.Regexp('^(\s*[+]?[0-9]*\.?' +
                                    '[0-9]+\s*,)*(\s*[+]?[0-9]*\.?[0-9]+\s*)$',
                                    allow_empty=True,
                                    regexp_desc=_('comma-separated list of positive floating point numbers')),
                  title=_('x-bins count'))

        if diagram_type == 'h2':
            # x-bins
            v.add('x' + n + 'b', [validation.Float(allow_empty=True),
                                  validation.Gte(1, allow_empty=True)],
                  title=_('x-bins count'))

            # y-bins
            v.add('y' + n + 'b', [validation.Float(allow_empty=True),
                                  validation.Gte(1, allow_empty=True)],
                  title=_('y-bins count'))

        # get permitted expression variables
        permitted_vars = None
        if 's' + n in settings:
            for filename, dataset in available_tables[1].iteritems():
                if filename == settings['s' + n]:
                    permitted_vars = {}
                    # init dummy vars to 1
                    for cn in dataset.colnames:
                        permitted_vars[cn] = 1
                    if ('rw' + n) in settings and settings['rw' + n]:
                        for cn in ['rate', 'count', 'weight']:
                            permitted_vars[cn] = 1

        # x/y/z adjustment function
        for ax in 'xyz':
            v.add(ax + n + 'a',
                  validation.Expression(
                      transform=False,
                      args=permitted_vars,
                      return_type=Number
                  ),
                  title=_('adjustment function for %(axis)s-variable') % {'axis': ax})

        # data reduction
        # condition
        v.add('c' + n,
              validation.Expression(
                  transform=False,
                  args=permitted_vars,
                  return_type=bool
              ),
              title=_('condition'))

        # rate calculation
        # interval
        v.add('rw' + n, validation.Float(allow_empty=True),
              title=_('time interval'))

        # push
        v.add('rs' + n, validation.FloatRange(0, 1, exclude_min=True,
                                              allow_empty=True), title=_('push'))

        # weight
        v.add('rc' + n,
              validation.Expression(transform=False, args=permitted_vars),
              title=_('weight'))

        # fit validation
        if diagram_type in ['xy', 'h1', 'p']:
            # fit parameters
            try:
                fp = settings['fp' + n]
                fp = [float(_fp) for _fp in fp.split(',')]
            except Exception:
                # this will force fit function validation to fail
                fp = None

            # fit function validation with dummy value x = 1
            v.add('ff' + n,
                  validation.Expression(
                      transform=False,
                      args={'x': 1, 'p': fp},
                      return_type=Number
                  ),
                  title=_('fit function and/or parameters'))

            # fit linestyle
            v.add('fl' + n, validation.Regexp(
                '^([bgrcmykw]?(-|--|:|-.)?|(-|--|:|-.)?[bgrcmykw]?)$',
                regexp_desc=_('mathplotlib colors and linestyles')
            ),
                title=_('fit line style'))

        # statistics box validation
        if diagram_type in ['h1', 'h2']:
            v.add('sb' + n, validation.Regexp('^[nuomspewkxca]*$'),
                  title=_('statistics box'))

        # outline validation
        if diagram_type == 'h2':
            v.add('o' + n + 'levels', [validation.Int(allow_empty=True),
                                       validation.Gte(0, allow_empty=True)],
                  title=_('outlines'))

        # width, height and boundarylat
        if diagram_type == 'map':
            v.add('o' + n + 'width', [validation.Int(allow_empty=True),
                                      validation.Gte(1, allow_empty=True)],
                  title=_('detail width'))

            v.add('o' + n + 'height', [validation.Int(allow_empty=True),
                                       validation.Gte(1, allow_empty=True)],
                  title=_('detail height'))

            v.add('o' + n + 'boundarylat', validation.FloatRange(-90, 90,
                                                                 exclude_min=True, exclude_max=True, allow_empty=True),
                  title=_('boundary latitude for (N/S) polar'))

        # diagram options
        if diagram_type != 'h2':
            # markersize
            v.add('o' + n + 'markersize', validation.Float(allow_empty=True),
                  title=_('marker size'))

            # linewidth
            v.add('o' + n + 'linewidth', validation.Float(allow_empty=True),
                  title=_('line width'))

        valid = (v.validate() and valid)
        errors['diagrams'][n] = v.get_errors()

    # global fields
    v = validation.FormDataValidator(settings)

    # x/y/z-ranges: min/max
    for a, m in product(['xr', 'yr', 'zr'], ['min', 'max']):
        field = a + '-' + m
        if field in settings:
            v.add(field, validation.Float(), title=_(field))

    # twin axis: x2/y2-ranges: min/max
    for a, m in product(['xrtw', 'yrtw'], ['min', 'max']):
        field = a + '-' + m
        if field in settings:
            v.add(field, validation.Float(), title=_(field))

    # width, height
    for wh in ['width', 'height']:
        field = wh[0]
        if field in settings:
            v.add(field, validation.Float(), title=_(wh))

    valid = (v.validate() and valid)
    errors['global'] = v.get_errors()
    log.debug('validation errors: {}'.format(errors))

    # validate
    return [valid, errors]


plot_lock = Lock()


def make_plot(settings, config):
    basename = 'plot{}'.format(hashargs(settings))
    name = os.path.join(config['plotdir'], basename).replace('\\', '/')

    # try to get plot from cache
    if not config['debug'] and config['cachedir'] and os.path.isfile(name + '.png'):
        return [dict([(e, name + '.' + e) for e in ['png', 'svg', 'pdf']]), None]
    else:
        # lock long running plot creation
        with plot_lock:
            valid, errors = validate_settings(settings)

            if not valid:
                return [None, errors]

            p = plot.Plot(config, **settings)
            return [p.save(name), None]


def randomChars(n):
    return ''.join(random.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits) for _ in range(n))


def handle_action(environ, start_response, config):
    global available_tables
    fields = FieldStorage(fp=environ['wsgi.input'], environ=environ)
    action = fields.getfirst('a')
    datadir = config['datadir']
    sessiondir = config['sessiondir']
    ex_sessiondir = config['ex_sessiondir']

    if action in ['plot', 'png', 'svg', 'pdf']:

        settings = {}
        for k in fields.keys():
            if k[0] in 'xyzcmsorntwhfglp' or k[:10] == 'experiment':
                settings[k] = fields.getfirst(
                    k).strip().decode('utf8', errors='ignore')

        try:
            images, errors = make_plot(settings, config)
        except Exception as e:
            log.exception(e)
            errors = {'global': [_('unknown error')]}

        if errors:
            return serve_json({'errors': errors}, start_response)

        for k, v in images.items():
            images[k] = 'plots/' + basename(v)

        if action == 'plot':
            return serve_json(images, start_response)

        elif action in ['png', 'svg', 'pdf']:
            return serve_plot(images[action], start_response, config)

    elif action == 'list':
        if not available_tables or time() - available_tables[0] > 86400:
            available_tables = time(), plot.available_tables(datadir)
        return serve_json(available_tables[1], start_response)

    elif action == 'save':
        id = fields.getfirst('id').strip()
        if len(id) < 8:
            raise RuntimeError('session id must have at least 8 digits')
        data = fields.getfirst('data').strip()
        with open(os.path.join(sessiondir, '{}.session'.format(id)), 'w') as f:
            f.write(data.replace('},{', '},\n{'))
        return serve_json('saved {}'.format(id), start_response)

    elif action == 'load':
        id = fields.getfirst('id').strip()
        if len(id) < 8:
            raise RuntimeError('session id must have at least 8 digits')

        ex_sessions = [s for s in os.listdir(
            ex_sessiondir) if os.path.isfile(os.path.join(ex_sessiondir, s))]

        if '{}.session'.format(id) in ex_sessions:
            try:
                with open(os.path.join(ex_sessiondir, '{}.session'.format(id))) as f:
                    return serve_plain(f.read(), start_response)
            except:
                return serve_json('no data for {}'.format(id), start_response)
        else:
            try:
                with open(os.path.join(sessiondir, '{}.session'.format(id))) as f:
                    return serve_plain(f.read(), start_response)
            except:
                return serve_json('no data for {}'.format(id), start_response)

    elif action == 'newid':
        id = randomChars(16)
        while os.path.isfile(os.path.join(sessiondir, '{}.session'.format(id))):
            id = randomChars(16)
        return serve_plain(id, start_response)

    else:
        raise ValueError('unknown action {}'.format(action))
