from cidd.skills.registry import resolve_skill


def test_dart_skills_are_nonempty_and_distinct():
    identifiers = [('domain.Todo', {'fields': [{'name': 'id'}]}),
                   ('domain.TodoRepository', {}), ('application.CreateTodo', {}),
                   ('infrastructure.TodoDatabase', {}), ('presentation.TodoView', {})]
    prompts = [resolve_skill('dart', identifier, entry) for identifier, entry in identifiers]
    assert all(prompts)
    assert len(set(prompts)) == len(prompts)
    assert 'StatelessWidget' in prompts[-1]
    assert 'duplicate domain' in prompts[-2]


def test_explicit_skill_is_retained():
    assert resolve_skill('dart', 'domain.Todo', {'fields': [], 'skill': 'explicit'}) == 'explicit'
