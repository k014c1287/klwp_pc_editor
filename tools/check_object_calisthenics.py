"""Static architecture checks for the project's Object Calisthenics rules."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import sys


MAXIMUM_METHOD_LINES = 30
MAXIMUM_CLASS_LINES = 250
MAXIMUM_INSTANCE_VARIABLES = 2
CONTROL_NODES = (ast.If, ast.For, ast.While, ast.Try, ast.With)


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    message: str

    def display(self):
        return f"{self.path}:{self.line}: {self.message}"


class ModuleInspector:
    def __init__(self, path):
        self._path = path
        source = path.read_text(encoding="utf-8-sig")
        self._tree = ast.parse(source, filename=str(path))

    def violations(self):
        checks = (
            self._else_violations,
            self._method_size_violations,
            self._class_size_violations,
            self._nesting_violations,
            self._instance_variable_violations,
            self._property_violations,
            self._message_chain_violations,
        )
        result = []
        for check in checks:
            result.extend(check())
        return result

    def _else_violations(self):
        nodes = filter(self._has_else_clause, ast.walk(self._tree))
        return [self._violation(node, "else clause is not allowed")
                for node in nodes]

    @staticmethod
    def _has_else_clause(node):
        return isinstance(node, (ast.If, ast.For, ast.While, ast.Try)) \
            and bool(node.orelse)

    def _method_size_violations(self):
        functions = filter(
            lambda node: isinstance(node, ast.FunctionDef),
            ast.walk(self._tree))
        return [
            self._violation(
                function,
                f"{function.name} has more than {MAXIMUM_METHOD_LINES} lines")
            for function in functions
            if function.end_lineno - function.lineno + 1 > MAXIMUM_METHOD_LINES
        ]

    def _class_size_violations(self):
        classes = filter(
            lambda node: isinstance(node, ast.ClassDef),
            ast.walk(self._tree))
        return [
            self._violation(
                class_node,
                f"{class_node.name} has more than {MAXIMUM_CLASS_LINES} lines")
            for class_node in classes
            if class_node.end_lineno - class_node.lineno + 1 > MAXIMUM_CLASS_LINES
        ]

    def _nesting_violations(self):
        result = []
        functions = filter(
            lambda node: isinstance(node, ast.FunctionDef),
            ast.walk(self._tree))
        for function in functions:
            result.extend(self._function_nesting_violations(function))
        return result

    def _function_nesting_violations(self, function):
        parents = {
            child: parent
            for parent in ast.walk(function)
            for child in ast.iter_child_nodes(parent)
        }
        controls = filter(
            lambda node: isinstance(node, CONTROL_NODES),
            ast.walk(function))
        return [
            self._violation(node, "method indentation exceeds one level")
            for node in controls
            if self._control_depth(node, function, parents) > 1
        ]

    @staticmethod
    def _control_depth(node, function, parents):
        depth = 1
        current = node
        while current in parents and parents[current] is not function:
            current = parents[current]
            depth += int(isinstance(current, CONTROL_NODES))
        return depth

    def _instance_variable_violations(self):
        classes = filter(
            lambda node: isinstance(node, ast.ClassDef),
            ast.walk(self._tree))
        violations = map(self._class_instance_violation, classes)
        return list(filter(None, violations))

    def _class_instance_violation(self, class_node):
        names = self._instance_variables(class_node)
        if len(names) <= MAXIMUM_INSTANCE_VARIABLES:
            return None
        message = (
            f"{class_node.name} has {len(names)} instance variables: "
            + ", ".join(sorted(names)))
        return self._violation(class_node, message)

    @staticmethod
    def _instance_variables(class_node):
        names = set()
        assignments = filter(
            lambda node: isinstance(node, (ast.Assign, ast.AnnAssign)),
            ast.walk(class_node))
        for assignment in assignments:
            targets = assignment.targets if isinstance(
                assignment, ast.Assign) else [assignment.target]
            names.update(ModuleInspector._self_attributes(targets))
        return names

    @staticmethod
    def _self_attributes(targets):
        names = map(ModuleInspector._self_attribute, targets)
        return set(filter(None, names))

    @staticmethod
    def _self_attribute(target):
        if not isinstance(target, ast.Attribute):
            return None
        value = target.value
        if not isinstance(value, ast.Name) or value.id != "self":
            return None
        return target.attr

    def _property_violations(self):
        functions = filter(
            lambda node: isinstance(node, ast.FunctionDef),
            ast.walk(self._tree))
        return [
            self._violation(function, "property/getter/setter is not allowed")
            for function in functions
            if any(self._property_decorator(decorator)
                   for decorator in function.decorator_list)
        ]

    @staticmethod
    def _property_decorator(decorator):
        if isinstance(decorator, ast.Name):
            return decorator.id == "property"
        if isinstance(decorator, ast.Attribute):
            return decorator.attr in ("getter", "setter", "deleter")
        return False

    def _message_chain_violations(self):
        attributes = filter(
            lambda node: isinstance(node, ast.Attribute),
            ast.walk(self._tree))
        return [
            self._violation(
                attribute,
                "message chain crosses more than one object on a line")
            for attribute in attributes
            if self._attribute_depth(attribute) > 1
        ]

    @staticmethod
    def _attribute_depth(attribute):
        depth = 0
        current = attribute
        while isinstance(current, ast.Attribute):
            depth += 1
            current = current.value
        return depth

    def _violation(self, node, message):
        return Violation(self._path, node.lineno, message)


def inspect_package(package_root):
    paths = sorted(Path(package_root).rglob("*.py"))
    violations = []
    for path in paths:
        inspector = ModuleInspector(path)
        violations.extend(inspector.violations())
    return sorted(violations, key=lambda item: (str(item.path), item.line))


def main():
    package_roots = [Path(sys.argv[1])] if len(sys.argv) > 1 \
        else [Path("klwp"), Path("tools")]
    violations = []
    for package_root in package_roots:
        violations.extend(inspect_package(package_root))
    for violation in violations:
        print(violation.display())
    if violations:
        return 1
    roots = ", ".join(map(str, package_roots))
    print(f"Object Calisthenics checks passed: {roots}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
