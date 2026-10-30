import pytest
from cidd.contracts.materializer import derive_use_case_interface
from cidd.genome.parser import GenomeError


def test_create_todo_public_interface():
    result = derive_use_case_interface(
        {'name': 'CreateTodo', 'input': {'title': 'string'}, 'output': 'Todo',
         'depends_on': ['domain.Todo', 'domain.TodoRepository']},
        'dart', {'Todo'}, {'domain.TodoRepository'})
    assert 'CreateTodo(TodoRepository repository)' in result
    assert 'Todo execute(String title);' in result


def test_list_todos_public_interface():
    result = derive_use_case_interface(
        {'name': 'ListTodos', 'input': {}, 'output': 'list<Todo>',
         'depends_on': ['domain.TodoRepository']},
        'dart', {'Todo'}, {'domain.TodoRepository'})
    assert 'List<Todo> execute();' in result


def test_reject_unknown_type():
    with pytest.raises(GenomeError):
        derive_use_case_interface({'name': 'Broken', 'input': {}, 'output': 'Magic'},
                                  'dart', {'Todo'}, {'domain.TodoRepository'})
