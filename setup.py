"""Python based sport sync routines
"""

import io
import os
from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / "README.md").read_text(encoding="utf-8")


def read(*paths, **kwargs):
    """Read the contents of a text file safely.
    >>> read("project_name", "VERSION")
    '0.1.0'
    >>> read("README.md")
    ...
    """

    content = ""
    with io.open(
        os.path.join(os.path.dirname(__file__), *paths),
        encoding=kwargs.get("encoding", "utf8"),
    ) as open_file:
        content = open_file.read().strip()
    return content


def read_requirements(path):
    return [
        line.strip()
        for line in read(path).split("\n")
        if not line.startswith(('"', "#", "-", "git+"))
    ]


setup(
    name="SportSync",  # Required
    version="0.1.0",
    description="Python library to sync between various sport APIs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/stuwilkins/sportsync",
    author="Stuart B. Wilkins",
    author_email="stuart@stuwilkins.org",
    # For a list of valid classifiers, see https://pypi.org/classifiers/
    # classifiers=[  # Optional
    #     # How mature is this project? Common values are
    #     #   3 - Alpha
    #     #   4 - Beta
    #     #   5 - Production/Stable
    #     "Development Status :: 3 - Alpha",
    #     # Indicate who your project is intended for
    #     "Intended Audience :: Developers",
    #     "Topic :: Software Development :: Build Tools",
    #     # Pick your license as you wish
    #     "License :: OSI Approved :: MIT License",
    #     # Specify the Python versions you support here. In particular, ensure
    #     # that you indicate you support Python 3. These classifiers are *not*
    #     # checked by 'pip install'. See instead 'python_requires' below.
    #     "Programming Language :: Python :: 3",
    #     "Programming Language :: Python :: 3.7",
    #     "Programming Language :: Python :: 3.8",
    #     "Programming Language :: Python :: 3.9",
    #     "Programming Language :: Python :: 3.10",
    #     "Programming Language :: Python :: 3 :: Only",
    # ],
    keywords="sport, strava, nokia, garmin, withings",
    packages=find_packages(exclude=["tests", ".github"]),
    python_requires=">=3.7, <4",
    install_requires=read_requirements("requirements.txt"),
    # Entry points. The following would provide a command called `sample` which
    # executes the function `main` from this package when invoked:
    entry_points={
        "console_scripts": [
            "sportsync=SportSync.console:sync",
        ],
    },
    # project_urls={  # Optional
    #     "Bug Reports": "https://github.com/pypa/sampleproject/issues",
    #     "Funding": "https://donate.pypi.org",
    #     "Say Thanks!": "http://saythanks.io/to/example",
    #     "Source": "https://github.com/pypa/sampleproject/",
    # },
)
