#!/usr/bin/env python
# encoding: utf-8
"""
https://packaging.python.org/en/latest/guides/distributing-packages-using-setuptools/#setup-args
"""

from setuptools import setup

from os import path
import sys

import darlog_pypi

HERE = path.abspath(path.dirname(__file__))
SRC_DIR = "src"

sys.path.append(path.join(HERE, SRC_DIR))
from darlog import selenium_wrapper as the_module


NAME = the_module.__pypi_package__
SHORT_DESC = the_module.__doc__.strip()

# We use this to cross-link PyPi <-> GitHub pages (header in readme text is updated during build):
LONG_DESC = darlog_pypi.ReadmeUpdater.from_rel_path(HERE, "README.md", NAME).update_for_github().text_for_pypi()


setup(
	version=the_module.__version__,
	description=SHORT_DESC,
	long_description=LONG_DESC,
	long_description_content_type="text/markdown",
	# https://packaging.python.org/en/latest/specifications/core-metadata/#description-content-type-optional

	url=the_module.__url__,
	author=the_module.__author__,
	maintainer=the_module.__author__,
	license=the_module.__license__,
)
