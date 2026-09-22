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


if expected=='tribunal-advocate-draft/1.1':
    if mode=='advocate-hidden':
        hidden=sys.argv[2]
        out={
          'schema':'tribunal-advocate-draft/1.1','outcome':'DEFEND',
          'summary':'Hidden evidence was used.','justification':'Intentional disclosure violation.',
          'cited_evidence_refs':[hidden], 'cited_target_refs':([first_t] if first_t else []),
          'discoveries':[], 'additional_evidence_requests':[],
          'grounding':[{'kind':'DISCLOSED_EVIDENCE','statement':'Illegally cites hidden evidence.','refs':[hidden]}]
        }
    elif mode=='advocate-prior-only':
        out={
          'schema':'tribunal-advocate-draft/1.1','outcome':'DEFEND',
          'summary':'The defense is only a model-prior hypothesis.',
          'justification':'No disclosed evidence directly supports the defense.',
          'cited_evidence_refs':[], 'cited_target_refs':([first_t] if first_t else []),
          'discoveries':[], 'additional_evidence_requests':[],
          'grounding':[{'kind':'MODEL_PRIOR','statement':'This is remembered domain knowledge, not evidence.','refs':[]}]
        }
    else:
        out={
          'schema':'tribunal-advocate-draft/1.1','outcome':'QUALIFY',
          'summary':'The challenged position remains defensible only in a qualified form.',
          'justification':'The disclosed evidence supports a narrower statement but does not eliminate the alternative explanation.',
          'cited_evidence_refs':([first_e] if first_e else []), 'cited_target_refs':([first_t] if first_t else []),
          'discoveries':[], 'additional_evidence_requests':[],
          'grounding':([{'kind':'DISCLOSED_EVIDENCE','statement':'Defense is grounded in disclosed evidence.','refs':[first_e]}] if first_e else [])
        }
    print(json.dumps(out,ensure_ascii=False)); raise SystemExit(0)

if expected=='tribunal-question-draft/1.0':
    purpose=control.get('purpose') or 'DIRECT_QUESTION'
    q='Which disclosed observation would discriminate the competing explanation?'
    if purpose=='QUESTION_ON_ANSWER':
        q='Which disclosed measurement closes the newly admitted issue in the previous answer?'
    print(json.dumps({'schema':'tribunal-question-draft/1.0','question':q},ensure_ascii=False))
    raise SystemExit(0)

if expected not in {'tribunal-answer-draft/1.0','tribunal-answer-draft/1.1'}:
    print(json.dumps({'schema':'unknown'},ensure_ascii=False)); raise SystemExit(0)

if mode=='hidden-answer':
    hidden=sys.argv[2]
    print(json.dumps({
        'schema':'tribunal-answer-draft/1.1','position':'QUALIFY',
        'summary':'Hidden sibling evidence was used.','justification':'This intentionally violates disclosure.',
        'cited_evidence_refs':[hidden], 'cited_target_refs':([first_t] if first_t else []),
        'discoveries':[], 'additional_evidence_requests':[],
        'grounding':[{'kind':'DISCLOSED_TARGET','statement':'Uses the disclosed target only.','refs':([first_t] if first_t else [])}]
    },ensure_ascii=False)); raise SystemExit(0)

purpose=control.get('purpose') or 'DIRECT_QUESTION'
if mode=='answer-prior-only':
    out={
      'schema':'tribunal-answer-draft/1.1','position':'QUALIFY',
      'summary':'A remembered domain explanation is plausible but not evidenced here.',
      'justification':'This answer intentionally relies on model prior rather than disclosed evidence.',
      'cited_evidence_refs':[], 'cited_target_refs':([first_t] if first_t else []),
      'discoveries':[], 'additional_evidence_requests':[],
      'grounding':[{'kind':'MODEL_PRIOR','statement':'Plausible domain knowledge recalled by the model, not a cited source.','refs':[]}]
    }
    print(json.dumps(out,ensure_ascii=False)); raise SystemExit(0)
if purpose=='QUESTION_ON_ANSWER':
    out={
      'schema':'tribunal-answer-draft/1.1','position':'OPEN',
      'summary':'The disclosed material does not close the issue without a discriminating measurement.',
      'justification':'The bounded evidence contains no independent stress-sensitive control that resolves the new issue.',
      'cited_evidence_refs':([first_e] if first_e else []),
      'cited_target_refs':([first_t] if first_t else []),
      'discoveries':[],
      'grounding':([{'kind':'DISCLOSED_EVIDENCE','statement':'Uses disclosed evidence.','refs':[first_e]}] if first_e else []),
      'additional_evidence_requests':[{
          'question':'Obtain a discriminating measurement or independent composition evidence.',
          'reason':'The current bounded evidence cannot close the issue.',
          'target_refs':([first_t] if first_t else []),
          'requested_evidence_kinds':['stress-sensitive XRD','independent composition evidence']
      }]
    }
else:
    out={
      'schema':'tribunal-answer-draft/1.1','position':'QUALIFY',
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
      'grounding':([{'kind':'DISCLOSED_EVIDENCE','statement':'Uses disclosed evidence.','refs':[first_e]}] if first_e else []),
      'additional_evidence_requests':[]
    }
print(json.dumps(out,ensure_ascii=False))
