from pathlib import Path
import json, yaml, hashlib, fitz, re, copy, sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from scripts.writer.planning.object_router import decide
from scripts.writer.references.fragment_graph import build as build_fg
from scripts.writer.references.select import select
from scripts.writer.composition.writing_policy import build as build_policy
from scripts.writer.composition.style_instruction import build as build_style_instruction
from scripts.writer.drafting.request import build as build_request
from scripts.writer.drafting.artifact import build as build_artifact
from scripts.writer.drafting.dom_patch import build_patch, apply as apply_patch
from scripts.writer.provenance.change_ledger import build as build_ledger
from scripts.writer.release.gate import evaluate_release

OUT=ROOT/'e2e_runs'/'chapter_iterative_001'; OUT.mkdir(parents=True,exist_ok=True)
PDF={
 'MEKA':Path('/mnt/data/s.meka_Ph.D_thesis.pdf'),
 'SCH':Path('/mnt/data/Diss_148.pdf'),
 'RAK':Path('/mnt/data/Диссертационная работа Рахадилова Б.К.-разблокирован.pdf'),
 'DEM':Path('/mnt/data/demchenko2011.pdf')}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def ptext(p,page):
 d=fitz.open(p); t=' '.join(d[page-1].get_text('text').split()); d.close(); return t

def frag(fid,rid,sid,p,page,role,kind,lang,excerpt,permissions):
 norm=' '.join(excerpt.split()); words=max(1,len(re.findall(r'\w+',norm,re.U)))
 f={'fragment_id':fid,'reference_id':rid,'source_id':sid,'source_sha256':sha(p),'locator':f'pdf_page:{page}','span':{'coordinate_space':'page_text','start':0,'end':len(norm)},'normalized_text_hash':hashlib.sha256(norm.casefold().encode()).hexdigest(),'section_role':role,'document_kind':kind,'language':lang,'permissions':permissions,'style_features':{'words':words,'citation_density_per_1000':0.0,'hedge_density_per_1000':1000*len(re.findall(r'\b(?:may|might|could|suggest|possible|возможно|вероятно|по-видимому)\b',norm,re.I))/words,'causal_density_per_1000':1000*len(re.findall(r'\b(?:because|therefore|thus|hence|can explain|поскольку|поэтому|обусловлен|приводит)\b',norm,re.I))/words},'excerpt':norm[:1200]}
 try: f['graph_digest']=build_fg(f)['fingerprint']
 except Exception as e: f['graph_digest']={'available':False,'error':str(e)}
 return f

# style references from discussion fragments
meka50=ptext(PDF['MEKA'],50)
sch33=ptext(PDF['SCH'],33)
sch34=ptext(PDF['SCH'],34)
style_frags=[
 frag('RF-MEKA-50','REF-MEKA','S-MEKA',PDF['MEKA'],50,'discussion','dissertation','en',meka50[:1100],{'style':True,'evidence':False}),
 frag('RF-SCH-33','REF-SCH','S-SCH',PDF['SCH'],33,'discussion','dissertation','en',sch33[:1100],{'style':True,'evidence':False}),
 frag('RF-SCH-34','REF-SCH','S-SCH',PDF['SCH'],34,'discussion','dissertation','en',sch34[:1100],{'style':True,'evidence':False}),
]
# target is Russian chapter: intentionally language mismatch means style selection should degrade; add Russian style from Rakhadilov p87 as fallback
rak87=ptext(PDF['RAK'],87)
style_frags.append(frag('RF-RAK-87','REF-RAK','S-RAK-87',PDF['RAK'],87,'discussion','dissertation','ru',rak87[:1100],{'style':True,'evidence':True}))

