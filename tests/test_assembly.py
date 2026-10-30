import json
from pathlib import Path
import pytest
from cidd.engine.assembly import assemble, AssemblyError


def test_assembly_adds_required_imports_and_preserves_original(tmp_path):
    project=tmp_path/'project'; project.mkdir()
    (project/'pubspec.yaml').write_text('name: todo\n')
    run=tmp_path/'run'; (run/'application').mkdir(parents=True)
    raw='class CreateTodo {\n final TodoRepository repository;\n Todo execute(String title) => repository.add(Todo(title: title));\n}\n'
    (run/'application'/'CreateTodo.dart').write_text(raw)
    graph={'fingerprint':'test','contracts':[
      {'id':'domain.Todo','dependencies':[]},
      {'id':'domain.TodoRepository','dependencies':[{'id':'domain.Todo','interface':'class Todo {}'}]},
      {'id':'application.CreateTodo','dependencies':[
        {'id':'domain.Todo','interface':'class Todo {}'},
        {'id':'domain.TodoRepository','interface':'abstract class TodoRepository {}'}]}]}
    (run/'domain').mkdir()
    (run/'domain'/'Todo.dart').write_text('class Todo { Todo({required String title}); }')
    (run/'domain'/'TodoRepository.dart').write_text('abstract class TodoRepository { Todo add(Todo todo); }')
    gp=tmp_path/'graph.json'; gp.write_text(json.dumps(graph))
    out=tmp_path/'assembled'
    report=assemble(gp,run,project,out,analyze=False)
    code=(out/'lib/application/create_todo.dart').read_text()
    assert "import 'package:todo/domain/todo.dart';" in code
    assert "import 'package:todo/domain/todo_repository.dart';" in code
    assert raw==(run/'application/CreateTodo.dart').read_text()
    assert all(item['status']=='ASSEMBLED' for item in report['contracts'])


def test_no_output_overwrite(tmp_path):
    project=tmp_path/'project'; project.mkdir(); (project/'pubspec.yaml').write_text('name: todo\n')
    graph=tmp_path/'g.json'; graph.write_text(json.dumps({'fingerprint':'t','contracts':[]}))
    output=tmp_path/'existing'; output.mkdir()
    with pytest.raises(AssemblyError, match='already exists'):
        assemble(graph,tmp_path/'run',project,output,analyze=False)
