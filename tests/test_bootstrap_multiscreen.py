
import json

import pytest

from cidd.engine.bootstrap import (
    BootstrapError,
    bootstrap_flutter,
)


def test_multiscreen_bootstrap(tmp_path):
    main = tmp_path / "lib" / "main.dart"
    main.parent.mkdir(parents=True)

    main.write_text(
        "class MyApp {}\nclass MyHomePage {}\n",
        encoding="utf-8",
    )

    def contract(cid, specification=None, dependencies=None):
        return {
            "id": cid,
            "specification": json.dumps(specification or {}),
            "dependencies": [
                {"id": dep, "interface": ""}
                for dep in (dependencies or [])
            ],
        }

    graph = {
        "presentation": {
            "entry_screen": "SplashScreen",
            "assets": [],
        },
        "contracts": [
            contract(
                "domain.TodoRepository",
            ),
            contract(
                "application.CreateTodo",
                dependencies=["domain.TodoRepository"],
            ),
            contract(
                "infrastructure.TodoDatabase",
                {"provider": "sqlite3"},
                dependencies=["domain.TodoRepository"],
            ),
            contract(
                "presentation.SplashScreen",
            ),
            contract(
                "presentation.TodoView",
                dependencies=["application.CreateTodo"],
            ),
            contract(
                "presentation.AboutView",
            ),
        ],
    }

    report = bootstrap_flutter(
        graph,
        tmp_path,
        "todo_plus",
    )

    code = main.read_text(encoding="utf-8")

    assert report["status"] == "PASS"
    assert "initialRoute: '/splash'" in code
    assert "'/splash':" in code
    assert "'/todo':" in code
    assert "'/about':" in code

    assert "SplashScreen()" in code
    assert "AboutView()" in code
    assert "createTodo: CreateTodo(repository)" in code


def test_multiscreen_requires_entry_screen(tmp_path):
    graph = {
        "presentation": {},
        "contracts": [
            {
                "id": "presentation.SplashScreen",
                "specification": "{}",
                "dependencies": [],
            },
            {
                "id": "presentation.TodoView",
                "specification": "{}",
                "dependencies": [],
            },
        ],
    }

    with pytest.raises(BootstrapError):
        bootstrap_flutter(graph, tmp_path, "todo_plus")
