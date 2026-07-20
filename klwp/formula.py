"""Safe, deliberately small preview evaluator for KLWP Kode formulas."""

import math
import re


DEFAULT_DATE_FORMAT_VALUES = {
    "hh": "02", "h": "2", "H": "2", "k": "2",
    "mm": "25", "m": "25", "ss": "41",
    "dd": "20", "d": "20", "e": "1", "M": "7", "MM": "07",
    "MMM": "Jul", "MMMM": "July", "yyyy": "2026", "yy": "26",
    "y": "2026", "a": "AM", "EEE": "Mon", "EEEE": "Monday", "f": "1",
}

# Compatibility name used by the preview model while old presets are migrated.
_DF = DEFAULT_DATE_FORMAT_VALUES


def _truthy(value):
    if not isinstance(value, str):
        return bool(value)
    normalized = value.strip()
    normalized = normalized.lower()
    return normalized not in ("", "0", "false", "none", "null")


def _as_number(value, default=0.0):
    if isinstance(value, bool):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _formula_text(value):
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


FORMULA_TOKEN_PATTERN = re.compile(
    r'''\s*(?:(?P<string>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|'''
    r'''(?P<color>\#[0-9A-Fa-f]{6,8})|'''
    r'''(?P<number>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)|'''
    r'''(?P<operator>!=|<=|>=|[=<>+\-*/|&(),])|'''
    r'''(?P<identifier>[^\s=<>+\-*/|&(),]+))'''
)


class FormulaTokenizer:
    """Turn formula source into an immutable sequence of typed tokens."""

    def tokens(self, source):
        tokens = []
        position = 0
        while position < len(source):
            position = self._consume(source, position, tokens)
        return tuple(tokens)

    def _consume(self, source, position, tokens):
        match = FORMULA_TOKEN_PATTERN.match(source, position)
        if match is None:
            return position + 1
        kind = match.lastgroup
        raw_value = match.group(kind)
        value = self._converted(kind, raw_value)
        tokens.append((kind, value))
        return match.end()

    @staticmethod
    def _converted(kind, value):
        conversions = {
            "string": FormulaTokenizer._string,
            "number": float,
        }
        conversion = conversions.get(kind)
        if conversion is None:
            return value
        return conversion(value)

    @staticmethod
    def _string(value):
        content = value[1:-1]
        if "\\" not in content:
            return content
        encoded = bytes(content, "utf-8")
        return encoded.decode("unicode_escape")


class FormulaTokenStream:
    """First-class token collection with its own cursor."""

    def __init__(self, source):
        tokenizer = FormulaTokenizer()
        self._tokens = tokenizer.tokens(source)
        self._position = 0

    def available(self):
        return self._position < len(self._tokens)

    def peek(self, expected=None):
        if not self.available():
            return False
        token = self._tokens[self._position]
        if expected is None:
            return True
        return token[1] == expected

    def current(self):
        if not self.available():
            return (None, None)
        return self._tokens[self._position]

    def take(self):
        token = self.current()
        if not self.available():
            return token
        self._position += 1
        return token

    def advance(self):
        if self.available():
            self._position += 1


class FormulaGlobals:
    """First-class collection for KLWP global variables."""

    def __init__(self, values=None):
        self._values = values or {}

    def optional(self, name, default=None):
        values = self._values
        return values.get(name, default)


class FormulaArguments:
    """First-class ordered arguments passed to one Kode function."""

    def __init__(self):
        self._values = []

    def __len__(self):
        return len(self._values)

    def __getitem__(self, index):
        return self._values[index]

    def append(self, value):
        values = self._values
        values.append(value)

    def optional(self, index, default=""):
        if index >= len(self._values):
            return default
        return self._values[index]

    def key(self, index=0):
        value = self.optional(index)
        return _formula_text(value).lower()


class FormulaContext:
    """The two collaborators required while parsing a formula."""

    def __init__(self, source, global_values=None):
        self._values = {
            "stream": FormulaTokenStream(source),
            "globals": FormulaGlobals(global_values),
        }

    def __getitem__(self, name):
        return self._values[name]


