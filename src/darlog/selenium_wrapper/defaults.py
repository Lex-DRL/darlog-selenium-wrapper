# encoding: utf-8
"""
A submodule defining global package defaults - see :attr:`Browser` object.
"""

import os as _os

from attrs import define as _define, field as _field, validators as _validators

from .common import (
	Vector2DOptionalInt as _IntVector2D,
	StrPath as _StrPath,
	convert_to_string_or_none as _to_string_none,
	validator_validator as _val_val,
	T as _T
)

import typing as _t
from typing import Optional as _O


_window_size_validators: _t.List[_t.Callable] = [
	_validators.instance_of(_IntVector2D),
	_IntVector2D.ValidatorGE(2, 2)  # Why would anyone create a window smaller than 2 pixels?
]


@_define
class __BrowserDefaults:
	"""
	A container for all the global defaults.

	TL;DR
	-----

	You should **NOT** instantiate this class directly and should only use the pre-defined instance instead,
	except for *VERY* odd and complicated scenarios *(in which case, you should think hard of whether you need
	this package at all, or maybe you better of with just raw Selenium)*.

	Specifics
	-----

	Since you've got to this docstring, you should know that the defaults should be kept intact or at most monkey-patched
	at the very start of your app, before any of the other package's classes/functions are instantiated/called. And this
	monkey-patching-initialisation should be **VERY CLEAR** in your codebase.

	If the defaults are changed later, they might be applied only partially (if at all) to any pre-instantiated objects,
	leading to some unexpected behavior.

	.. note::

		There supposed to be only a single instance of this class as a "static" meta-sub-class in this module,
		but unfortunately :mod:`attrs` don't play nice with metaclasses.
		Therefore, the pre-defined class instance in this submodule is just a regular object and not a static class,
		but you still should treat it as such.

		Just use it "as is" and don't create any new :class:`__BrowserDefaults` instances,
		**unless you REALLY know what you're doing**.

	By "knowing what you're doing" the following edge case is meant as probably THE ONLY valid use for
	multiple :class:`__BrowserDefaults` instances:

		- You **REALLY** need to have multiple *sets* of defaults for different parts of your program.
		- In such a case, you can pre-instantiate all of them but only keep one as active at a time.
		- "Keeping active" means assigning it to the pre-defined name (``Browser``) in this module (by monkey-patching it).
		- You'll need to have your own manager for those defaults variants, keeping track of them and juggling them around:
			-
				You re-assign it to the desired :class:`__BrowserDefaults` instance BEFORE accessing a specific class/function
				which uses defaults (for example, before instantiating :class:`selenium_wrapper.firefox.BrowserConfig`).
			-
				All the package's classes/functions look up defaults by accessing them as the module member every time
				(``defaults.Browser``), so they catch a new reassigned instance immediately.
			-
				Be wary to always do the same yourself and **NEVER** cache the default instance with something like::

					from selenium_wrapper.defaults import Browser
					# You've imported a SPECIFIC `__BrowserDefaults` object here ^
			-
				After interacting with a class which uses the container object, you reassign the original instance back
				to the same name.
		-
			But honestly, **EVEN IF** you need to override the global defaults (which is already a big debate of whether
			you do, instead of using environment variables), you better off doing it just once, at the very start of
			your program. And then, just working with multiple :class:`selenium_wrapper.firefox.BrowserConfig` instances
			(as an example) which all fall back to these same defaults only when they don't have their own values specified.
	"""
	HEADLESS: bool = _field(default=False, converter=bool)
	FIREFOX_PROFILE_DIR: _O[_StrPath] = _field(
		default=None, validator=_validators.instance_of((str, type(None), _os.PathLike))
	)
	FIREFOX_USERAGENT: _O[str] = _field(
		default=None,
		converter=_to_string_none,
		validator=_validators.instance_of((str, type(None))),
	)

	FAKE_USERAGENT_FALLBACK: bool = _field(default=False, converter=bool)
	WINDOW_MAXIMIZED: bool = _field(default=False, converter=bool)
	WINDOW_POS: _IntVector2D = _field(
		default=None,
		converter=_IntVector2D.attrs_converter,
		validator=_validators.instance_of(_IntVector2D),
	)
	WINDOW_SIZE: _IntVector2D = _field(
		default=None,
		converter=_IntVector2D.attrs_converter,
		validator=_window_size_validators,
	)
	WINDOW_SIZE_VALIDATORS: _t.List[_t.Callable] = _field(
		default=_window_size_validators,
		validator=_val_val
	)


