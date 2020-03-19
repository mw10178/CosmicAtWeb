# ctplot

ctplot is a tool to create various kinds plots from and to perform
statistical analysis on tabular data stored in HDF5 files. The plots
are created from the command line or via an interactive web interface.

Included is an extensible tool to convert raw data into HDF5 tables.

## Installation
To install ctplot, download the ZIP, extract it and run `setup.py` or just run

    # pip install https://github.com/quantenschaum/ctplot/archive/master.zip
  
  
## Use with Apache
To use ctplot with an Apache webserver, create a `ctplot.wsgi` somewhere on your server containing

    #!/usr/bin/env python

    from ctplot.wsgi import application

Set the following environment variables to configure the data directories

    CTPLOT_BASEDIR=/data
    CTPLOT_DATADIR=/data/data
    CTPLOT_CACHEDIR=/data/cache
    CTPLOT_PLOTDIR=/data/plots
    CTPLOT_SESSIONDIR=/data/sessions

It's only neccessary to set `CTPLOT_BASEDIR`. The other paths are subdirectories of basedir, which can be overridden by setting them explicitly.

### Run with mod_wsgi
Enable [mod_wsgi](https://code.google.com/p/modwsgi) and in your apache config set a `WSGIScriptAlias` like

    WSGIApplicationGroup %{GLOBAL}
    WSGIDaemonProcess ctplot processes=2 threads=20
    WSGIScriptAlias /ctplot /path/to/ctplot.wsgi
    
Set `processes` to the number of plot creating processes that are allowed to run in parallel (number of cores).

### Run as cgi-script
To run ctplot as simple CGI script with [mod_cgi](http://httpd.apache.org/docs/current/mod/mod_cgi.html), create `ctplot.py` containing

    #!/usr/bin/env python

    from ctplot.wsgi import application

    # this allows the WSGI app to be run as CGI script
    if __name__ == '__main__':
        import wsgiref.handlers
        wsgiref.handlers.CGIHandler().run(application)

and put it into your server tree and register it with a CGI handler. 

### Run as standalone app
Run `ctserver` (depends on [tornado](http://www.tornadoweb.org)) to run ctplot as standalone webserver. You may set the environment variable `CTPLOT_PORT` to set a port different from the default of 8080 and `CTPLOT_ADDRESS` to specify a listening address. If `CTPLOT_ADDRESS` is not set, the webserver will listen on all addresses.


## Run as Docker container
Use the `Dockerfile` to create a [Docker](https://www.docker.com/) image. 

    docker build -t ctplot .

To run the image do

    docker run -p 8080:8080 -v /path/to/data:/data ctplot


