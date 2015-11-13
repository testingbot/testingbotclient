#!/usr/bin/env python

"""setup/install script for testingbotclient."""


import os
from distutils.core import setup
from testingbotclient import __version__


setup(
    name='testingbotclient',
    version=__version__,
    py_modules=['testingbotclient'],
    author='TestingBot',
    author_email='info _at_ testingbot.com',
    description='Python client library for TestingBot API.',
    long_description='Update test details on TestingBot.com with this library. Set success state/name of test after running the Selenium test.',
    url='https://github.com/testingbot/testingbotclient',
    download_url='http://pypi.python.org/pypi/testingbotclient',
    keywords='testingbot selenium testing'.split(),
    license='Apache v2.0',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Testing',
    ]
)
