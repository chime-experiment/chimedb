from setuptools import setup, find_packages

import codecs
import os
import re

# Get the version from __init__.py without having to import it.
def _get_version():
    with codecs.open(
        os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "chimedb", "core", "__init__.py"
        ),
        "r",
    ) as init_py:
        version_match = re.search(
            r"^__version__ = ['\"]([^'\"]*)['\"]", init_py.read(), re.M
        )

        if version_match:
            return version_match.group(1)
        raise RuntimeError("Unable to find version string.")


setup(
    name="chimedb",
    version=_get_version(),
    packages=find_packages(),
    zip_safe=False,
    install_requires=[
        "mysqlclient",
        "peewee >= 3.10",
        "sshtunnel",
        "ujson",
        "future",
        "PyYAML",
    ],
    author="The CHIME Collaboration",
    author_email="dvw@phas.ubc.ca",
    description="Low-level CHIME database access",
    license="GPL v3.0",
    url="https://github.com/chime-experiment/chimedb",
)
