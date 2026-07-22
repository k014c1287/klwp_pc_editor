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
    r'''(?P<operator>!=|~=|<=|>=|[=<>+\-*/|&(),])|'''
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
            "~=": BinaryOperations.regular_expression,
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
    def regular_expression(left, right):
        pattern = str(right)
        return re.search(pattern, str(left), re.IGNORECASE) is not None

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


class PreviewFormulaValues:
    def __init__(self, context):
        self._context = context

    def value(self, section, arguments, defaults, fallback):
        key = arguments.key()
        return self.named(section, key, defaults, fallback)

    def named(self, section, key, defaults, fallback):
        context = self._context
        global_values = context["globals"]
        preview = global_values.optional("__preview__", {})
        values = self._section(preview, section)
        if key in values:
            return values[key]
        return defaults.get(key, fallback)

    @staticmethod
    def _section(preview, section):
        if not isinstance(preview, dict):
            return {}
        values = preview.get(section, {})
        if isinstance(values, dict):
            return values
        return {}


class MathematicsUtilities:
    @staticmethod
    def apply(arguments):
        mode = arguments.key()
        handlers = {
            "ceil": MathematicsUtilities._ceil,
            "floor": MathematicsUtilities._floor,
            "sqrt": MathematicsUtilities._sqrt,
            "round": MathematicsUtilities._round,
            "min": MathematicsUtilities._minimum,
            "max": MathematicsUtilities._maximum,
            "abs": MathematicsUtilities._absolute,
            "pow": MathematicsUtilities._power,
            "sin": MathematicsUtilities._sine,
            "cos": MathematicsUtilities._cosine,
            "tan": MathematicsUtilities._tangent,
        }
        handler = handlers.get(mode, MathematicsUtilities._round)
        return handler(arguments)

    @staticmethod
    def _number(arguments):
        return _as_number(arguments.optional(1, arguments.optional(0)))

    @staticmethod
    def _ceil(arguments):
        return math.ceil(MathematicsUtilities._number(arguments))

    @staticmethod
    def _floor(arguments):
        return math.floor(MathematicsUtilities._number(arguments))

    @staticmethod
    def _sqrt(arguments):
        return math.sqrt(MathematicsUtilities._number(arguments))

    @staticmethod
    def _round(arguments):
        digits = int(_as_number(arguments.optional(2)))
        return round(MathematicsUtilities._number(arguments), digits)

    @staticmethod
    def _minimum(arguments):
        return min(map(_as_number, arguments._values[1:]))

    @staticmethod
    def _maximum(arguments):
        return max(map(_as_number, arguments._values[1:]))

    @staticmethod
    def _absolute(arguments):
        return abs(MathematicsUtilities._number(arguments))

    @staticmethod
    def _power(arguments):
        exponent = _as_number(arguments.optional(2))
        return math.pow(MathematicsUtilities._number(arguments), exponent)

    @staticmethod
    def _sine(arguments):
        radians = math.radians(MathematicsUtilities._number(arguments))
        return math.sin(radians)

    @staticmethod
    def _cosine(arguments):
        radians = math.radians(MathematicsUtilities._number(arguments))
        return math.cos(radians)

    @staticmethod
    def _tangent(arguments):
        radians = math.radians(MathematicsUtilities._number(arguments))
        return math.tan(radians)


class TextConversions:
    @staticmethod
    def apply(arguments):
        mode = arguments.key()
        text = _formula_text(arguments.optional(1))
        handlers = {
            "low": str.lower, "l": str.lower,
            "up": str.upper, "u": str.upper,
            "cap": str.title, "c": str.title,
            "len": len,
        }
        handler = handlers.get(mode)
        if handler is not None:
            return handler(text)
        return TextConversions._advanced(mode, text, arguments)

    @staticmethod
    def _advanced(mode, text, arguments):
        if mode == "split":
            return TextConversions._split(text, arguments)
        if mode == "count":
            return text.count(_formula_text(arguments.optional(2)))
        if mode in ("cut", "ell"):
            return TextConversions._cut(mode, text, arguments)
        return ""

    @staticmethod
    def _split(text, arguments):
        separator = _formula_text(arguments.optional(2, "#"))
        parts = text.split(separator)
        index = int(_as_number(arguments.optional(3, 0)))
        if 0 <= index < len(parts):
            return parts[index]
        return ""

    @staticmethod
    def _cut(mode, text, arguments):
        start = int(_as_number(arguments.optional(2, 0)))
        if len(arguments) < 4:
            result = TextConversions._edge_cut(text, start)
            return TextConversions._ellipsized(mode, text, result)
        length = int(_as_number(arguments.optional(3, 0)))
        result = text[start:start + length]
        return TextConversions._ellipsized(mode, text, result)

    @staticmethod
    def _edge_cut(text, amount):
        if amount < 0:
            return text[amount:]
        return text[:amount]

    @staticmethod
    def _ellipsized(mode, source, result):
        if mode == "ell" and len(result) < len(source):
            return result + "…"
        return result


