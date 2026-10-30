from cidd.engine.retry import FeedbackProvider
from cidd.providers.base import LLMResponse

class Dummy:
    def __init__(self):
        self.system = None
        self.user = None
    def generate(self, system_prompt, user_prompt):
        self.system, self.user = system_prompt, user_prompt
        return LLMResponse(content='class TodoView {}', input_tokens=4, output_tokens=5)

def test_retry_feedback_is_scoped_to_user_message():
    original = Dummy()
    response = FeedbackProvider(original, 'argument_type_not_assignable at line 149').generate('system unchanged', 'CONTRACT ID: presentation.TodoView')
    assert original.system == 'system unchanged'
    assert original.user.startswith('CONTRACT ID: presentation.TodoView')
    assert 'argument_type_not_assignable at line 149' in original.user
    assert 'Do not patch previous code' in original.user
    assert response.input_tokens == 4
