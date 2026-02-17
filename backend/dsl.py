import re
from dataclasses import dataclass
from typing import Any, Optional

LOGICAL_OPS = ("and", "or", "not")
COMPARISON_OPS = ("==", "!=", "in", "not in", ">", ">=", "<", "<=")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Token:
    kind: str
    value: Any = None


def _tokenize(s: str) -> tuple[list[Token], Optional[str]]:
    s = s.strip()
    if not s:
        return [], "Empty rule"
    tokens: list[Token] = []
    i = 0
    n = len(s)

    def skip_ws():
        nonlocal i
        while i < n and s[i] in " \t\n\r":
            i += 1

    def read_string(quote: str) -> Optional[str]:
        nonlocal i
        i += 1
        start = i
        while i < n:
            if s[i] == "\\" and i + 1 < n:
                i += 2
                continue
            if s[i] == quote:
                val = s[start:i].encode().decode("unicode_escape") if "\\" in s[start:i] else s[start:i]
                i += 1
                return val
            i += 1
        return None

    while i < n:
        skip_ws()
        if i >= n:
            break
        c = s[i]
        if c in "()":
            tokens.append(Token("LPAREN" if c == "(" else "RPAREN"))
            i += 1
            continue
        if c in "[]":
            tokens.append(Token("LBRACKET" if c == "[" else "RBRACKET"))
            i += 1
            continue
        if c == ",":
            tokens.append(Token("COMMA"))
            i += 1
            continue
        if c in "\"\'":
            val = read_string(c)
            if val is None:
                return [], "Unclosed string"
            tokens.append(Token("STRING", val))
            continue
        if c in "0123456789.-" or (c == "-" and i + 1 < n and s[i + 1].isdigit()):
            start = i
            if s[i] == "-":
                i += 1
            while i < n and (s[i].isdigit() or s[i] == "."):
                i += 1
            num_s = s[start:i]
            try:
                if "." in num_s:
                    tokens.append(Token("NUMBER", float(num_s)))
                else:
                    tokens.append(Token("NUMBER", int(num_s)))
            except ValueError:
                return [], f"Invalid number: {num_s!r}"
            continue
        if c == "=":
            i += 1
            if i < n and s[i] == "=":
                i += 1
                tokens.append(Token("OP", "=="))
            else:
                return [], "Expected =="
            continue
        if c == "!":
            i += 1
            if i < n and s[i] == "=":
                i += 1
                tokens.append(Token("OP", "!="))
            else:
                return [], "Expected !="
            continue
        if c in "><":
            op = c
            i += 1
            if i < n and s[i] == "=":
                op += "="
                i += 1
            tokens.append(Token("OP", ">=" if op == ">=" else "<=" if op == "<=" else op))
            continue
        if s[i].isalpha() or s[i] == "_":
            start = i
            while i < n and (s[i].isalnum() or s[i] == "_"):
                i += 1
            word = s[start:i].strip().lower()
            raw = s[start:i]
            if word == "and":
                tokens.append(Token("AND"))
            elif word == "or":
                tokens.append(Token("OR"))
            elif word == "not":
                skip_ws()
                if i < n and s[i].isalpha():
                    start2 = i
                    while i < n and (s[i].isalnum() or s[i] == "_"):
                        i += 1
                    if s[start2:i].lower() == "in":
                        tokens.append(Token("OP", "not in"))
                    else:
                        i = start2
                        tokens.append(Token("NOT"))
                else:
                    tokens.append(Token("NOT"))
            elif word == "in":
                tokens.append(Token("OP", "in"))
            elif word == "true":
                tokens.append(Token("BOOL", True))
            elif word == "false":
                tokens.append(Token("BOOL", False))
            else:
                tokens.append(Token("IDENT", raw))
            continue
        return [], f"Unexpected char: {c!r} at {i}"
    tokens.append(Token("END"))
    return tokens, None


