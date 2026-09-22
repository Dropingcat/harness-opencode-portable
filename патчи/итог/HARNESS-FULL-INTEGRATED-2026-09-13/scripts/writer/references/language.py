from __future__ import annotations
import re
from typing import Iterable
SCHEMA='language_profile/1.0'
_DE={' der ',' die ',' das ',' und ',' von ',' zur ',' bei ',' für ',' mit ',' wurde ',' werden ',' nitridierung',' ergebnisse',' einleitung'}
_EN={' the ',' and ',' of ',' in ',' to ',' with ',' was ',' were ',' results ',' discussion ',' introduction ',' nitriding '}
_RU={' и ',' в ',' на ',' при ',' для ',' азотир',' результат',' введени',' исследован',' диссертац'}

def detect(text:str)->dict:
    s=' '+re.sub(r'\s+',' ',str(text or '').casefold())+' '
    scores={
        'ru':sum(s.count(x) for x in _RU)+len(re.findall(r'[а-яё]',s))//80,
        'en':sum(s.count(x) for x in _EN),
        'de':sum(s.count(x) for x in _DE),
    }
    ranked=sorted(scores.items(),key=lambda x:(-x[1],x[0])); top,sv=ranked[0]
    if sv<=0:return {'schema':SCHEMA,'language':'unknown','confidence':0.0,'scores':scores}
    second=ranked[1][1]
    lang='mixed' if second>0 and second/sv>=0.65 else top
    conf=round((sv-second)/max(1,sv),4) if lang!='mixed' else round(second/max(1,sv),4)
    return {'schema':SCHEMA,'language':lang,'confidence':conf,'scores':scores}

def detect_fragments(texts:Iterable[str])->dict:
    rows=[detect(x) for x in texts if str(x or '').strip()]
    if not rows:return {'schema':SCHEMA,'language':'unknown','confidence':0.0,'fragments':[]}
    votes={k:0.0 for k in ('ru','en','de','mixed','unknown')}
    for r in rows:votes[r['language']]+=max(.1,float(r['confidence']))
    lang=max(votes,key=votes.get)
    return {'schema':SCHEMA,'language':lang,'confidence':round(votes[lang]/max(.1,sum(votes.values())),4),'fragments':rows}
