# encoding: utf-8
"""
Firefox-dependent wrapper.
"""

import errno as _errno
import os as _os
from pathlib import Path
from shutil import rmtree as _rmtree
from traceback import print_exception as _print_exception

from attrs import define, field, validators
from fake_useragent import UserAgent
from selenium.webdriver import (
	Firefox,
	FirefoxOptions,
	FirefoxProfile,
	FirefoxService,
)
from webdriver_manager.firefox import GeckoDriverManager

from .common import *
from . import defaults as _d
from .defaults import get_setting

import typing as _t
from typing import Optional as _O


class FirefoxProfileTMP(FirefoxProfile):
	"""
	A subclass of a regular Selenium's :class:`FirefoxProfile`, which also auto-removes it's cloned profile dir
	whenever the class instance is deleted/garbage-collected.
	"""

	def __init__(self, profile_directory:StrPath = None, del_empty_subdirs_depth: int = 2):
		"""
		:param del_empty_subdirs_depth:
			Selenium's :class:`FirefoxProfile` tend to clone a specified source profile
			into ``$TMP/tmp{random-char-sequence}/webdriver-py-profilecopy`` folder.
			Thus, to fully clean up, we need to delete not just the innermost profile folder itself, but also it's container.
			This parameter specifies how far to iteratively go up in attempts to delete empty leftover folders.
			All the subsequent parents (except for the innermost folder) are only deleted if they're empty.
			A value of 1 removes only the endpoint profile folder itself and 0 disables the cleanup process completely.
		"""
		super().__init__(profile_directory=profile_directory)
		self.__del_empty_subdirs_depth = 0
		self.del_empty_subdirs_depth = del_empty_subdirs_depth

	@property
	def del_empty_subdirs_depth(self):
		return self.__del_empty_subdirs_depth

	@del_empty_subdirs_depth.setter
	def del_empty_subdirs_depth(self, value):
		if not isinstance(value, int):
			raise TypeError(f"del_empty_subdirs_depth must be an int. Got {type(value)!r}: {value!r}")
		if value < 0:
			raise ValueError(f"del_empty_subdirs_depth must be 0+. Got: {value}")
		self.__del_empty_subdirs_depth = value

	def __del_unsafe(self):
		"""
		The actual cleanup function, which removes a temporary clone of the profile.
		It's extracted into a separate one so that the actual ``__del__`` could catch any exceptions.
		"""
		if not self.path:
			return
		tmp_profile_path = Path(self.path).absolute()

		innermost_dir = True
		for i in range(self.del_empty_subdirs_depth):
			if not tmp_profile_path or tmp_profile_path == tmp_profile_path.parent:
				return

			if not tmp_profile_path.is_dir():
				raise OSError(_errno.ENOTDIR, _os.strerror(_errno.ENOTDIR), str(tmp_profile_path))

			try:
				if innermost_dir:
					print(f"Auto-removing TMP profile folder (with contents): {str(tmp_profile_path)}")
					for child in tmp_profile_path.iterdir():
						if child.is_dir() and not child.is_symlink():
							_rmtree(child)
						else:
							child.unlink(missing_ok=True)
				else:
					if list(tmp_profile_path.iterdir()):
						raise OSError(
							_errno.ENOTEMPTY, "Kept a leftover folder. {}".format(_os.strerror(_errno.ENOTEMPTY)), str(tmp_profile_path)
						)
					print(f"Removing empty leftover folder: {str(tmp_profile_path)}")

				if tmp_profile_path.is_symlink():
					tmp_profile_path.unlink(missing_ok=True)
				else:
					_rmtree(tmp_profile_path)
			except (IOError, OSError) as e:
				_print_exception(type(e), e, None)
				return
			innermost_dir = False
			tmp_profile_path = tmp_profile_path.parent

	def __del__(self):
		try:
			self.__del_unsafe()
		except Exception as e:
			_print_exception(type(e), e, None)