# evidence source snippets
rak83=ptext(PDF['RAK'],83); rak85=ptext(PDF['RAK'],85); rak86=ptext(PDF['RAK'],86); dem1=ptext(PDF['DEM'],1); dem2=ptext(PDF['DEM'],2); sch34e=ptext(PDF['SCH'],34)
sources=[
 {'id':'S-RAK-83','sha256':sha(PDF['RAK']),'text':'Содержание азота в поверхности стали Р6М5 достигает до 7 % (в весовых %). После азотирования наблюдается уширение, снижение интенсивности и сдвиг линии (110) α-фазы к меньшим углам; автор связывает это с образованием твердого раствора азота в железе.'},
 {'id':'S-RAK-85','sha256':sha(PDF['RAK']),'text':'После азотирования на дифрактограммах Р9 и Р18 обнаружены линии Fe4N. Содержание γ′-Fe4N: Р9 5,5 %, Р6М5 3,9 %, Р18 3,7 %.'},
 {'id':'S-RAK-87','sha256':sha(PDF['RAK']),'text':'SEM выявляет мелкодисперсные нитриды легирующих элементов, однако XRD не выявил эти фазы; в тексте это связывается с низкой концентрацией и малым размером и предлагается TEM.'},
 {'id':'S-DEM-1','sha256':sha(PDF['DEM']),'text':'Предварительная пластическая деформация 3–50 %; азотирование при 853 K. Ускоренное образование ε- и γ′-фаз отмечено в интервалах 3–8 % и 20–30 %.'},
 {'id':'S-DEM-2','sha256':sha(PDF['DEM']),'text':'Толщина фазовых слоев меняется немонотонно; максимумы около 3–5 % и 20–25 % деформации. Микротвердость заметно возрастает в интервалах 3–8 % и 20–30 %.'},
 {'id':'S-SCH-34','sha256':sha(PDF['SCH']),'text':'Для Fe-Cr при 700 °C наблюдались четкие отражения CrN, отсутствовавшие при 450 и 580 °C; автор связывает это с укрупнением выделений.'}
]

claims=[
 {'id':'C-001','text':'После азотирования стали Р6М5 линия (110) α-фазы уширяется, ее интенсивность снижается и максимум смещается к меньшим углам; в исходной работе это интерпретируется как признак образования твердого раствора азота в железе.','kind':'factual','scope':'Р6М5; электролитно-плазменное азотирование','modality':'qualified','causal_level':'interpretive','required_qualifiers':['интерпретируется'],'evidence':[{'source_id':'S-RAK-83','span':'pdf_page:83'}]},
 {'id':'C-002','text':'После азотирования в исследованных быстрорежущих сталях обнаруживается γ′-Fe4N.','kind':'factual','scope':'Р6М5, Р9, Р18','modality':'assertive','causal_level':'none','evidence':[{'source_id':'S-RAK-85','span':'pdf_page:85'}]},
 {'id':'C-003','text':'Содержание γ′-Fe4N после азотирования составляет 5,5 % для Р9, 3,9 % для Р6М5 и 3,7 % для Р18.','kind':'factual','scope':'Р6М5, Р9, Р18','modality':'assertive','causal_level':'none','evidence':[{'source_id':'S-RAK-85','span':'pdf_page:85-86'}]},
 {'id':'C-004','text':'Нитриды легирующих элементов, наблюдавшиеся методом SEM, не были выявлены XRD; автор работы допускает, что причиной могут быть их малая концентрация и размер.','kind':'factual','scope':'быстрорежущие стали после азотирования','modality':'qualified','causal_level':'hypothesis','required_qualifiers':['допускает'],'evidence':[{'source_id':'S-RAK-87','span':'pdf_page:87'}]},
 {'id':'C-005','text':'В предварительно деформированном α-Fe при азотировании 853 K толщина нитридных слоев изменяется немонотонно, с максимумами при 3–5 % и 20–25 % деформации.','kind':'factual','scope':'α-Fe; 853 K','modality':'assertive','causal_level':'none','evidence':[{'source_id':'S-DEM-2','span':'pdf_page:2'}]},
 {'id':'C-006','text':'В системе Fe-Cr четкие отражения CrN наблюдались после азотирования при 700 °C, но не при 450 и 580 °C; это сопоставление показывает, что отсутствие линии XRD само по себе не доказывает отсутствие мелкодисперсной фазы.','kind':'factual','scope':'сравнительный пример Fe-Cr','modality':'qualified','causal_level':'interpretive','required_qualifiers':['сопоставление'],'evidence':[{'source_id':'S-SCH-34','span':'pdf_page:34'}]},
]