class BinaryOperations:
    """Dispatch binary operators without a conditional cascade."""

    @staticmethod
    def apply(operator, left, right):
        operations = {
            "|": BinaryOperations.logical_or,
            "&": BinaryOperations.logical_and,
            "=": BinaryOperations.equal,
            "!=": BinaryOperations.not_equal,
            "<": BinaryOperations.less_than,
            ">": BinaryOperations.greater_than,
            "<=": BinaryOperations.less_than_or_equal,
            ">=": BinaryOperations.greater_than_or_equal,
            "+": BinaryOperations.add,
            "-": BinaryOperations.subtract,
            "*": BinaryOperations.multiply,
            "/": BinaryOperations.divide,
        }
        operation = operations.get(operator, BinaryOperations.empty)
        return operation(left, right)

    @staticmethod
    def logical_or(left, right):
        return _truthy(left) or _truthy(right)

    @staticmethod
    def logical_and(left, right):
        return _truthy(left) and _truthy(right)

    @staticmethod
    def equal(left, right):
        if isinstance(left, (int, float)) or isinstance(right, (int, float)):
            return _as_number(left) == _as_number(right)
        return str(left).lower() == str(right).lower()

    @staticmethod
    def not_equal(left, right):
        return not BinaryOperations.equal(left, right)

    @staticmethod
    def less_than(left, right):
        return _as_number(left) < _as_number(right)

    @staticmethod
    def greater_than(left, right):
        return _as_number(left) > _as_number(right)

    @staticmethod
    def less_than_or_equal(left, right):
        return _as_number(left) <= _as_number(right)

    @staticmethod
    def greater_than_or_equal(left, right):
        return _as_number(left) >= _as_number(right)

    @staticmethod
    def add(left, right):
        if isinstance(left, str) or isinstance(right, str):
            return _formula_text(left) + _formula_text(right)
        return _as_number(left) + _as_number(right)

    @staticmethod
    def subtract(left, right):
        if isinstance(left, str) or isinstance(right, str):
            return _formula_text(left) + "-" + _formula_text(right)
        return _as_number(left) - _as_number(right)

    @staticmethod
    def multiply(left, right):
        return _as_number(left) * _as_number(right)

    @staticmethod
    def divide(left, right):
        divisor = _as_number(right)
        if not divisor:
            return 0.0
        return _as_number(left) / divisor

    @staticmethod
    def empty(_left, _right):
        return ""


