# encoding: utf-8
"""
This submodule defines classes which load a page and verify/ensure that it's in an expected state
(a user is logged in, required dynamic elements are fully loaded, etc.).
"""

from functools import partial as _partial

from attrs import define as _define, field as _field, validators as _validators
from selenium.webdriver.remote.webdriver import WebDriver as _BrowserDriver

from .common import convert_to_string_or_none as _convert_to_string_or_none
from . import defaults as _d
from .defaults import get_setting as _get_setting

import typing as _t
from typing import (
	Optional as _O,
	Union as _U
)


T = _t.TypeVar('T')

_validator_str = _validators.instance_of(str)
_validator_str_or_none = _validators.instance_of((str, type(None)))

_convert_to_string_or_none_no_strip = _partial(_convert_to_string_or_none, strip=False)


@_define
class _BasePageLoader:
	"""Base class for all page loaders."""

	browser: _BrowserDriver = _field(validator=_validators.instance_of(_BrowserDriver))
	url: _O[str] = _field(validator=_validator_str_or_none)

	@staticmethod
	def _sequence_converter(value: _U[T, _t.Iterable[T]]) -> _t.Tuple[T, ...]:
		""":mod:`attrs` converter for an expected sequence of :class:`_BasePageLoader` objects."""
		if isinstance(value, (_BasePageLoader, str)):  # str - just to avoid turning 'val' into ('v', 'a', 'l')
			return (value, )
		try:
			return tuple(value)
		except (TypeError, ValueError):
			# noinspection PyTypeChecker
			return (value, )


@_define
class Loginer(_BasePageLoader):
	"""Special loader which ensures a user is logged in."""
	login_name: _O[str] = _field(
		factory=lambda: _d.Login.USER,
		converter=_convert_to_string_or_none_no_strip,
		validator=_validator_str_or_none
	)
	login_password: _O[str] = _field(
		factory=lambda: _d.Login.PASSWORD,
		converter=_convert_to_string_or_none_no_strip,
		validator=_validator_str_or_none
	)


@_define
class PageLoader(_BasePageLoader):
	"""Regular page loader. Used most of the time."""
	pass


@_define
class SequenceLoader(_BasePageLoader):
	"""A loader which executes multiple other loaders in a sequence."""
	loaders: _t.Tuple[_BasePageLoader, ...] = _field(
		converter=_BasePageLoader._sequence_converter,
		validator=_validators.deep_iterable(
			_validators.instance_of(_BasePageLoader),
			iterable_validator=_validators.and_(_validators.instance_of(tuple), _validators.min_len(1)),
		),
	)


if __name__ == '__main__':
	_qqq = Loginer(None, 'qqq', 'www')
	_qqq = PageLoader(None, 'www')
