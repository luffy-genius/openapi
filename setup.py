#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Date: 2022/6/20
import re
import os
from setuptools import setup, find_packages


def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", init_py).group(1)


version = get_version('openapi')

setup(
    name='openapi',
    version=version,
    description='openapi tools',
    long_description='openapi tools',
    classifiers=[],
    keywords='openapi',
    author='ZhiChao Liu',
    author_email='liuzhichao9527@gmail.com',
    url='https://github.com/csrftoken',
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=True,
    install_requires=[
        'httpx',
        'pydantic',
        'pycryptodome',
        'cryptography'
    ],
    entry_points={
      'console_scripts': []
    }
)
