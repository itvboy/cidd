from cidd.engine.feedback import route_feedback, FeedbackError
import pytest

def graph():
    return {'fingerprint':'abc','contracts':[{'id':'presentation.TodoView'},{'id':'domain.Todo'}]}

def report(stdout, status='FAIL'):
    return {'graph_fingerprint':'abc','contracts':[{'id':'presentation.TodoView','path':'lib\\presentation\\todo_view.dart','status':'ASSEMBLED'}],
            'analyzer':{'status':status,'stdout':stdout}}

def test_routes_nullable_error_to_one_contract():
    text="  error - The argument type 'int?' can't be assigned to the parameter type 'int'. - lib\\presentation\\todo_view.dart:149:38 - argument_type_not_assignable\n"
    result=route_feedback(graph(),report(text))
    assert result['affected_count']==1
    assert result['affected_contracts'][0]['id']=='presentation.TodoView'
    assert result['affected_contracts'][0]['diagnostics'][0]['code']=='argument_type_not_assignable'
    assert result['llm_calls']==0

def test_ignores_informational_lines():
    text=" info - key could be a super parameter - lib\\presentation\\todo_view.dart:12:9 - use_super_parameters\n"
    assert route_feedback(graph(),report(text,'PASS'))['affected_count']==0

def test_refuses_fingerprint_mismatch():
    bad=report(''); bad['graph_fingerprint']='other'
    with pytest.raises(FeedbackError,match='fingerprint'):route_feedback(graph(),bad)

def test_refuses_unmapped_errors():
    text='error - unknown symbol - lib\\unknown.dart:1:1 - undefined_class'
    with pytest.raises(FeedbackError,match='Unmapped'):route_feedback(graph(),report(text))

def test_multiline_message():
    text=" error - The argument type 'int?' can't be assigned to the parameter type\n         'int'. - lib\\presentation\\todo_view.dart:149:38 - argument_type_not_assignable\n"
    assert route_feedback(graph(),report(text))['affected_count']==1