@define(frozen=True)
class FirefoxBrowserConfig:
	"""
	An overall config for new browser sessions.
	During initialisation, `.env` is automatically (re-)loaded, unless
	:attr:`selenium_wrapper.defaults.Env.DOTENV_AUTO_LOAD` is ``False``.
	
	Each of the attributes has its own ``get_*()`` method, which also checks system environment variables on each call.
	The order of precedence is determined by :attr:`selenium_wrapper.defaults.Env.DOTENV_PRIORITY_OVER_CONFIGS`:
		- ``True``: env values override the config's attributes.
		- ``False``: config attributes override env ones, if specified (not ``None``).

	Raw attributes preserve their values as they were initialised.
	"""
	dotenv_load_kwargs: _t.Dict[str, _t.Any] = field(
		factory=lambda: dict(_d.Env.DOTENV_LOAD_KWARGS), converter=lambda x: dict(x)
	)

	headless: bool = field(factory=lambda: _d.Browser.HEADLESS, converter=bool)
	profile_dir: _O[StrPath] = field(
		factory=lambda: _d.Browser.FIREFOX_PROFILE_DIR,
		validator=validators.instance_of((str, type(None), _os.PathLike))
	)
	useragent: _O[str] = field(
		factory=lambda: _d.Browser.FIREFOX_USERAGENT,
		converter=convert_to_string_or_none,
		validator=validators.instance_of((str, type(None))),
	)

	fake_useragent_fallback: bool = field(factory=lambda: _d.Browser.FAKE_USERAGENT_FALLBACK, converter=bool)
	window_maximized: bool = field(factory=lambda: _d.Browser.WINDOW_MAXIMIZED, converter=bool)
	window_pos: Vector2DOptionalInt = field(
		factory=lambda: _d.Browser.WINDOW_POS,
		converter=Vector2DOptionalInt.attrs_converter,
		validator=validators.instance_of(Vector2DOptionalInt),
	)
	window_size: Vector2DOptionalInt = field(
		factory=lambda: _d.Browser.WINDOW_SIZE,
		converter=Vector2DOptionalInt.attrs_converter,
		validator=_d.Browser.WINDOW_SIZE_VALIDATORS,
	)

	def __attrs_post_init__(self):
		if _d.Env.DOTENV_AUTO_LOAD:
			dotenv_load_kwargs = dict(_d.Env.DOTENV_LOAD_KWARGS)
			dotenv_load_kwargs.update(self.dotenv_load_kwargs)
			args_string = ', '.join(f"{k}={val!r}" for k, val in sorted(dotenv_load_kwargs.items()))
			print(f"Calling load_dotenv({args_string}) during init of: {self!r}")
			load_dotenv(**dotenv_load_kwargs)
		print(f"Initialized: {self!r}")

	def get_headless(self) -> bool:
		return get_setting(
			_d.EnvNames.HEADLESS, self.headless, _d.Browser.HEADLESS,
			converter=bool_or_none_env, _type=bool
		)

	def get_profile_dir(self) -> str:
		return get_setting(_d.EnvNames.FIREFOX_PROFILE_DIR, self.profile_dir, _d.Browser.FIREFOX_PROFILE_DIR)

	def get_fake_useragent_fallback(self) -> bool:
		return get_setting(
			_d.EnvNames.FAKE_USERAGENT_FALLBACK, self.fake_useragent_fallback, _d.Browser.FAKE_USERAGENT_FALLBACK,
			converter=bool_or_none_env, _type=bool
		)

	def get_useragent(self) -> str:
		"""
		This value-getter is special: if after all fallbacks the value is still ``None``
		**AND** :attr:`selenium_wrapper.defaults.Browser.DO_FAKE_USERAGENT` is ``True``,
		:class:`UserAgent` is used to generate a fake one.
		"""
		value = get_setting(_d.EnvNames.FIREFOX_USERAGENT, self.useragent, _d.Browser.FIREFOX_USERAGENT)
		if value is None and self.get_fake_useragent_fallback():
			return UserAgent().firefox
		return value


	def get_window_maximized(self) -> bool:
		return get_setting(
			_d.EnvNames.WINDOW_MAXIMIZED, self.window_maximized, _d.Browser.WINDOW_MAXIMIZED,
			converter=bool_or_none_env, _type=bool
		)

	def get_window_pos(self) -> Vector2DOptionalInt:
		res = get_setting(
			_d.EnvNames.WINDOW_POS, self.window_pos, _d.Browser.WINDOW_POS,
			converter=Vector2DOptionalInt.env_to_vector_or_none, _type=Vector2DOptionalInt
		)
		return Vector2DOptionalInt() if res is None else res

	def get_window_size(self) -> Vector2DOptionalInt:
		res = get_setting(
			_d.EnvNames.WINDOW_SIZE, self.window_size, _d.Browser.WINDOW_SIZE,
			converter=Vector2DOptionalInt.env_to_vector_or_none, _type=Vector2DOptionalInt
		)
		return Vector2DOptionalInt() if res is None else res