class FormulaFunctions:
    """Small handlers for the Kode functions supported by the preview."""

    def __init__(self, context):
        self._context = context

    def call(self, name, arguments):
        handlers = {
            "if": self._conditional,
            "df": self._date_format,
            "mi": self._media_information,
            "wi": self._weather_information,
            "wf": self._weather_forecast,
            "bi": self._battery_information,
            "li": self._location_information,
            "nc": self._network_connection,
            "rm": self._resource_monitor,
            "gv": self._global_variable,
            "mu": self._mathematics_utility,
            "tf": self._time_format,
            "tc": self._text_converter,
            "ci": self._calendar_information,
            "ai": self._astronomy_information,
            "br": self._browser_information,
        }
        handler = handlers.get(name, self._empty)
        return handler(arguments)

    def _conditional(self, arguments):
        indexes = range(0, len(arguments) - 1, 2)
        match = next((index for index in indexes if _truthy(arguments[index])), None)
        if match is not None:
            return arguments[match + 1]
        if len(arguments) % 2:
            return arguments[-1]
        return ""

    def _date_format(self, arguments):
        context = self._context
        global_values = context["globals"]
        date_values = global_values.optional("__df__", DEFAULT_DATE_FORMAT_VALUES)
        return date_values.get(_formula_text(arguments.optional(0)), "02")

    @staticmethod
    def _media_information(arguments):
        values = {
            "title": "Song Title", "artist": "Artist Name", "state": "PLAYING",
            "percent": 40.0, "cover": "", "pos": 88000.0, "len": 218000.0,
        }
        return values.get(arguments.key(), 0.0)

    @staticmethod
    def _weather_information(arguments):
        values = {
            "temp": 32.0, "flik": 32.0, "tempu": "C",
            "icon": "CLEAR", "cond": "Mostly Cloudy",
        }
        return values.get(arguments.key(), 32.0)

    @staticmethod
    def _weather_forecast(arguments):
        values = {"max": 29.0, "min": 26.0, "cond": "MOSTLY_CLOUDY"}
        return values.get(arguments.key(), 27.0)

    @staticmethod
    def _battery_information(arguments):
        values = {"level": 95.0, "charging": 0.0, "fullempty": "future"}
        return values.get(arguments.key(), 95.0)

    @staticmethod
    def _location_information(arguments):
        values = {"loc": "横浜市", "country": "日本", "postal": "231-0836"}
        return values.get(arguments.key(), "横浜市")

    @staticmethod
    def _network_connection(arguments):
        values = {
            "wifi": "CONNECTED", "ssid": "SSID-328F3B", "wsig": 9.0,
            "csig": 4.0, "dtype": "LTE", "cell": "ON",
        }
        return values.get(arguments.key(), "")

    @staticmethod
    def _resource_monitor(arguments):
        values = {"cused": 42.0, "fstot": 256.0, "fsfree": 59.0}
        return values.get(arguments.key(), 42.0)

    def _global_variable(self, arguments):
        context = self._context
        global_values = context["globals"]
        entry = global_values.optional(_formula_text(arguments.optional(0)))
        value = self._global_entry_value(entry, arguments)
        return self._evaluate_global_value(value)

    def _global_entry_value(self, entry, arguments):
        if isinstance(entry, dict):
            return self._dictionary_global_value(entry, arguments)
        if entry is None:
            return arguments.optional(1)
        return entry

    def _dictionary_global_value(self, entry, arguments):
        formula = entry.get("global_formula")
        if isinstance(formula, str) and formula.strip():
            context = self._context
            global_values = context["globals"]
            return eval_formula(formula, global_values._values)
        return entry.get("value", arguments.optional(1))

    def _evaluate_global_value(self, value):
        if isinstance(value, str) and "$" in value:
            context = self._context
            global_values = context["globals"]
            return eval_formula(value, global_values._values)
        return value

    @staticmethod
    def _mathematics_utility(arguments):
        mode = arguments.key()
        value = _as_number(arguments.optional(1, arguments.optional(0)))
        operations = {"ceil": math.ceil, "floor": math.floor}
        operation = operations.get(mode, round)
        return operation(value)

    @staticmethod
    def _time_format(arguments):
        value = arguments.optional(0)
        if arguments.key(1) == "mm:ss" and isinstance(value, (int, float)):
            seconds = int(value / 1000)
            return f"{seconds // 60:02d}:{seconds % 60:02d}"
        return "2時間後"

    @staticmethod
    def _text_converter(arguments):
        if arguments.key() != "split":
            return ""
        separator = _formula_text(arguments.optional(2, "#"))
        parts = _formula_text(arguments.optional(1)).split(separator)
        index = int(_as_number(arguments.optional(3, 0)))
        if 0 <= index < len(parts):
            return parts[index]
        return ""

    @staticmethod
    def _calendar_information(arguments):
        if arguments.key() == "title":
            return "学校"
        return ""

    @staticmethod
    def _astronomy_information(arguments):
        if arguments.key() == "seasonc":
            return "SPRING"
        return ""

    @staticmethod
    def _browser_information(_arguments):
        return "今日も、ちゃんと顔見せてくれて、ありがと。"

    @staticmethod
    def _empty(_arguments):
        return ""


