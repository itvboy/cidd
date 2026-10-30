import json
from pathlib import Path
import pytest
from cidd.engine.assembly import _code_with_imports, _prepare_dependencies, AssemblyError


def graph():
    return {'fingerprint':'demo', 'contracts':[
        {'id':'domain.Todo','dependencies':[], 'specification':'{}'},
        {'id':'domain.TodoRepository','dependencies':[{'id':'domain.Todo','interface':'class Todo {}'}], 'specification':'{}'},
        {'id':'application.ListTodos','dependencies':[
            {'id':'domain.TodoRepository','interface':'abstract class TodoRepository { List<Todo> getAll(); }'}], 'specification':'{}'},
        {'id':'infrastructure.TodoDatabase','dependencies':[], 'specification':json.dumps({'provider':'sqlite3'})},
    ]}


def test_qualifier_normalization():
    source = "class ListTodos { final domain.TodoRepository repository; List<domain.Todo> execute() => repository.getAll(); }\n"
    output, added = _code_with_imports(source,current='application.ListTodos',graph=graph(),package='todo')
    assert 'domain.TodoRepository repository' not in output
    assert 'final TodoRepository repository;' in output
    assert 'List<Todo> execute()' in output
    assert "import 'package:todo/domain/todo.dart';" in output
    assert "import 'package:todo/domain/todo_repository.dart';" in output


def test_comment_untouched():
    source = '// domain.TodoRepository is mentioned\nclass ListTodos { final domain.TodoRepository repository; }\n'
    output, _ = _code_with_imports(source,current='application.ListTodos',graph=graph(),package='todo')
    assert '// domain.TodoRepository is mentioned' in output


def test_no_unauthorized_qualified_reference():
    source = 'class ListTodos { domain.Todo x; }'
    g = graph()
    g['contracts'][2]['dependencies'] = []
    with pytest.raises(AssemblyError):
        _code_with_imports(source,current='application.ListTodos',graph=g,package='todo')


def test_dependency_added_once(tmp_path):
    file = tmp_path/'pubspec.yaml'
    file.write_text('name: todo\ndependencies:\n  flutter:\n    sdk: flutter\n',encoding='utf-8')
    assert _prepare_dependencies(graph(),tmp_path) == ['sqlite3: 3.8.0']
    assert _prepare_dependencies(graph(),tmp_path) == []
    assert file.read_text().count('sqlite3:') == 1