@define
class BrowserManager:
	"""
	A higher-level class on top of :class:`Firefox` and :class:`FirefoxProfile`,
	responsible for managing the browser session and providing easier methods to interact with it.

	The read-only properties instantiate the required internal objects (:class:`FirefoxOptions`, :class:`Firefox`, etc.)
	according to the settings specified in :attr:`config` (:class:`FirefoxBrowserConfig`), env vars and the global
	fallback values in :mod:`selenium_wrapper.defaults` submodule.

	:attr:`profile_factory` is a factory taking a single ``str`` argument and creating a new :class:`FirefoxProfile`
	instance. The use of :class:`FirefoxProfileTMP` is highly recommended for auto-cleanup of the leftover profile copy
	when the browser is closed.

	All the ``*_override`` attributes are expected to have a callable which takes a single (pre-made) instance of the
	corresponding type and returns it - whether the same instance or a new one.
	Though, whenever possible, overriding the default values with :attr:`config` is recommended instead.
	"""

	config: FirefoxBrowserConfig = field(
		factory=FirefoxBrowserConfig, validator=validators.instance_of(FirefoxBrowserConfig)
	)
	profile_factory: _t.Callable[[StrPath], FirefoxProfile] = field(
		default=FirefoxProfileTMP, validator=is_callable_validator
	)

	options_override: _O[_t.Callable[[FirefoxOptions], FirefoxOptions]] = field(
		default=None, validator=is_callable_or_none_validator
	)
	driver_manager_override: _O[_t.Callable[[GeckoDriverManager], GeckoDriverManager]] = field(
		default=None, validator=is_callable_or_none_validator
	)
	service_override: _O[_t.Callable[[FirefoxService], FirefoxService]] = field(
		default=None, validator=is_callable_or_none_validator
	)
	browser_override: _O[_t.Callable[[Firefox], Firefox]] = field(
		default=None, validator=is_callable_or_none_validator
	)

	__profile: _O[FirefoxProfile] = field(default=None, repr=False, init=False)
	__options: _O[FirefoxOptions] = field(default=None, repr=False, init=False)
	__driver_manager: _O[GeckoDriverManager] = field(default=None, repr=False, init=False)
	__service: _O[FirefoxService] = field(default=None, repr=False, init=False)
	__browser: _O[Firefox] = field(default=None, repr=False, init=False)

	def __do_override_f(
		self, value: T, override_f: _O[_t.Callable[[T], T]], override_attr_name: str, expected_type: _t.Type[T],
		take_and=' take and'
	) -> T:
		if override_f is None:
			return value
		try:
			value = override_f(value)
		except Exception as e:
			raise ValueError(
				f"Invalid <{override_attr_name}> on {self!r}: {override_f!r}\n"
				f"When calling it for {value!r}, an error occurred."
			) from e
		if not isinstance(value, expected_type):
			raise ValueError(
				f"Invalid <{override_attr_name}> on {self!r}: {override_f!r}\n"
				f"It must{take_and} return an instance of {expected_type!r}. Got: {value!r}"
			)
		return value

	@property
	def profile(self) -> FirefoxProfile:
		"""
		Always-ready-to-go :class:`FirefoxProfile` instance for :class:`FirefoxOptions`
		(used for :attr:`_options` > :attr:`browser`).
		"""
		profile = self.__profile
		if profile is None or not profile:
			config = self.config
			profile_dir = config.get_profile_dir()
			# noinspection PyTypeChecker
			profile: FirefoxProfile = self.__do_override_f(
				profile_dir,
				FirefoxProfileTMP if (self.profile_factory is None) else self.profile_factory,
				'profile_factory', FirefoxProfile, take_and=' take a profile path string and'
			)
			self.__profile = profile
		return profile

	@property
	def _options(self) -> FirefoxOptions:
		"""Always-ready-to-go :class:`FirefoxOptions` instance for :class:`Firefox` (used for :attr:`browser`)."""
		options = self.__options
		if options is None or not options:
			config = self.config
			options = FirefoxOptions()
			options.profile = self.profile

			if config.headless:
				options.add_argument('--headless')

			useragent = config.get_useragent()
			if useragent:
				options.set_preference("general.useragent.override", useragent)

			options = self.__do_override_f(
				options, self.options_override, 'options_override', FirefoxOptions
			)
			self.__options = options
		return options

	@property
	def _driver_manager(self) -> GeckoDriverManager:
		"""
		Always-ready-to-go :class:`GeckoDriverManager` instance for :class:`FirefoxService`
		(used for :attr:`_service` > :attr:`browser`).
		"""
		value = self.__driver_manager
		if value is None or not value:
			value = GeckoDriverManager()
			value = self.__do_override_f(
				value, self.driver_manager_override, 'driver_manager_override', GeckoDriverManager
			)
			self.__driver_manager = value
		return value

	@property
	def _service(self) -> FirefoxService:
		"""Always-ready-to-go :class:`FirefoxService` instance for :class:`Firefox` (used for :attr:`browser`)."""
		value = self.__service
		if value is None or not value:
			value = FirefoxService(executable_path=self._driver_manager.install())
			value = self.__do_override_f(
				value, self.service_override, 'service_override', FirefoxService
			)
			self.__service = value
		return value

	@property
	def browser(self) -> Firefox:
		"""An always-valid instance of running :class:`Firefox` session."""
		browser = self.__browser
		if browser is None or not browser:
			config = self.config

			browser: Firefox = Firefox(options=self._options, service=self._service)

			x, y = config.window_size
			if not (x is None and y is None):
				def_x, def_y = _d.Browser.WINDOW_SIZE
				cur_xy = browser.get_window_size()
				if x is None:
					x = cur_xy.get('width', def_x)
				if y is None:
					y = cur_xy.get('height', def_y)
				browser.set_window_size(x, y)

			x, y = config.window_pos
			if not (x is None and y is None):
				def_x, def_y = _d.Browser.WINDOW_POS
				cur_xy = browser.get_window_position()
				if x is None:
					x = cur_xy.get('x', def_x)
				if y is None:
					y = cur_xy.get('y', def_y)
				browser.set_window_position(x, y)

			if config.window_maximized:
				browser.maximize_window()

			browser = self.__do_override_f(
				browser, self.browser_override, 'browser_override', Firefox
			)
			self.__browser = browser
		return browser

	@property
	def driver(self):
		"""Just an alias for :attr:`browser` property - to be consistent with Selenium's terminology."""
		return self.browser

	def browser_close(self, reset_profile=False, reset_all=False):
		"""
		Properly close the browser session (and return self). Use this instead of ``.quit()`` or ``.close()`` on the
		:attr:`browser` instance itself.

		It's highly recommended for the :attr:`profile_factory` to return an instance of :class:`FirefoxProfileTMP`
		so it would auto-clean-up after itself.
		"""
		closing_method = None
		# noinspection PyBroadException
		try:
			closing_method = self.__browser.quit
		except Exception:
			pass

		if callable(closing_method):
			try:
				closing_method()
			except Exception as e:
				_print_exception(type(e), e, None)
		self.__browser = None
		if reset_profile or reset_all:
			self.__profile = None
		if reset_all:
			self.__options = None
			self.__driver_manager = None
			self.__service = None

		return self


if __name__ == '__main__':
	# config: FirefoxBrowserConfig = FirefoxBrowserConfig()
	#
	# @using_dotenv
	# def load_profile():
	# 	profile_dir = _os.getenv('FIREFOX_PROFILE', config.profile_dir_fallback)
	# 	return FirefoxProfileTMP(profile_dir)
	#
	# profile = load_profile()
	# print(profile.path)
	# print('TADA!')
	# config.remove_profile_dir(profile)


	b = BrowserManager()
	print(b)
	print(b.browser)
	print(b.profile)
	print(b.profile.path)
	print(b.browser.service)
	# type(b._BrowserManager__browser)
	# type(b._BrowserManager__profile)
	browser = b.browser

	# print(bool(browser))
	# print(browser.quit())
	#
	# print(bool(browser))
	# try:
	# 	print(browser.close())
	# except Exception:
	# 	pass

	b.browser_close(reset_all=True)

	import gc
	gc.collect()
	print('TADA #2!')

	_os.strerror(_errno.ENOTDIR)
