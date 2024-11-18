# encoding: utf-8
"""
Common utilities being useful regardless of a chosen webdriver.
"""
from inspect import signature as _signature, Signature as _Signature, Parameter as _Parameter
from functools import wraps as _wraps
import os as _os
import re as _re

from attrs import define as _define, field as _field, validators as _validators, exceptions as _attrs_exceptions
from dotenv import load_dotenv

import typing as _t
from typing import Optional as _O

try:
	from typing import final as _final
except ImportError:
	def _final(f):
		"""A dummy fallback version of ``@final`` decorator from pre-python 3.8 :mod:`typing` module."""
		return f


T = _t.TypeVar('T')
StrPath = _t.Union[_t.AnyStr, _os.PathLike]


class StaticClass:
	"""
	A simple base class which explicitly forbids instantiation of it.
	Should be inherited along with usage of a metaclass which actually defines the static subclass.
	"""
	@_final
	def __init__(self, *args, **kwargs):
		raise TypeError(f"<{self.__class__.__name__}> is a static (non-instantiable) class")


_re_vector2_precise_match_spaces = _re.compile(  # '123'
	'^[0-9]+$',
	flags=_re.IGNORECASE
).match
_re_vector2_precise_match_separator = _re.compile(  # '123x456' '123x' 'x456' 'x', any single char instead of <x>
	'^([0-9]+)?[^0-9]([0-9]+)?$',
	flags=_re.IGNORECASE
).match
_re_vector2_env_search = _re.compile(  # "~~bEcAuSe <123> I'm VeRy [456] sTuPiD!!!111 - and can't even follow formats"
	'([0-9]+)'
	'(?:[^0-9]+([0-9]+))?',
	flags=_re.IGNORECASE
).search


