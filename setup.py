#! /usr/bin/env python
# Date: 2022/6/20
import os
import re

from setuptools import find_packages, setup

with open('README.md', encoding='utf-8') as fd:
    long_description = fd.read()


def get_version(package):
    """Return package version as listed in `__version__` in `init.py`."""
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search('__version__ = [\'"]([^\'"]+)[\'"]', init_py).group(1)


version = get_version('openapi')

setup(
    name='openapipy',
    version=version,
    description='openapi tools',
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[],
    keywords='openapi,openapi-python,python-openapi,openapipy,pyopenapi',
    author='ZhiChaoLiu',
    author_email='liuzhichao9527@gmail.com',
    url='https://github.com/luffy-genius/openapi',
    license='MIT',
    packages=find_packages(exclude=('examples',)),
    include_package_data=True,
    zip_safe=True,
    install_requires=['httpx', 'pydantic', 'pycryptodome', 'cryptography'],
    entry_points={'console_scripts': []},
)