obj=decide('Раздел диссертации: фазовые превращения и обсуждение результатов азотирования',explicit_kind='chapter')
# target graph from rough paragraph
rough='После азотирования структура меняется. На дифрактограммах появляются новые фазы. Необходимо обсудить результаты и сопоставить их с литературой.'
targetf=frag('TARGET','TARGET','TARGET',PDF['RAK'],83,'discussion','chapter','ru',rough,{'style':True,'evidence':False})
target_graph=targetf.get('graph_digest') or {}
target_style=targetf.get('style_features') or {}
style_sel=select(style_frags,role='style',target_kind='dissertation',language='ru',section_role='discussion',target_text=rough,target_style=target_style,target_graph=target_graph,limit=3,max_per_reference=2)
# if only self-like Russian style survives, keep it; this is an intended diagnostic
# evidence fragments
E=[]
for i,s in enumerate(sources,1):
    E.append({'fragment_id':f'EV-{i:02d}','reference_id':s['id'],'source_id':s['id'],'source_sha256':s['sha256'],'locator':next((e['span'] for c in claims for e in c['evidence'] if e['source_id']==s['id']),'unknown'),'span':{'coordinate_space':'source_text','start':0,'end':len(s['text'])},'normalized_text_hash':hashlib.sha256(s['text'].casefold().encode()).hexdigest(),'section_role':'results','document_kind':'article' if s['id'].startswith('S-DEM') else 'dissertation','language':'ru','permissions':{'style':False,'evidence':True},'style_features':{},'graph_digest':{},'excerpt':s['text']})
evidence_sel=select(E,role='evidence',target_text='азотирование XRD Fe4N деформация нитридные фазы',limit=6,max_per_reference=2)
policy=build_policy(obj,'discussion',style_sel,target_language='ru')
fmap={f['fragment_id']:f for f in style_frags}
style_instr=build_style_instruction(style_sel,fmap,policy)

# initial DOM with one section and six claims, but rough paragraph realizes only first two without citations
base={'product':{'id':'PROD-E2E','kind':'dissertation'},'claims':copy.deepcopy(claims),'sources':copy.deepcopy(sources),'graphs':[],'uncertainty':{},'structure':{'chapters':[{'id':'CH-4','title':'Фазовые превращения при азотировании','sections':[{'id':'SEC-4.3','role':'discussion','title':'Фазовые превращения и обсуждение','paragraphs':[{'id':'PAR-1','text':rough,'claims':['C-001','C-002'],'evidence_refs':[]}]}]}]}}

