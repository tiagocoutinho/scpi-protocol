# -*- coding: utf-8 -*-

"""The setup script."""

import sys
from setuptools import setup, find_packages


TESTING = any(x in sys.argv for x in ["test", "pytest"])

install_requirements = ['numpy']

setup_requirements = []
if TESTING:
    setup_requirements += ['pytest-runner']
test_requirements = ['pytest', 'pytest-cov']

with open('README.md') as f:
    description = f.read()

setup(
    name='scpi-protocol',
    author="Jose Tiago Macara Coutinho",
    author_email='coutinhotiago@gmail.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
    description="Sans I/O SCPI protocol parser",
    license="GPLv3+",
    long_description=description,
    long_description_content_type='text/markdown',
    keywords='SCPI, parser',
    packages=find_packages(),
    install_requires=install_requirements,
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://gitlab.com/tiagocoutinho/scpi-protocol/',
    version='0.2.0',
    python_requires='>=3.5',
    zip_safe=True
)
