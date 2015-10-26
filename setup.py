#!/usr/bin/env python

from rabird_bootstrap import use_pip
use_pip()

import sys
import glob
from setuptools import setup, find_packages

package_name = "u8gettext"

our_packages = find_packages()
    
our_requires = [
    "six>=1.3.0",
    "polib",
    ]
    
if sys.platform == "win32":
    try:
        import bdflib
    except:
        import pip
        # Because bdflib 1.0.1 currently in pypi can't install on windows, so 
        # we install a modified version from our repository.
        pip.main(["install", "https://gitlab.com/starofrainnight/bdflib/repository/archive.zip?ref=starofrainnight"])
else:
    our_requires.append("bdflib")

long_description=(
     open("README.rst", "r").read()
     + "\n" +
     open("CHANGES.rst", "r").read()
     )

setup(
    name=package_name,
    version="0.0.1",
    author="Hong-She Liang",
    author_email="starofrainnight@gmail.com",
    url="https://github.com/starofrainnight/%s" % package_name,
    description="A series helper scripts for U8Gettext library",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",        
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent", 
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: Implementation :: CPython",        
        "Topic :: Software Development :: Libraries",
    ],
    install_requires=our_requires,
    packages=our_packages,
    entry_points={
        'console_scripts':[
            'u8gettext-gen-data = u8gettext.console_scripts:gen_data',
        ],
    },
    )
