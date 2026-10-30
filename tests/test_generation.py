import json
from pathlib import Path
import pytest
from cidd.contracts.materializer import build_graph, write_graph
from cidd.engine.generation import load_verified_graph, generate_graph, GenerationError
from cidd.providers.base import LLMProvider, LLMResponse

class DummyProvider(LLMProvider):
    def __init__(self): self.calls=[]
    def generate(self, system_prompt, user_prompt):
        self.calls.append(user_prompt)
        return LLMResponse(content='class Todo {}', input_tokens=11, output_tokens=3)

@pytest.fixture
def graph_file(tmp_path):
    genome={"genome":"0.1","project":{"name":"todo","template":"flutter","language":"dart"},
            "domain":{"entities":[{"name":"Todo","fields":[{"name":"id","type":"int"}]}]},
            "application":{"use_cases":[]},"infrastructure":{"persistence":[]},"presentation":{"framework":"flutter","screens":[]}}
    path=tmp_path/'graph.json'
    write_graph(build_graph(genome),path)
    return path

def test_generate_stages_code_and_metrics(graph_file,tmp_path):
    provider=DummyProvider()
    result=generate_graph(graph_file,tmp_path/'runs',provider)
    assert result['results'][0]['status']=='GENERATED'
    assert result['input_tokens']==11 and result['output_tokens']==3
    assert (Path(result['run_dir'])/'domain/Todo.dart').read_text().strip()=='class Todo {}'
    assert len(provider.calls)==1

def test_detects_tampering_before_llm(graph_file,tmp_path):
    graph=json.loads(graph_file.read_text())
    graph['contracts'][0]['specification']='changed'
    graph_file.write_text(json.dumps(graph))
    provider=DummyProvider()
    with pytest.raises(GenerationError,match='fingerprint'):
        generate_graph(graph_file,tmp_path/'runs',provider)
    assert provider.calls==[]

def test_prevent_overwrite(graph_file,tmp_path):
    provider=DummyProvider()
    generate_graph(graph_file,tmp_path/'runs',provider)
    with pytest.raises(GenerationError,match='already exists'):
        generate_graph(graph_file,tmp_path/'runs',provider)
    assert len(provider.calls)==1
