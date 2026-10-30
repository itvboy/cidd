from cidd.engine import generation
from cidd.providers.base import LLMProvider, LLMResponse


class StubProvider(LLMProvider):
    def generate(self, system_prompt, user_prompt):
        return LLMResponse(content='class Todo {}', input_tokens=1, output_tokens=3)


def test_capture_preserves_exact_messages():
    wrapped = generation.PromptRecordingProvider(StubProvider())
    response = wrapped.generate('system\nline 2', 'user\nline 2')
    assert wrapped.messages == ('system\nline 2', 'user\nline 2')
    assert response.content == 'class Todo {}'


def test_debug_copy_is_comment_only_and_original_unchanged():
    source = 'class Todo {}'
    output = generation.debug_source(source, ('SYS', 'CONTRACT\nSKILL'), 'dart')
    assert output.startswith(source + '\n')
    assert '// ------- PROMPT USED -------' in output
    assert '// SYS' in output
    assert '// ------- CONTEXT USED -------' in output
    assert '// CONTRACT\n// SKILL' in output
    assert source == 'class Todo {}'
