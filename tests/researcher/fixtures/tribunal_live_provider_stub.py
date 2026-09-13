#!/usr/bin/env python3
from __future__ import annotations
import json, sys, time

mode=sys.argv[1] if len(sys.argv)>1 else 'default'
if mode=='sleep':
    time.sleep(2.0)
    print('{}')
    raise SystemExit(0)
if mode=='invalid-json':
    print('not-json')
    raise SystemExit(0)

env=json.load(sys.stdin)
expected=env.get('expected_output_schema')
control=env.get('control_contract') or {}
visible_evidence=list(env.get('visible_evidence_refs') or [])
visible_targets=list(env.get('visible_target_refs') or [])
first_e=visible_evidence[0] if visible_evidence else None
first_t=visible_targets[0] if visible_targets else None
question_turn_id=env.get('question_turn_id')
grounding=[]
if first_e:
    grounding.append({'kind':'DISCLOSED_EVIDENCE','statement':'Uses disclosed evidence.','refs':[first_e]})
if question_turn_id:
    grounding.append({'kind':'PRIOR_TURN','statement':'Answers the materialized question.','refs':[question_turn_id]})

if expected=='tribunal-question-draft/1.0':
    purpose=control.get('purpose') or 'DIRECT_QUESTION'
    q='Which disclosed observation would discriminate the competing explanation?'
    if purpose=='QUESTION_ON_ANSWER':
        q='Which disclosed measurement closes the newly admitted issue in the previous answer?'
    print(json.dumps({'schema':'tribunal-question-draft/1.0','question':q},ensure_ascii=False))
    raise SystemExit(0)

if expected not in {'tribunal-answer-draft/1.0', 'tribunal-answer-draft/1.1'}:
    print(json.dumps({'schema':'unknown'},ensure_ascii=False)); raise SystemExit(0)

if mode=='hidden-answer':
    hidden=sys.argv[2]
    print(json.dumps({
        'schema':expected,'position':'QUALIFY',
        'summary':'Hidden sibling evidence was used.','justification':'This intentionally violates disclosure.',
        'cited_evidence_refs':[hidden], 'cited_target_refs':([first_t] if first_t else []),
        'discoveries':[], 'additional_evidence_requests':[],
        'grounding':[{'kind':'DISCLOSED_EVIDENCE','statement':'Uses hidden evidence.','refs':[hidden]}]
    },ensure_ascii=False)); raise SystemExit(0)

purpose=control.get('purpose') or 'DIRECT_QUESTION'
if purpose=='QUESTION_ON_ANSWER':
    out={
      'schema':expected,'position':'OPEN',
      'summary':'The disclosed material does not close the issue without a discriminating measurement.',
      'justification':'The bounded evidence contains no independent stress-sensitive control that resolves the new issue.',
      'cited_evidence_refs':([first_e] if first_e else []),
      'cited_target_refs':([first_t] if first_t else []),
      'discoveries':[],
      'additional_evidence_requests':[{
          'question':'Obtain a discriminating measurement or independent composition evidence.',
          'reason':'The current bounded evidence cannot close the issue.',
          'target_refs':([first_t] if first_t else []),
          'requested_evidence_kinds':['stress-sensitive XRD','independent composition evidence']
      }],
      'grounding':grounding
    }
else:
    out={
      'schema':expected,'position':'QUALIFY',
      'summary':'The interpretation remains qualified because an alternative explanation is not excluded.',
      'justification':'The disclosed evidence does not independently test the key assumption.',
      'cited_evidence_refs':([first_e] if first_e else []),
      'cited_target_refs':([first_t] if first_t else []),
      'discoveries':[{
          'kind':'ASSUMPTION_ISSUE',
          'statement':'The interpretation assumes the alternative contribution is negligible.',
          'target_refs':([first_t] if first_t else []),
          'evidence_refs':([first_e] if first_e else []),
          'blocking':False
      }],
      'additional_evidence_requests':[],
      'grounding':grounding
    }
print(json.dumps(out,ensure_ascii=False))