def _parse(tokens: list[Token]) -> tuple[Any, Optional[str]]:
    pos = [0]

    def cur() -> Token:
        return tokens[pos[0]] if pos[0] < len(tokens) else Token("END")

    def advance() -> Token:
        t = cur()
        if pos[0] < len(tokens):
            pos[0] += 1
        return t

    def parse_or() -> tuple[Any, Optional[str]]:
        left, err = parse_and()
        if err:
            return None, err
        while cur().kind == "OR":
            advance()
            right, err = parse_and()
            if err:
                return None, err
            left = {"or": [left, right]}
        return left, None

    def parse_and() -> tuple[Any, Optional[str]]:
        left, err = parse_not()
        if err:
            return None, err
        while cur().kind == "AND":
            advance()
            right, err = parse_not()
            if err:
                return None, err
            left = {"and": [left, right]}
        return left, None

    def parse_not() -> tuple[Any, Optional[str]]:
        if cur().kind == "NOT":
            advance()
            inner, err = parse_not()
            if err:
                return None, err
            return {"not": inner}, None
        return parse_primary()

    def parse_primary() -> tuple[Any, Optional[str]]:
        if cur().kind == "LPAREN":
            advance()
            node, err = parse_or()
            if err:
                return None, err
            if cur().kind != "RPAREN":
                return None, "Expected ')'"
            advance()
            return node, None
        return parse_comparison()

    def parse_value() -> tuple[Any, Optional[str]]:
        t = cur()
        if t.kind == "STRING":
            advance()
            return t.value, None
        if t.kind == "NUMBER":
            advance()
            return t.value, None
        if t.kind == "BOOL":
            advance()
            return t.value, None
        if t.kind == "LBRACKET":
            advance()
            items = []
            if cur().kind == "RBRACKET":
                advance()
                return None, "Empty list for in/not in"
            while True:
                item, err = parse_value()
                if err:
                    return None, err
                items.append(item)
                if cur().kind == "COMMA":
                    advance()
                    continue
                if cur().kind == "RBRACKET":
                    advance()
                    break
                return None, "Expected ',' or ']'"
            return items, None
        return None, f"Expected value, got: {t.kind}"

    def parse_comparison() -> tuple[Any, Optional[str]]:
        if cur().kind != "IDENT":
            return None, f"Expected attribute name, got: {cur().kind}"
        attr = advance().value
        if cur().kind == "OP":
            op = advance().value
        else:
            return None, f"Expected comparison operator, got: {cur().kind}"
        value, err = parse_value()
        if err:
            return None, err
        return {"attr": attr, "op": op, "value": value}, None

    node, err = parse_or()
    if err:
        return None, err
    if cur().kind != "END":
        return None, f"Unexpected trailing content: {cur().kind}"
    return node, None


def _parse_dsl_string(rule: str) -> tuple[Any, Optional[str]]:
    tokens, err = _tokenize(rule)
    if err:
        return None, err
    return _parse(tokens)


def _is_string(v: Any) -> bool:
    return isinstance(v, str)


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_bool(v: Any) -> bool:
    return isinstance(v, bool)


def _is_date_value(v: Any) -> bool:
    return isinstance(v, str) and bool(DATE_PATTERN.match(v))


def _infer_value_type(value: Any) -> Optional[str]:
    if _is_bool(value):
        return "bool"
    if _is_number(value):
        return "number"
    if _is_date_value(value):
        return "date"
    if _is_string(value):
        return "string"
    return None


def _validate_value_type(value: Any) -> Optional[str]:
    if _infer_value_type(value) is not None:
        return None
    return f"Invalid value type: {type(value).__name__}"


def _validate_comparison_value(op: str, value: Any) -> Optional[str]:
    if op in ("in", "not in"):
        if not isinstance(value, list):
            return "in/not in require a list"
        if len(value) == 0:
            return "in/not in list cannot be empty"
        first_type = _infer_value_type(value[0])
        if first_type is None:
            return _validate_value_type(value[0])
        for i, item in enumerate(value[1:], start=1):
            t = _infer_value_type(item)
            if t is None:
                return _validate_value_type(item)
            if t != first_type:
                return f"List items must have same type (index {i})"
        return None
    return _validate_value_type(value)


def _validate_dsl_node(node: Any) -> Optional[str]:
    if not isinstance(node, dict):
        return "Expected condition or comparison"
    keys = set(node.keys())
    for logical_key in LOGICAL_OPS:
        if keys == {logical_key}:
            payload = node[logical_key]
            if logical_key == "not":
                return _validate_dsl_node(payload)
            if not isinstance(payload, list):
                return f"'{logical_key}' requires a list"
            if logical_key != "or" and len(payload) < 2:
                return f"'{logical_key}' requires at least 2 items"
            if logical_key == "or" and len(payload) < 1:
                return "'or' requires at least 1 item"
            for i, child in enumerate(payload):
                err = _validate_dsl_node(child)
                if err:
                    return f"{logical_key}[{i}]: {err}"
            return None
    if keys <= {"attr", "op", "value"} and "attr" in keys and "op" in keys and "value" in keys:
        attr = node["attr"]
        op = node["op"]
        value = node["value"]
        if not isinstance(attr, str) or not attr.strip():
            return "attr must be non-empty string"
        if not isinstance(op, str):
            return "op must be string"
        op_clean = op.strip()
        if op_clean not in COMPARISON_OPS:
            return f"Invalid operator '{op}'"
        err = _validate_comparison_value(op_clean, value)
        if err:
            return err
        return None
    if keys:
        return f"Unknown node keys: {sorted(keys)}"
    return "Empty object not allowed"


