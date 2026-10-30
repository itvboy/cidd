import json
from copy import deepcopy
from unittest.mock import Mock
import pytest
from cidd.contracts.expander import expand_repository_contracts
from cidd.contracts.materializer import build_graph
from cidd.providers.base import LLMResponse
from cidd.genome.parser import GenomeError


def genome():
    return {'genome':'0.1', 'project':{'name':'todo','template':'flutter','language':'dart'},
            'domain':{'entities':[{'name':'Todo','interface':'class Todo { final int id; }'}]},
            'application':{'use_cases':[{'name':'CreateTodo','rules':['Create and persist a Todo']}]},
            'infrastructure':{'persistence':[]},
            'presentation':{'framework':'flutter','screens':[]}}


def provider(text):
    p=Mock()
    p.generate.return_value=LLMResponse(content=text,input_tokens=100,output_tokens=50)
    return p


def test_expansion_seals_derived_repo_without_mutating_source():
    source=genome(); original=deepcopy(source)
    output, usage=expand_repository_contracts(source, provider(json.dumps({'interface':'abstract class TodoRepository {\n Future<int> add(Todo todo);\n}'})))
    assert source == original
    graph=build_graph(output)
    assert len(graph.contracts)==3
    use_case=next(c for c in graph.contracts if c.contract_id=='application.CreateTodo')
    assert {d.contract_id for d in use_case.dependencies}=={'domain.Todo','domain.TodoRepository'}
    assert usage[0].input_tokens==100


def test_invalid_response_does_not_mutate_genome():
    source=genome();original=deepcopy(source)
    with pytest.raises(GenomeError):
        expand_repository_contracts(source,provider('not JSON'))
    assert source==original


def test_no_use_cases_means_no_llm():
    source=genome();source['application']['use_cases']=[]
    p=provider('')
    output,usage=expand_repository_contracts(source,p)
    assert not usage and not p.generate.called