class Vector2DOptionalInt(_t.NamedTuple):
	"""
	A simple 2D-vector-namedtuple, allowing ``int`` or ``None`` as values.

	Also provides :meth:`attrs_converter` method and :class:`Vector2DOptionalInt.ValidatorGE` sub-class.
	"""
	x: _O[int] = None
	y: _O[int] = None

	@staticmethod
	def attrs_converter(value: T) -> _t.Union['Vector2DOptionalInt', T]:
		"""
		An :mod:`attrs` converter, which tries to convert any given value to a :class:`Vector2DOptionalInt` instance.
		If it fails, no error is thrown, but the value is returned as is.
		So probably this converter should be used in combination with type validator.
		"""
		if isinstance(value, Vector2DOptionalInt):
			return value
		if value is None or isinstance(value, int):
			value = (value, value)
		# noinspection PyBroadException
		try:
			value_iter = iter(value)
			x = next(value_iter)
			y = next(value_iter)
			return Vector2DOptionalInt(
				x if x is None else int(x),
				y if y is None else int(y)
			)
		except Exception:
			return value

	@staticmethod
	def __parse_from_string(value: str) -> _O[_t.Tuple[_O[int], _O[int]]]:
		if not value:
			return None
		# First, let's check if the string is perfectly formatted with SINGLE space. Aka '123 456' or '123 ' or ' 456' or '7':
		split = value.split(' ')
		if len(split) in [1, 2] and all(
			(not a or _re_vector2_precise_match_spaces(a))
			for a in split
		):
			# Yep, we have a string perfectly-formatted with a space.
			ints = tuple((int(x) if x else None) for x in split)
			if len(ints) == 1:
				comp = ints[0]
				return None if comp is None else (comp, comp)
			# noinspection PyTypeChecker
			return ints

		# The precise-space match failed. Let's try 'x' format. I.e., '123x456' or '123x' or 'x456' or 'x', where
		# 'x' can be replaced with any non-numeric character.
		match = _re_vector2_precise_match_separator(value.strip().lower())
		if match:
			ints = tuple((int(x) if x else None) for x in match.groups())
			if len(ints) == 2:
				# noinspection PyTypeChecker
				return ints

		# Both precise formats failed. Let's do our best detecting the value...
		match = _re_vector2_env_search(value)
		if not match:
			return None
		ints = tuple(int(x) for x in match.groups() if x is not None)
		if not ints:
			return None
		if len(ints) == 1:
			comp = ints[0]
			return comp, comp
		# noinspection PyTypeChecker
		return ints

	@staticmethod
	def env_to_vector_or_none(value) -> _O['Vector2DOptionalInt']:
		"""A utility method turing an environment-variable string into the tuple instance."""
		if value is None:
			return None
		if isinstance(value, str):
			ints = Vector2DOptionalInt.__parse_from_string(value)
			if ints is None:
				return None
			x, y = ints
			if x is None and y is None:
				return None
			return Vector2DOptionalInt(x, y)

		res = Vector2DOptionalInt.attrs_converter(value)
		if not(res is None or isinstance(res, Vector2DOptionalInt)):
			raise TypeError(
				f"Environment variable (string) is expected (or None/Vector2DOptionalInt/iterable of ints). Got: {value!r}"
			)
		return res

	@staticmethod
	def env_to_vector(value) -> 'Vector2DOptionalInt':
		res = Vector2DOptionalInt.env_to_vector_or_none(value)
		return Vector2DOptionalInt() if res is None else res

	@_define(repr=False, frozen=True, slots=True)
	class ValidatorGE:
		"""
		An :mod:`attrs` validator which checks that either or both of the :class:`Vector2DOptionalInt` components
		are greater or equal to a certain threshold OR are ``None``.
		"""
		x: _O[int] = _field(default=None, converter=lambda a: a if (a is None or isinstance(a, int)) else int(a))
		y: _O[int] = _field(default=None, converter=lambda a: a if (a is None or isinstance(a, int)) else int(a))
		allow_none: bool = True

		_validator: _t.Callable[[_t.Any, _t.Any, _t.Any], None] = _field(
			default=None, repr=False, init=False
		)

		def __attrs_post_init__(self):
			object.__setattr__(self, "_validator", self.__build_validator_method())

		@staticmethod
		def __verify_component_type_none_passes(comp_val) -> _O[int]:
			if not(comp_val is None or isinstance(comp_val, int)):
				raise TypeError()
			return comp_val

		@staticmethod
		def __verify_component_type_none_fails(comp_val) -> int:
			if not isinstance(comp_val, int):
				raise TypeError()
			return comp_val

		def __get_proper_sized_tuple(
			self, inst, attr, value, verify_component_type_f: _t.Callable[[_t.Any], _O[int]]
		) -> _t.Tuple[_O[int], _O[int]]:
			# noinspection PyBroadException
			try:
				val_iter = iter(value)
				v_x = verify_component_type_f(next(val_iter))
				v_y = verify_component_type_f(next(val_iter))
				try:
					next(val_iter)
					raise ValueError()
				except StopIteration:
					pass
			except Exception:
				raise TypeError(
					f"{attr.name!r} must be an iterable of 2 ints{'/None' if self.allow_none else ' (not None)'}, "
					f"preferably Vector2DOptionalInt. Got: {value!r} (type: {type(value)!r})"
				)
			return v_x, v_y

		def __expected_value_message(self):
			x = self.x
			y = self.y
			allow_none = self.allow_none
			if x is None and y is None:
				assert not allow_none
				return "neither X nor Y being None"
			if x is not None and y is not None:
				msg = f"(X >= {x}, Y >= {y})"
				return f"{msg} or either being None" if allow_none else f"{msg} and neither being None"
			or_none = ' or being None' if allow_none else ''
			if y is None:
				return f"X >= {x}{or_none}"
			return f"Y >= {y}{or_none}"

		def __comp_validator_none_passes(self, inst, attr, value, comp_val, comp_min: int):
			if comp_val is not None and comp_val < comp_min:
				expected_value = self.__expected_value_message()
				raise ValueError(
					f"'{attr.name}' must be a Vector2DOptionalInt with {expected_value}. Got: {value!r}"
				)

		def __comp_validator_none_fails(self, inst, attr, value, comp_val, comp_min: int):
			if comp_val < comp_min:
				expected_value = self.__expected_value_message()
				raise ValueError(
					f"'{attr.name}' must be a Vector2DOptionalInt with {expected_value}. Got: {value!r}"
				)

		def __build_validator_method(self) -> _t.Callable[[_t.Any, _t.Any, _t.Any], None]:
			"""
			The main validator-building factory method. It does in sequence:
				*
					Chooses between :meth:`__verify_component_type_none_passes`
					and :meth:`__verify_component_type_none_fails`
					for initial per-component type check.
				*
					Chooses between :meth:`__comp_validator_none_passes`
					and :meth:`__comp_validator_none_fails`
					for per-component value check (assuming type check is already passed).
				*
					Depending on the instance parameters, generates a proper validator function to be attached as an instance method.
					This method:
						* uses :meth:`__get_proper_sized_tuple` passing the chosen ``__verify_component*`` method as an argument,
						* directly calls the chosen ``__comp_validator*`` method as a function.
			"""
			x = self.x
			y = self.y
			allow_none = self.allow_none
			if x is None and y is None and allow_none:
				raise ValueError(
					f"Validator {Vector2DOptionalInt.ValidatorGE!r} needs at least one of the components to have a minimum "
					f"value specified, or None being forbidden. Got: (x={x!r}, y={y!r}, allow_none={allow_none!r})"
				)

			_verify_component_type = self.__verify_component_type_none_passes if allow_none else self.__verify_component_type_none_fails
			_comp_validator = self.__comp_validator_none_passes if allow_none else self.__comp_validator_none_fails
			_get_proper_sized_tuple = self.__get_proper_sized_tuple

			def validator_not_none(inst, attr, value):
				_get_proper_sized_tuple(inst, attr, value, _verify_component_type)

			def validator_x_only(inst, attr, value):
				val_tuple = _get_proper_sized_tuple(inst, attr, value, _verify_component_type)
				# noinspection PyArgumentList
				_comp_validator(inst, attr, value, val_tuple[0], x)

			def validator_y_only(inst, attr, value):
				val_tuple = _get_proper_sized_tuple(inst, attr, value, _verify_component_type)
				# noinspection PyArgumentList
				_comp_validator(inst, attr, value, val_tuple[1], y)

			def validator_xy(inst, attr, value):
				v_x, v_y = _get_proper_sized_tuple(inst, attr, value, _verify_component_type)
				# noinspection PyArgumentList
				_comp_validator(inst, attr, value, v_x, x)
				# noinspection PyArgumentList
				_comp_validator(inst, attr, value, v_y, y)

			if self.x is None and self.y is None:
				return validator_not_none
			if self.y is None:
				# X-only case
				return validator_x_only
			if self.x is None:
				# Y-only case
				return validator_y_only
			return validator_xy

		def __call__(self, inst, attr, value):
			self._validator(inst, attr, value)
		
		def __repr__(self):
			return (
				f"<Validator for Vector2DOptionalInt to be at least ({self.x}, {self.y}) "
				f"{'or None' if self.allow_none else 'and not None'}>"
			)


