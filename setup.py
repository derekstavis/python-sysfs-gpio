#/usr/bin/env python

'''The setup and build script for the SysFS GPIO project.'''

from setuptools import setup, find_packages

__name__         = 'sysfs-gpio'
__description__  = 'Linux SysFS GPIO Access'
__author__       = 'Derek Willian Stavis'
__version__      = '0.2.2'
__author_email__ = 'dekestavis@gmail.com'
__author_site__  = 'http://derekstavis.github.io'

requirements = ['Twisted>=13.1.0']

setup(
    name                 = __name__,
    description          = __description__,
    version              = __version__,
    author               = __author__,
    author_email         = __author_email__,
    url                  = __author_site__,

    install_requires     = requirements,
    include_package_data = True,

    packages = find_packages(),  # include all packages under src
)