class ColorEditor:
    @staticmethod
    def apply(arguments):
        color = ColorEditor._channels(arguments.optional(0))
        mode = arguments.key(1)
        if mode == "invert":
            return ColorEditor._invert(color)
        if mode == "contrast":
            return ColorEditor._contrast(color)
        if mode == "alpha":
            percentage = _as_number(arguments.optional(2, 100))
            alpha = int(percentage * 255.0 / 100.0 + 0.5)
            return ColorEditor._encoded((alpha,) + color[1:])
        return ColorEditor._encoded(color)

    @staticmethod
    def _channels(value):
        hexadecimal = str(value).lstrip("#")
        if len(hexadecimal) == 6:
            hexadecimal = "FF" + hexadecimal
        if len(hexadecimal) != 8:
            hexadecimal = "FFFFFFFF"
        return tuple(int(hexadecimal[index:index + 2], 16)
                     for index in range(0, 8, 2))

    @staticmethod
    def _invert(color):
        return ColorEditor._encoded(
            (color[0], 255 - color[1], 255 - color[2], 255 - color[3]))

    @staticmethod
    def _contrast(color):
        luminance = color[1] * 0.299 + color[2] * 0.587 + color[3] * 0.114
        if luminance > 186:
            return "#FF000000"
        return "#FFFFFFFF"

    @staticmethod
    def _encoded(color):
        values = map(lambda value: max(0, min(255, value)), color)
        return "#" + "".join(f"{value:02X}" for value in values)


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
            "ce": self._color_editor,
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
        pattern = _formula_text(arguments.optional(0))
        direct = date_values.get(pattern)
        if direct is not None:
            return direct
        return self._formatted_date_pattern(pattern, date_values)

    @staticmethod
    def _formatted_date_pattern(pattern, values):
        names = sorted(values, key=len, reverse=True)
        output = pattern
        for name in names:
            output = output.replace(name, str(values[name]))
        return output

    def _media_information(self, arguments):
        values = {
            "title": "Song Title", "artist": "Artist Name", "state": "PLAYING",
            "percent": 40.0, "cover": "", "pos": 88000.0, "len": 218000.0,
        }
        return PreviewFormulaValues(self._context).value(
            "media", arguments, values, 0.0)

    def _weather_information(self, arguments):
        values = {
            "temp": 32.0, "flik": 32.0, "tempu": "C",
            "icon": "CLEAR", "cond": "Mostly Cloudy",
        }
        return PreviewFormulaValues(self._context).value(
            "weather", arguments, values, 32.0)

    def _weather_forecast(self, arguments):
        values = {"max": 29.0, "min": 26.0, "cond": "MOSTLY_CLOUDY"}
        return PreviewFormulaValues(self._context).value(
            "forecast", arguments, values, 27.0)

    def _battery_information(self, arguments):
        values = {"level": 95.0, "charging": 0.0, "fullempty": "future"}
        return PreviewFormulaValues(self._context).value(
            "battery", arguments, values, 95.0)

    def _location_information(self, arguments):
        values = {"loc": "横浜市", "country": "日本", "postal": "231-0836"}
        return PreviewFormulaValues(self._context).value(
            "location", arguments, values, "横浜市")

    def _network_connection(self, arguments):
        values = {
            "wifi": "CONNECTED", "ssid": "SSID-328F3B", "wsig": 9.0,
            "csig": 4.0, "dtype": "LTE", "cell": "ON",
        }
        return PreviewFormulaValues(self._context).value(
            "network", arguments, values, "")

    def _resource_monitor(self, arguments):
        values = {"cused": 42.0, "fstot": 256.0, "fsfree": 59.0}
        return PreviewFormulaValues(self._context).value(
            "resource", arguments, values, 42.0)

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
        return MathematicsUtilities.apply(arguments)

    @staticmethod
    def _time_format(arguments):
        value = arguments.optional(0)
        if arguments.key(1) == "mm:ss" and isinstance(value, (int, float)):
            seconds = int(value / 1000)
            return f"{seconds // 60:02d}:{seconds % 60:02d}"
        return "2時間後"

    @staticmethod
    def _text_converter(arguments):
        return TextConversions.apply(arguments)

    @staticmethod
    def _color_editor(arguments):
        return ColorEditor.apply(arguments)

    def _calendar_information(self, arguments):
        values = {"title": "学校"}
        return PreviewFormulaValues(self._context).value(
            "calendar", arguments, values, "")

    def _astronomy_information(self, arguments):
        values = {"seasonc": "SPRING"}
        return PreviewFormulaValues(self._context).value(
            "astronomy", arguments, values, "")

    def _browser_information(self, arguments):
        key = _formula_text(arguments.optional(1)).lower()
        values = {"gpt_ans": "Preview broadcast value"}
        return PreviewFormulaValues(self._context).named(
            "broadcast", key, values, "")

    @staticmethod
    def _empty(_arguments):
        return ""


class FormulaParser:
    """Precedence-climbing parser backed by one context object."""

    PRECEDENCE = {
        "|": 1, "&": 2, "=": 3, "!=": 3, "~=": 3, "<": 3,
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
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
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
