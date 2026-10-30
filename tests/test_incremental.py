import json
from copy import deepcopy
from unittest.mock import Mock
import pytest

from cidd.contracts.incremental import incremental_expand
from cidd.contracts.materializer import build_graph
from cidd.genome.parser import GenomeError
from cidd.providers.base import LLMResponse


def setup_data():
    genome = {'genome': '0.1', 'project': {'name':'todo','template':'flutter','language':'dart'},
              'domain': {'entities': [{'name':'Todo','fields':[{'name':'id','type':'int','nullable':True}]}]},
              'application': {'use_cases': [
                  {'name':'CreateTodo','input':{'title':'string'},'output':'Todo','rules':['Create a Todo']},
                  {'name':'DeleteTodo','input':{'id':'int'},'output':'bool','rules':['Delete a Todo']} ]},
              'infrastructure': {'persistence': []},
              'presentation': {'framework':'flutter','screens': []}}
    old = deepcopy(genome)
    old['application']['use_cases'].pop()
    old['domain']['entities'].append({'name':'TodoRepository','interface':
        'abstract class TodoRepository {\n  Todo add(Todo todo);\n  Todo? findById(int id);\n  Todo update(Todo todo);\n  List<Todo> getAll();\n}',
        'depends_on':['domain.Todo']})
    old['application']['use_cases'][0]['depends_on']=['domain.Todo','domain.TodoRepository']
    return genome, build_graph(old).to_dict()


def provider(response):
    p=Mock()
    p.generate.return_value=LLMResponse(content=json.dumps(response),input_tokens=11,output_tokens=6)
    return p


def test_preserves_existing_methods_and_adds_new():
    genome, previous=setup_data(); original=deepcopy(genome)
    p=provider({'add_methods':['bool deleteById(int id);']})
    expanded, usage=incremental_expand(genome,p,previous)
    assert genome==original
    iface=expanded['domain']['entities'][-1]['interface']
    for method in ['Todo add(Todo todo);','Todo? findById(int id);','Todo update(Todo todo);','List<Todo> getAll();']:
        assert method in iface
    assert 'bool deleteById(int id);' in iface
    assert len(usage)==1
    graph=build_graph(expanded)
    assert len(graph.contracts)==4
    assert 'new_use_cases' in p.generate.call_args.args[1]


def test_refuses_redefinition():
    genome, previous=setup_data()
    with pytest.raises(GenomeError,match='redefine'):
        incremental_expand(genome,provider({'add_methods':['bool update(Todo todo);']}),previous)


def test_rejects_old_usecase_mutation():
    genome, previous=setup_data()
    genome['application']['use_cases'][0]['rules']=['Changed']
    with pytest.raises(GenomeError,match='existing use case changed'):
        incremental_expand(genome,provider({'add_methods':[]}),previous)


def test_no_new_use_case_does_not_call_model():
    genome, previous=setup_data()
    genome['application']['use_cases'].pop()
    p=provider({'add_methods':[]})
    expanded, usage=incremental_expand(genome,p,previous)
    assert usage==[] and not p.generate.called
    assert 'deleteById' not in expanded['domain']['entities'][-1]['interface']
