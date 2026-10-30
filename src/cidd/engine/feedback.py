"""Deterministic Flutter analyzer diagnostics -> isolated contract feedback.

Offline only: never calls providers, edits generated code or modifies the graph.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

class FeedbackError(ValueError):
    pass

# Flutter output may wrap long diagnostic messages onto additional lines.
_DIAG = re.compile(
    r"^\s*(error|warning|info)\s+-\s+(.*?)\s+-\s+"
    r"(lib[\\/][^\r\n]+?\.dart):(\d+):(\d+)\s+-\s+([a-z][a-z0-9_]*)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_START = re.compile(r"^\s*(?:error|warning|info)\s+-\s+",re.I)

def _diagnostics(stdout: str) -> list[dict]:
    records=[]
    current=[]
    for line in stdout.splitlines():
        if _START.match(line):
            if current:
                records.append(' '.join(x.strip() for x in current))
            current=[line]
        elif current and line.strip() and not re.match(r'^\s*(?:\d+ issues? found|No issues found|Analyzing )',line):
            current.append(line)
        elif current:
            records.append(' '.join(x.strip() for x in current))
            current=[]
    if current:
        records.append(' '.join(x.strip() for x in current))
    result=[]
    for record in records:
        match=_DIAG.match(record)
        if not match:
            raise FeedbackError('Unrecognized Flutter diagnostic: '+record[:240])
        severity,message,path,line,column,code=match.groups()
        result.append(dict(severity=severity.lower(),message=message,path=path.replace('\\','/'),line=int(line),column=int(column),code=code))
    return result

def route_feedback(graph: dict, report: dict, *, max_errors_per_contract: int = 20) -> dict:
    if graph.get('fingerprint') != report.get('graph_fingerprint'):
        raise FeedbackError('Graph fingerprint does not match assembly report')
    analyzer=report.get('analyzer',{})
    if analyzer.get('status') not in ('PASS','FAIL'):
        raise FeedbackError('Analyzer has not completed')
    paths={c['path'].replace('\\','/').lower():c['id'] for c in report.get('contracts',[]) if c.get('status')=='ASSEMBLED' and c.get('path')}
    valid_ids={c['id'] for c in graph.get('contracts',[])}
    if any(cid not in valid_ids for cid in paths.values()):
        raise FeedbackError('Assembly report contains unknown contracts')
    routed={}
    unresolved=[]
    for diag in _diagnostics(analyzer.get('stdout','')):
        cid=paths.get(diag['path'].lower())
        if cid is None:
            if diag['severity']=='error': unresolved.append(diag)
            continue
        if diag['severity']!='error': continue
        routed.setdefault(cid,[]).append(diag)
    if unresolved:
        raise FeedbackError('Unmapped analyzer errors; cannot safely route feedback: '+', '.join(d['path'] for d in unresolved))
    if analyzer['status']=='FAIL' and not routed:
        raise FeedbackError('Analyzer failed without mappable Dart errors; inspect command/stderr')
    contracts=[]
    for contract in graph['contracts']:
        cid=contract['id']
        if cid not in routed: continue
        failures=routed[cid]
        if len(failures)>max_errors_per_contract:
            raise FeedbackError(f'{cid}: too many diagnostics for isolated feedback')
        contracts.append({'id':cid,'diagnostics':failures, 'feedback':
            'Regenerate the complete implementation of '+cid+' from its sealed contract. '
            'Do not patch existing source. Preserve the required public API. '
            'Correct these Dart analyzer errors:\n'+
            '\n'.join(f"- {d['code']} at line {d['line']}, column {d['column']}: {d['message']}" for d in failures)})
    return {'schema':'cidd.contract-feedback/0.1','graph_fingerprint':graph['fingerprint'],
            'affected_contracts':contracts,'affected_count':len(contracts),
            'llm_calls':0}

def main():
    p=argparse.ArgumentParser(description='Route Flutter analyzer errors to contracts without LLM calls')
    p.add_argument('--graph',required=True,type=Path)
    p.add_argument('--report',required=True,type=Path)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    result=route_feedback(json.loads(args.graph.read_text(encoding='utf-8')),
                          json.loads(args.report.read_text(encoding='utf-8')))
    destination=args.output or args.report.parent/'cidd-contract-feedback.json'
    destination.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Affected contracts:',result['affected_count'])
    for item in result['affected_contracts']:
        print('FEEDBACK',item['id'],len(item['diagnostics']),'error(s)')
    print('Feedback:',destination)

if __name__=='__main__': main()
