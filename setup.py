#!/usr/bin/env python3

from setuptools import setup
from latex2svg import VERSION

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name='latex2svg',
    version=VERSION,
    description='Converts LaTeX math code to SVG using pdflatex, dvisvgm, and scour',
    long_description_content_type="text/markdown",
    long_description=long_description,
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: Public Domain',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Intended Audience :: Science/Research',
        'Intended Audience :: System Administrators',
        'Programming Language :: Python :: 3',
        'Topic :: Multimedia :: Graphics :: Graphics Conversion',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Software Development :: Pre-processors',
        'Topic :: Utilities',
    ],
    keywords='latex converter math formula svg optimizer affinity designer',
    url='http://github.com/vlarroque/latex2svg',
    author='vlarroque',
    author_email='',
    license='Public Domain',
    packages=['latex2svg'],
    entry_points={
        'console_scripts': ['latex2svg=latex2svg:main'],
    },
    python_requires='>=3',
    install_requires=[
        'lxml',
        'scour',
        'pyperclip'
    ],
    include_package_data=True,
    zip_safe=False,
)