def validate_targeting_rule(rule: Optional[str]) -> bool:
    if rule is None or (isinstance(rule, str) and not rule.strip()):
        return True
    ast, parse_err = _parse_dsl_string(rule)
    if parse_err:
        return False
    temp = _validate_dsl_node(ast)
    return True if temp is None else temp


def _collect_attrs(node: Any) -> set[str]:
    if not isinstance(node, dict):
        return set()
    keys = set(node.keys())
    for logical_key in ("and", "or"):
        if keys == {logical_key}:
            attrs = set()
            for child in node[logical_key]:
                attrs |= _collect_attrs(child)
            return attrs
    if keys == {"not"}:
        return _collect_attrs(node["not"])
    if keys <= {"attr", "op", "value"} and "attr" in keys:
        return {node["attr"]}
    return set()


def _evaluate_node(node: Any, data: dict[str, Any]) -> bool:
    if not isinstance(node, dict):
        return False
    keys = set(node.keys())
    if keys == {"not"}:
        return not _evaluate_node(node["not"], data)
    if keys == {"and"}:
        return all(_evaluate_node(c, data) for c in node["and"])
    if keys == {"or"}:
        return any(_evaluate_node(c, data) for c in node["or"])
    if keys <= {"attr", "op", "value"} and "attr" in keys and "op" in keys and "value" in keys:
        attr = node["attr"]
        op = node["op"]
        value = node["value"]
        lhs = data[attr]
        if op == "==":
            return lhs == value
        if op == "!=":
            return lhs != value
        if op == ">":
            return lhs > value
        if op == ">=":
            return lhs >= value
        if op == "<":
            return lhs < value
        if op == "<=":
            return lhs <= value
        if op == "in":
            return lhs in value
        if op == "not in":
            return lhs not in value
    return False


def evaluate_targeting_rule(dsl: str, data: dict[str, Any]) -> bool:
    if not dsl or not dsl.strip():
        return True
    ast, parse_err = _parse_dsl_string(dsl)
    if parse_err:
        return False
    validation_err = _validate_dsl_node(ast)
    if validation_err:
        return False
    required_attrs = _collect_attrs(ast)
    if not required_attrs.issubset(data.keys()):
        return False
    return _evaluate_node(ast, data)


if __name__ == "__main__":
    assert not validate_targeting_rule("test")
    assert validate_targeting_rule('number > 10 and rule == "ds"')
    assert validate_targeting_rule('страна in ["RU", "KZ"] and версия >= "1.6.0" and платформа == "ios"')
    assert validate_targeting_rule('(segment == "beta") and (country in ["RU", "KZ", "BY"] or tier >= 2) and not (blocked == true)')
    assert validate_targeting_rule('event_date >= "2024-01-01" and event_date <= "2024-12-31" and premium == true and score > 0.5')
    assert validate_targeting_rule('region not in ["EXCLUDED", "TEST"] and (version != "0.0.0" or build > 1000)')
    assert validate_targeting_rule('(a == "x" or b in [1, 2, 3]) and (not (disabled == false) and created >= "2023-06-01")')
    assert not validate_targeting_rule('x like "%test%"')
    assert not validate_targeting_rule('country in []')
    assert not validate_targeting_rule('name == "foo')
    assert validate_targeting_rule("")
    assert validate_targeting_rule(None)

    assert evaluate_targeting_rule("year >= 18", {"year": 18}) is True
    assert evaluate_targeting_rule("year >= 18", {"year": 20}) is True
    assert evaluate_targeting_rule("year >= 18", {"year": 17}) is False
    assert evaluate_targeting_rule('country in ["RU", "KZ"]', {"country": "RU"}) is True
    assert evaluate_targeting_rule('country in ["RU", "KZ"]', {"country": "BY"}) is False
    assert evaluate_targeting_rule('year >= 18 and country == "RU"', {"year": 20, "country": "RU"}) is True
    assert evaluate_targeting_rule('year >= 18 and country == "RU"', {"year": 20, "country": "KZ"}) is False

    assert evaluate_targeting_rule("year >= 18", {}) is False
    assert evaluate_targeting_rule("year >= 18", {"country": "RU"}) is False
    assert evaluate_targeting_rule('year >= 18 and country == "RU"', {"year": 20}) is False
    assert evaluate_targeting_rule('year >= 18 and country == "RU"', {"country": "RU"}) is False

    assert evaluate_targeting_rule("", {"year": 1}) is True
    assert evaluate_targeting_rule("   ", {"year": 1}) is True
