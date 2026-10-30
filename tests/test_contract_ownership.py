import pytest

from cidd.engine.sanitizer import (
    SanitizationError,
    sanitize_dart,
)


DEPENDENCIES = (
    "application.CreateTodo",
    "application.CompleteTodo",
    "application.ListTodos",
    "application.DeleteTodo",
)

ALL_CONTRACTS = (
    "presentation.TodoView",
    *DEPENDENCIES,
)


def sanitize(source: str):
    return sanitize_dart(
        source,
        contract_id="presentation.TodoView",
        dependencies=DEPENDENCIES,
        all_contract_ids=ALL_CONTRACTS,
        package_name="todo",
    )


def test_accepts_owned_helper_widgets():
    source = """
import 'package:flutter/material.dart';

class TodoInput extends StatelessWidget {
  const TodoInput({super.key});

  @override
  Widget build(BuildContext context) {
    return const SizedBox();
  }
}

class TodoView extends StatelessWidget {
  const TodoView({super.key});

  @override
  Widget build(BuildContext context) {
    return const TodoInput();
  }
}
"""

    result = sanitize(source)

    assert "class TodoInput" in result.source
    assert "class TodoView" in result.source


def test_rejects_redefined_dependency():
    source = """
abstract interface class CreateTodo {
  void execute(String title);
}

class TodoView {}
"""

    with pytest.raises(
        SanitizationError,
        match="Worker redefined dependency contracts: CreateTodo",
    ):
        sanitize(source)


def test_rejects_multiple_redefined_dependencies():
    source = """
abstract interface class CreateTodo {}

abstract interface class CompleteTodo {}

abstract interface class ListTodos {}

abstract interface class DeleteTodo {}

class TodoView {}
"""

    with pytest.raises(SanitizationError) as exc:
        sanitize(source)

    message = str(exc.value)

    for name in (
        "CreateTodo",
        "CompleteTodo",
        "ListTodos",
        "DeleteTodo",
    ):
        assert name in message

def test_normalizes_dot_style_package_import():
    source = """
import 'package:application.CreateTodo.dart';

class TodoView {}
"""

    result = sanitize(source)

    assert (
        "import 'package:todo/application/create_todo.dart';"
        in result.source
    )
    assert "package:application.CreateTodo.dart" not in result.source

def test_removes_unused_self_import_with_alias():
    source = """
import 'package:presentation.TodoView.dart' as presentation;

class TodoView {}
"""

    result = sanitize(source)

    assert "package:presentation.TodoView.dart" not in result.source
    assert "class TodoView {}" in result.source


def test_rejects_self_import_when_alias_is_used():
    source = """
import 'package:presentation.TodoView.dart' as presentation;

class TodoView {
  void example() {
    presentation.TodoView();
  }
}
"""

    with pytest.raises(
        SanitizationError,
        match="Self-import alias is referenced",
    ):
        sanitize(source)

def test_preserves_authorized_import_alias():
    source = """
import 'package:application.CreateTodo.dart' as create;

class TodoView {}
"""

    result = sanitize(source)

    assert (
        "import 'package:todo/application/create_todo.dart' "
        "as create;"
    ) in result.source

def test_removes_unused_self_import():
    source = """
import 'package:presentation.TodoView.dart' as presentation;

class TodoView {}
"""

    result = sanitize(source)

    assert "package:presentation.TodoView.dart" not in result.source
    assert "class TodoView" in result.source