_bool_env_false_values = {'', '0', 'no', 'off', 'false', }
_bool_env_none_values = {'', 'none', }


def bool_env(value) -> bool:
	"""A utility class converting a environment variable string with True/False/empty value to an actual boolean."""
	if isinstance(value, bool):
		return value
	if isinstance(value, str):
		return not (value.strip().lower() in _bool_env_false_values)
	return bool(value)


def bool_or_none_env(value) -> _O[bool]:
	return (
		None
		if (value is None or (isinstance(value, str) and value.strip().lower() in _bool_env_none_values))
		else bool_env(value)
	)


def convert_to_string_or_none(value, strip=True, empty_string_to_none=True) -> _O[str]:
	"""A simple :mod:`attrs` converter, ensuring the passed value is turned to a string or ``None``."""
	if value is None:
		return None
	res = str(value)
	if strip:
		res = res.strip()
	if empty_string_to_none and not res:
		return None
	return res


def using_dotenv(_func=None, /, *_, verbose=True, override=True, **load_dotenv_kwargs):
	"""A simple function decorator auto-calling `load_dotenv()`"""
	def decorator(f: _t.Callable):
		@_wraps(f)
		def wrapper(*args, **kwargs):
			load_dotenv(verbose=verbose, override=override, **load_dotenv_kwargs)
			return f(*args, **kwargs)
		return wrapper

	if _func is None:
		return decorator
	return decorator(_func)