def save_json(name,obj): (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
def save_dom(name,dom): (OUT/name).write_text(yaml.safe_dump(dom,allow_unicode=True,sort_keys=False),encoding='utf8')
def paragraph_text(dom):
 ps=dom['structure']['chapters'][0]['sections'][0]['paragraphs']; return '\n\n'.join(p['text'] for p in ps)
def release(version,dom):
 dp=OUT/f'{version}_dom.yaml'; tp=OUT/f'{version}_text.md'; save_dom(dp.name,dom); tp.write_text(paragraph_text(dom),encoding='utf8')
 try:r=evaluate_release(dp,tp,evidence_policy='strict',strict_trace=True,fail_on='high')
 except Exception as e:r={'verdict':'ERROR','error':f'{type(e).__name__}: {e}'}
 save_json(f'{version}_release.json',r); return r

def iterate(version,dom,paragraphs,claim_subset,notes):
 req=build_request(obj,style_sel,evidence_sel,claim_subset,'discussion',notes,policy,style_instr); save_json(f'{version}_request.json',req)
 art=build_artifact(req,paragraphs); save_json(f'{version}_draft_artifact.json',art)
 patch=build_patch(dom,art); save_json(f'{version}_patch.json',patch)
 ap=apply_patch(dom,patch); save_json(f'{version}_patch_apply.json',{k:v for k,v in ap.items() if k!='dom'})
 newdom=ap.get('dom',dom)
 ledger=build_ledger(dom,newdom); save_json(f'{version}_ledger.json',ledger)
 rel=release(version,newdom)
 return newdom,art,ledger,rel

save_json('object_decision.json',obj); save_json('style_fragments.json',{'fragments':style_frags}); save_json('style_selection.json',style_sel); save_json('evidence_selection.json',evidence_sel); save_json('writing_policy.json',policy); save_json('style_instruction.json',style_instr); save_dom('v0_dom.yaml',base); release('v0',base)

# V1 factual coherent draft, only C1-C2-C4
v1p=[{'target_paragraph_id':'PAR-1','text':'Рентгеноструктурные данные показывают, что после азотирования состояние α-фазы быстрорежущей стали изменяется: для Р6М5 отмечены уширение и снижение интенсивности линии (110), а также ее смещение к меньшим углам. В исходной работе это интерпретируется как признак образования твердого раствора азота в железе [C-001] [S-RAK-83]. Одновременно после азотирования для исследованных быстрорежущих сталей фиксируется γ′-Fe4N [C-002] [S-RAK-85]. Нитриды легирующих элементов, наблюдаемые методом SEM, при этом не выявлены XRD; автор допускает, что причиной могут быть их малая концентрация и размер [C-004] [S-RAK-87].','realizes_claims':['C-001','C-002','C-004'],'evidence_refs':['S-RAK-83','S-RAK-85','S-RAK-87'],'style_instruction_id':style_instr['style_instruction_id']}]
v1,_,_,_=iterate('v1',base,v1p,[claims[0],claims[1],claims[3]],'Собрать первый фактологический абзац без новых выводов.')

# V2 add numeric paragraph and external comparison
v2p=[{'target_paragraph_id':'PAR-1','text':v1p[0]['text'],'realizes_claims':['C-001','C-002','C-004'],'evidence_refs':['S-RAK-83','S-RAK-85','S-RAK-87'],'style_instruction_id':style_instr['style_instruction_id']},
 {'text':'Количественный фазовый анализ дает различное содержание γ′-Fe4N: 5,5 % для Р9, 3,9 % для Р6М5 и 3,7 % для Р18 [C-003] [S-RAK-85]. В качестве внешнего сопоставления можно отметить, что в предварительно деформированном α-Fe при азотировании 853 K толщина нитридных слоев изменялась немонотонно, с максимумами при 3–5 % и 20–25 % деформации [C-005] [S-DEM-2]. Эти данные относятся к другой системе и используются только как сравнительный пример чувствительности фазообразования к состоянию матрицы.','realizes_claims':['C-003','C-005'],'evidence_refs':['S-RAK-85','S-DEM-2'],'style_instruction_id':style_instr['style_instruction_id']}]
v2,_,_,_=iterate('v2',v1,v2p,[claims[0],claims[1],claims[2],claims[3],claims[4]],'Добавить количественные данные и явно ограниченное внешнее сопоставление.')

# V3 style pass: observation -> comparison -> interpretation -> limitation
v3p=[{'target_paragraph_id':'PAR-1','text':'После азотирования изменения α-фазы проявляются непосредственно в дифракционной картине: для Р6М5 линия (110) уширяется, ее интенсивность уменьшается, а максимум смещается к меньшим углам. В исходной работе совокупность этих признаков интерпретируется как образование твердого раствора азота в железе [C-001] [S-RAK-83]. На том же уровне анализа в исследованных быстрорежущих сталях фиксируется γ′-Fe4N [C-002] [S-RAK-85]. При этом SEM выявляет мелкодисперсные нитриды легирующих элементов, которые не обнаруживаются методом XRD; автор допускает, что такое расхождение связано с их малой концентрацией и размером [C-004] [S-RAK-87]. Следовательно, отрицательный результат фазового XRD в данном случае следует рассматривать с учетом предела обнаружения и дополнять локальными методами анализа.','realizes_claims':['C-001','C-002','C-004'],'evidence_refs':['S-RAK-83','S-RAK-85','S-RAK-87'],'style_instruction_id':style_instr['style_instruction_id']},
 {'target_paragraph_id':'DP-002','text':'Количественный анализ показывает, что содержание γ′-Fe4N после азотирования составляет 5,5 % для Р9, 3,9 % для Р6М5 и 3,7 % для Р18 [C-003] [S-RAK-85]. Для сопоставления, в предварительно деформированном α-Fe при 853 K толщина нитридных слоев изменялась немонотонно и имела максимумы при 3–5 % и 20–25 % деформации [C-005] [S-DEM-2]. Поскольку это другая материал-система и другой режим обработки, такое сопоставление не переносит количественную закономерность на быстрорежущие стали, а лишь показывает, что исходное дефектное состояние матрицы может сопровождаться немонотонным изменением параметров нитридного слоя.','realizes_claims':['C-003','C-005'],'evidence_refs':['S-RAK-85','S-DEM-2'],'style_instruction_id':style_instr['style_instruction_id']}]
v3,_,_,_=iterate('v3',v2,v3p,[claims[0],claims[1],claims[2],claims[3],claims[4]],'Сделать discussion-проход, сохраняя квалификаторы и границы переноса.')

# V4 intentionally overclaim + extra comparison claim C6
v4p=copy.deepcopy(v3p)
v4p[0]['text']=v4p[0]['text'].replace('автор допускает, что такое расхождение связано','это расхождение однозначно вызвано')
v4p[0]['text'] += ' В системе Fe-Cr четкие отражения CrN появлялись при 700 °C, но отсутствовали при 450 и 580 °C; это сопоставление показывает, что отсутствие линии XRD само по себе не доказывает отсутствие мелкодисперсной фазы [C-006] [S-SCH-34].'
v4p[0]['realizes_claims'].append('C-006'); v4p[0]['evidence_refs'].append('S-SCH-34')
v4,_,_,_=iterate('v4',v3,v4p,claims,'Намеренно усилить одну причинную формулировку, чтобы проверить RTT.')

# V5 repair overclaim; preserve C6 qualified comparison
v5p=copy.deepcopy(v4p)
v5p[0]['text']=v5p[0]['text'].replace('это расхождение однозначно вызвано их малой концентрацией и размером','автор допускает, что такое расхождение может быть связано с их малой концентрацией и размером')
v5,_,_,_=iterate('v5',v4,v5p,claims,'Selective repair: вернуть квалификатор и убрать causality upgrade.')

# compact summary
rows=[]
for v in ['v0','v1','v2','v3','v4','v5']:
 r=json.loads((OUT/f'{v}_release.json').read_text(encoding='utf8'))
 rows.append({'version':v,'release':r.get('verdict'),'blockers':r.get('blockers'),'evidence':(((r.get('gates') or {}).get('evidence') or {}).get('verdict')),'trace':(((r.get('gates') or {}).get('traceability') or {}).get('verdict')),'rtt':(((r.get('gates') or {}).get('semantic_roundtrip') or {}).get('verdict'))})
summary={'run_id':'chapter_iterative_001','style_selection':{'status':style_sel.get('status'),'selected':[{'fragment_id':x.get('fragment_id'),'reference_id':x.get('reference_id'),'score':x.get('score')} for x in style_sel.get('selected') or []]},'evidence_selected':[x.get('reference_id') for x in evidence_sel.get('selected') or []],'iterations':rows}
save_json('SUMMARY.json',summary)
print(json.dumps(summary,ensure_ascii=False,indent=2))