@_define
class __EnvDefaults:
	DOTENV_AUTO_LOAD: bool = _field(default=True, converter=bool)
	DOTENV_LOAD_KWARGS: _t.Dict[str, _t.Any] = _field(
		factory=lambda: dict(verbose=True, override=True),
		converter=lambda x: dict(x)
	)
	DOTENV_PRIORITY_OVER_CONFIGS: bool = _field(default=True, converter=bool)


@_define
class __LoginDefaults:
	USER: _O[str] = None
	PASSWORD: _O[str] = None


@_define
class __EnvNames:
	HEADLESS: str = 'SELENIUM_HEADLESS'
	FIREFOX_PROFILE_DIR: str = 'SELENIUM_FIREFOX_PROFILE_DIR'
	FIREFOX_USERAGENT: str = 'SELENIUM_FIREFOX_USERAGENT'

	LOGIN_USER: str = 'SELENIUM_LOGIN_USER'
	LOGIN_PASSWORD: str = 'SELENIUM_LOGIN_PASSWORD'

	FAKE_USERAGENT_FALLBACK: str = 'SELENIUM_FAKE_USERAGENT_FALLBACK'
	WINDOW_MAXIMIZED: str = 'SELENIUM_WINDOW_MAXIMIZED'
	WINDOW_POS: str = 'SELENIUM_WINDOW_POS'
	WINDOW_SIZE: str = 'SELENIUM_WINDOW_SIZE'

# @_define(slots=False)
# class Browser(_StaticClass, metaclass=__Defaults):
# 	pass

Browser = __BrowserDefaults()
# Browser.__doc__ = """
# """
Env = __EnvDefaults()
Login = __LoginDefaults()

EnvNames = __EnvNames()


def get_setting(
	env_var: str, config_value: _O[_T], *fallback_values: _O[_T],
	converter: _t.Callable[[...], _T] = str, _type: _t.Union[_t.Type[_T], _t.Tuple[_t.Type[_T], ...]] = str
) -> _O[_T]:
	"""
	A utility function which gets a value with fallbacks from ENV > config > ... > defaults.

	The first two might be switched depending on :attr:`selenium_wrapper.defaults.Env.DOTENV_PRIORITY_OVER_CONFIGS`.
	"""
	if Env.DOTENV_PRIORITY_OVER_CONFIGS:
		val = _os.getenv(env_var, config_value)
	else:
		val = config_value if (config_value is not None) else _os.getenv(env_var, None)
	if val is not None:
		return val if isinstance(val, _type) else converter(val)

	for fallback in fallback_values:
		if fallback is not None:
			return fallback if isinstance(fallback, _type) else converter(fallback)
	return None


if __name__ == '__main__':
	print(Browser)
	print(Browser.WINDOW_SIZE)
	Browser.WINDOW_SIZE = (10, 10)
	Browser.WINDOW_SIZE = (None, None)
	Browser.WINDOW_SIZE = 7
	Browser.WINDOW_SIZE = None
	Browser.WINDOW_SIZE = (3, None)
	Browser.WINDOW_SIZE = (None, 2)
	Browser.FIREFOX_USERAGENT = None
	Browser.FIREFOX_USERAGENT = tuple()
	Browser.FIREFOX_USERAGENT = 7
	Browser.FIREFOX_PROFILE_DIR = 3
	pass