@_define(repr=False, frozen=True, slots=True)
class __ValidatorValidator:
	"""
	An :mod:`attrs` validator which checks that the provided value is suitable to be used as ``validator`` argument
	for some other :mod:`attrs` field.

	Useful if you intend to store validators themselves in a field dedicated to them.
	"""

	@staticmethod
	def __is_single_validator_object(x):
		if not callable(x):
			return False

		try:
			sig: _Signature = _signature(x, follow_wrapped=False)
		except (ValueError, TypeError):
			# We can't detect the signature, but it's a callable. So let's assume it has a proper signature
			# and hope for the best (or encounter an error later during actual validation with this validator).
			return True
		try:
			params = iter(sig.parameters.values())
		except (TypeError, AttributeError, NameError):
			# An odd case: we've detected the sig, but cannot get params? Let's assume the best again:
			return True

		# OK, let's go checking the callable's signature...
		valid_kinds = {_Parameter.POSITIONAL_ONLY, _Parameter.POSITIONAL_OR_KEYWORD}
		passed_args_n = 3
		n = 0
		for param in params:
			try:
				kind = param.kind
				param_detected = True
			except (TypeError, AttributeError, NameError):
				kind = None
				param_detected = False
			if param_detected and kind == _Parameter.VAR_POSITIONAL:
				return True
			if (param_detected and kind not in valid_kinds) or n > passed_args_n:
				break
			n += 1
		return n == passed_args_n

	def __call__(self, inst, attr, raw_value, **aaa):
		value = raw_value
		if callable(value):
			value = (value,)
		if not isinstance(value, (tuple, list)):
			raise _attrs_exceptions.NotCallableError(
				msg=f"{attr.name!r} must be a validator or a list/tuple of them. Got: {raw_value!r} (type: {type(raw_value)!r})",
				value=raw_value
			)
		is_ok_f = self.__is_single_validator_object
		for x in value:
			if not is_ok_f(x):
				single_item = x is raw_value
				this = 'this' if single_item else 'this as an item'
				in_iterable = '' if single_item else f" in: {raw_value!r}"
				raise _attrs_exceptions.NotCallableError(
					msg=f"{attr.name!r} must be a list/tuple of validators. Got {this}: {x!r} (type: {type(x)!r}){in_iterable}",
					value=raw_value
				)

	def __repr__(self):
		return f"<Validator-validator (checks that the given value is a proper validator)>"

_ValidatorValidator_instance = __ValidatorValidator()


def validator_validator(inst, attr, raw_value):
	"""
	An :mod:`attrs` validator which checks that the provided value is suitable to be used as ``validator`` argument
	for some other field.

	Useful if you intend to store validators themselves in a field dedicated to them.
	"""
	return _ValidatorValidator_instance(inst, attr, raw_value)


is_callable_validator = _validators.is_callable()


def is_callable_or_none_validator(inst, attr, value):
	if value is None:
		return
	is_callable_validator(inst, attr, value)


if __name__ == '__main__':
	# Some debug/testing garbage

	# @using_dotenv
	# def test():
	# 	import os
	# 	print(os.getenv('FIREFOX_PROFILE', 'aaa'))
	#
	# test()

	# @_define
	# class TestClass:
	# 	window_size: Vector2DOptionalInt = _field(
	# 		factory=lambda: (4, 4),
	# 		validator=[
	# 			_validators.instance_of(Vector2DOptionalInt),
	# 			Vector2DOptionalInt.ValidatorGE(None, None, False)
	# 		],
	# 		converter=Vector2DOptionalInt.attrs_converter,
	# 	)
	#
	# test = TestClass()
	# print(test.window_size)
	# test.window_size = (-10, 0)
	# test.window_size = (None, 1)
	# print(test.window_size)

	# @_define
	# class QQQ:
	# 	bbb: int
	# 	ccc: _O[str] = None
	#
	# for p in _signature(_ValidatorValidator_instance, follow_wrapped=False).parameters.values():
	# 	print(f"{p.name} -> {p.kind}")
	#
	# for p in _signature(QQQ.__init__, follow_wrapped=True).parameters.values():
	# 	print(f"{p.name} -> {p.kind}")

	from attrs import Attribute
	validator_validator(
		None,
		Attribute(name='qqq', default='', validator=None, repr=False, cmp=False, hash=False, init=False, inherited=False),
		[str, list]
	)

	pass