class FormulaParser:
    """Precedence-climbing parser backed by one context object."""

    PRECEDENCE = {
        "|": 1, "&": 2, "=": 3, "!=": 3, "<": 3,
        ">": 3, "<=": 3, ">=": 3, "+": 4, "-": 4, "*": 5, "/": 5,
    }

    def __init__(self, source, global_values=None):
        self._context = FormulaContext(source, global_values)

    def parse(self):
        return self._expression(0)

    def _expression(self, minimum_precedence):
        left = self._primary()
        while self._has_binary_operator(minimum_precedence):
            left = self._apply_next_operator(left)
        return left

    def _has_binary_operator(self, minimum_precedence):
        context = self._context
        stream = context["stream"]
        kind, operator = stream.current()
        if kind != "operator":
            return False
        precedence_values = self.PRECEDENCE
        precedence = precedence_values.get(operator)
        if precedence is None:
            return False
        return precedence >= minimum_precedence

    def _apply_next_operator(self, left):
        context = self._context
        stream = context["stream"]
        _kind, operator = stream.take()
        precedence = self.PRECEDENCE[operator]
        right = self._expression(precedence + 1)
        return BinaryOperations.apply(operator, left, right)

    def _primary(self):
        context = self._context
        stream = context["stream"]
        kind, value = stream.take()
        handlers = {
            "number": self._identity,
            "string": self._identity,
            "color": self._identity,
            "identifier": self._identifier,
            "operator": self._operator,
        }
        handler = handlers.get(kind, self._empty)
        return handler(value)

    def _operator(self, operator):
        if operator == "-":
            return -_as_number(self._primary())
        if operator == "(":
            return self._parenthesized()
        return operator

    def _parenthesized(self):
        value = self._expression(0)
        self._discard_closing_parenthesis()
        return value

    def _identifier(self, value):
        context = self._context
        stream = context["stream"]
        if stream.peek("("):
            return self._function(value)
        literals = {"true": True, "false": False}
        normalized = str(value).lower()
        return literals.get(normalized, value)

    def _function(self, value):
        context = self._context
        stream = context["stream"]
        stream.advance()
        arguments = self._arguments()
        self._discard_closing_parenthesis()
        functions = FormulaFunctions(self._context)
        return functions.call(str(value).lower(), arguments)

    def _arguments(self):
        arguments = FormulaArguments()
        context = self._context
        stream = context["stream"]
        if stream.peek(")"):
            return arguments
        while self._append_argument(arguments):
            pass
        return arguments

    def _append_argument(self, arguments):
        arguments.append(self._expression(0))
        context = self._context
        stream = context["stream"]
        if not stream.peek(","):
            return False
        stream.advance()
        return True

    def _discard_closing_parenthesis(self):
        context = self._context
        stream = context["stream"]
        if stream.peek(")"):
            stream.advance()

    @staticmethod
    def _identity(value):
        return value

    @staticmethod
    def _empty(_value):
        return ""


def eval_formula(text, global_values=None):
    """Evaluate one formula while preserving non-string result types."""
    if not isinstance(text, str):
        return text
    stripped = text.strip()
    if _is_single_formula(stripped):
        return FormulaParser(stripped[1:-1], global_values).parse()
    return sample_eval(text, global_values)


def _is_single_formula(text):
    return text.startswith("$") and text.endswith("$") and text.count("$") == 2


def sample_eval(text, global_values=None):
    """Replace embedded formulas with deterministic desktop preview values."""
    if not isinstance(text, str):
        return ""
    evaluator = EmbeddedFormulaEvaluator(global_values)
    output = re.sub(r"\$(.+?)\$", evaluator.evaluate, text, flags=re.S)
    output = re.sub(r"\[/?[biu]\]", "", output, flags=re.I)
    return output.replace("\r", "").strip()


class EmbeddedFormulaEvaluator:
    def __init__(self, global_values=None):
        self._global_values = global_values

    def evaluate(self, match):
        source = match.group(1)
        parsed = FormulaParser(source, self._global_values).parse()
        return _formula_text(parsed)
