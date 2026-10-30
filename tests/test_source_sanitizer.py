from cidd.engine.sanitizer import sanitize_dart, SanitizationError
import pytest

KW = dict(contract_id='application.CreateTodo', dependencies=('domain.Todo','domain.TodoRepository'), all_contract_ids=('application.CreateTodo','domain.Todo','domain.TodoRepository'), package_name='todo')

def test_markdown_and_import_rewrite():
    src = "```dart\nimport 'package:domain/Todo.dart';\nclass CreateTodo {}\n```"
    result = sanitize_dart(src, **KW)
    assert result.markdown_removed
    assert "import 'package:todo/domain/todo.dart';" in result.source
    assert result.imports_rewritten == 1
    assert '```' not in result.source

def test_no_markdown():
    assert sanitize_dart('class CreateTodo {}', **KW).source == 'class CreateTodo {}\n'

def test_reject_unknown_import():
    with pytest.raises(SanitizationError, match='Unknown'):
        sanitize_dart("import 'package:random/foo.dart';\nclass CreateTodo {}", **KW)

def test_reject_undeclared_contract_import():
    with pytest.raises(SanitizationError, match='Unknown'):
        sanitize_dart("import 'package:presentation/TodoView.dart';\nclass CreateTodo {}", **KW)

def test_reject_mixed_markdown():
    with pytest.raises(SanitizationError, match='Ambiguous'):
        sanitize_dart('Here is code\n```dart\nclass X {}\n```', **KW)

def test_deduplicates_imports():
    src = "import 'domain.Todo.dart';\nimport 'package:domain/Todo.dart';\nclass CreateTodo {}"
    assert sanitize_dart(src, **KW).source.count("import 'package:todo/domain/todo.dart';") == 1
