from setuptools import setup, find_packages

# To use a consistent encoding
from codecs import open
from pip.req import parse_requirements
from pip.download import PipSession
import os

# parse_requirements() returns generator of pip.req.InstallRequirement objects
install_reqs = parse_requirements(
    'requirements/install.txt', session=PipSession()
)
reqs = [str(ir.req) for ir in install_reqs]

here = os.path.abspath(os.path.dirname(__file__))

# Get the long description from the relevant file
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

about = {}

with open(os.path.join(here, "monkeystud", "__about__.py")) as f:
    exec(f.read(), about)

setup(
    name=about['__title__'],

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version=about['__version__'],
    description=about['__summary__'],
    long_description=long_description,
    url=about['__uri__'],
    author=about['__author__'],
    author_email=about['__email__'],
    license=about['__license__'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Application',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],
    packages=find_packages(exclude=['docs', 'tests*']),
    include_package_data=True,
    zip_safe=True,
    install_requires=reqs,
    entry_points={
        'console_scripts': [
            'monkeystud=monkeystud.cli:main',
        ],
    },
    setup_requires=['setuptools-git'],
)
