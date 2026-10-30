import json
import tempfile
import unittest
from pathlib import Path
from cidd.engine.bootstrap import bootstrap_flutter, BootstrapError


def contract(cid, deps=(), spec='{}'):
    return {'id': cid, 'dependencies': [{'id': d} for d in deps], 'specification': spec}


class BootstrapTests(unittest.TestCase):
    def graph(self):
        return {'contracts': [
            contract('presentation.TodoView', ('application.CreateTodo', 'application.ListTodos')),
            contract('application.CreateTodo', ('domain.TodoRepository',)),
            contract('application.ListTodos', ('domain.TodoRepository',)),
            contract('domain.TodoRepository'),
            contract('infrastructure.TodoDatabase', ('domain.TodoRepository',), json.dumps({'provider': 'sqlite3'})),
        ]}

    def test_builds_main_and_removes_only_default_tests(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'lib').mkdir()
            (root/'lib/main.dart').write_text('class MyApp {}\nclass MyHomePage {}')
            (root/'test').mkdir()
            (root/'test/widget_test.dart').write_text("import 'package:flutter_test/flutter_test.dart';\nvoid main() { MyApp(); }")
            (root/'test/custom_test.dart').write_text('my own test')
            report = bootstrap_flutter(self.graph(), root, 'todo')
            main = (root/'lib/main.dart').read_text()
            self.assertEqual(report['status'], 'PASS')
            self.assertIn('TodoDatabase(database)', main)
            self.assertIn('createTodo: CreateTodo(repository)', main)
            self.assertIn('listTodos: ListTodos(repository)', main)
            self.assertFalse((root/'test/widget_test.dart').exists())
            self.assertTrue((root/'test/custom_test.dart').exists())

    def test_fails_closed_without_repository_dependency(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'lib').mkdir()
            (root/'lib/main.dart').write_text('class MyApp {}\nclass MyHomePage {}')
            graph = self.graph()
            graph['contracts'][1]['dependencies'] = []
            with self.assertRaises(BootstrapError):
                bootstrap_flutter(graph, root, 'todo')


if __name__ == '__main__':
    unittest.main()
