#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Have a look at https://pythonhosted.org/setuptools
# http://stackoverflow.com/questions/7522250/how-to-include-package-data-with-setuptools-distribute
# http://stackoverflow.com/questions/1231688/how-do-i-remove-packages-installed-with-pythons-easy-install
# http://stackoverflow.com/questions/6344076/differences-between-distribute-distutils-setuptools-and-distutils2?answertab=active#tab-top
from ez_setup import use_setuptools
use_setuptools()

import os
from datetime import datetime
from subprocess import check_output
from setuptools import setup, find_packages

#   https://pythonhosted.org/setuptools/setuptools.html#non-package-data-files
#   http://peak.telecommunity.com/DevCenter/PythonEggs#accessing-package-resources
from pkg_resources import resource_string, resource_filename, require

required_libs = ['matplotlib >=1.1', 'numpy >=0.9', 'scipy >=0.12', 'pytz', 'numexpr >=1.4',
                 'tables >=2.2', 'python-dateutil >=1.5', 'Pillow >=3.1.0', 'basemap >=1.0', 'locket']

def readme(name):
    """Utility function to read the README file.
       Used for the long_description.  It's nice, because now
       1) we have a top level README file and
       2) it's easier to type in the README file than to put a raw string in below"""
    return resource_string(__name__, name)


def update_version():
    cwd = os.path.dirname(__file__)
    version = '1.3b0' # see PEP 440
    revision = 'unknown'
    try:
        revision = check_output('git describe --dirty=+', shell = True, cwd = cwd).strip()
    except:
        pass
    version_py = 'ctplot/__version__.py'
    build_date = '{:%F %T}'.format(datetime.now())
    with open(os.path.join(cwd, version_py), 'w') as f:
        f.write("__version__ = '{}'\n".format(version))
        f.write("__revision__ = '{}'\n".format(revision))
        f.write("__build_date__ = '{}'\n".format(build_date))
    print 'updated', version_py, 'to', version, revision, build_date

update_version()

import ctplot

setup(
    name = ctplot.__name__,
    version = ctplot.__version__,
    author = ctplot.__author__,
    author_email = ctplot.__author_email__,
    description = ctplot.__description__,
    license = ctplot.__license__,
    url = ctplot.__url__,
    packages = find_packages(),
    long_description = readme('README.md'),
    install_requires = required_libs,
    extra_require = {
                        'server': ['tornado']
    },
    entry_points = {'console_scripts':[
                        'rawdata=ctplot.rawdata:main',
                        'mergedata=ctplot.merge:main',
                        'ctplot=ctplot.plot:main',
                        'ctserver=ctplot.webserver:main'
                   ]},
    package_data = {
                    'ctplot':['web/*.*', 'web/*/*.*', 'web/*/*/*.*']
                   },
    zip_safe = True
)



