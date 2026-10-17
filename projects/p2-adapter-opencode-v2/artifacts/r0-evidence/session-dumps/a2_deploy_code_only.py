import os, sys, json, hashlib, pathlib, shutil, tempfile, subprocess, datetime, importlib.util, dataclasses
W=pathlib.Path.cwd(); C=pathlib.Path('E:/opencode_harness_portable'); R=C/'.runs/architecture-A2-release-20261016'; B=R/'backup'
FOUR=['scripts/meta/'+n+'.py' for n in ['damage_basket','sleep_planner','meta_daemon','run_audit_cycle']]
DOC='docs/DAMAGE_BASKET_DURABILITY.md'; A1=['scripts/meta/'+n+'.py' for n in ['durable_json','daemon_safety','trace_store']]
TESTS=['tests/coder/'+n+'.py' for n in ['test_damage_basket_durability','test_basket_snapshot_callers','test_damage_basket_independent','test_trace_store_durability','test_trace_store_durability_independent']]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def snapshot(p):
 if not p.exists(): return {'path':str(p),'exists':False}
 assert not p.is_symlink() and not (p.stat().st_file_attributes & 1024), 'reparse store'
 if p.is_file():
  s=p.stat(); return {'path':str(p),'exists':True,'sha256':sha(p),'size':s.st_size,'mtime_ns':s.st_mtime_ns,'inode':s.st_ino}
 assert p.is_dir()
 return {'path':str(p),'exists':True,'directory':True,'children':[snapshot(x) for x in sorted(p.iterdir())]}
def known_check():
 ps="""$ErrorActionPreference='Stop'; $p=@(Get-CimInstance Win32_Process -Property ProcessId,Name,ExecutablePath,CreationDate -Filter 'ProcessId=9736 OR ProcessId=3336 OR ProcessId=6740' | Select-Object ProcessId,Name,ExecutablePath,CreationDate); $t=@(Get-CimInstance -Namespace Root/Microsoft/Windows/TaskScheduler -ClassName MSFT_ScheduledTask -Property TaskName,State -Filter \"TaskName='HarnessMetaNightly'\" | Select-Object TaskName,State); [pscustomobject]@{observed_utc=[DateTime]::UtcNow.ToString('o');processes=$p;nightly_tasks=$t;query='SUCCESS_RESTRICTED'} | ConvertTo-Json -Depth 5"""
 p=subprocess.run(['powershell','-NoProfile','-Command',ps],capture_output=True,text=True,check=True)
 d=json.loads(p.stdout); assert not d['processes'] and not d['nightly_tasks'], 'known process/task present'; return d
receipt={'actual_agent':'general','role':'deployer','result':'BLOCKED','release_scope':'code-only installation; no production execution or activation','operator_attestation':{'quote':'Подтверждаю, окно удерживаю','authority':'explicit operator attestation supplied by user','coverage':'No other manual/remote/automatic basket writers or new Harness/bootstrap/nightly launches through installation','limitation':'Not independently proven global absence; restricted checks are supplementary'},'created_utc':now(),'unresolved_limits':['TD184 OPEN; no full autonomy','No production activation or loaded-instance certification','A3 races/cross-store recovery/exactly-once deferred','Backups are not permission for data rollback after new writes'],'known_process_task_checks':[]}
changed=[]; originals={}; data_before=None; stores=[]
try:
 spec=importlib.util.spec_from_file_location('a2_guard',W/'scripts/researcher/researcher_core/guard.py'); g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
 inputs=['docs/A2_SAFE_RELEASE_PLAN_2026-10-16.md','light_A2_basket.json','tester_A2_release.json','preflight_A2_writers.json','.runs/architecture-A2-20261016/release_identity_projection.json']
 receipt['input_guard']={}
 for rel in inputs:
  report=g.scan_text((W/rel).read_text(encoding='utf-8-sig'),field=rel,provenance='untrusted',tool='read'); assert report.verdict=='PASS'; receipt['input_guard'][rel]={'stage':'P0','verdict':report.verdict,'raw_sha256':sha(W/rel),'not_combined_protection':True}
 light=json.loads((W/'light_A2_basket.json').read_text(encoding='utf-8-sig'))['sha256_manifest']['after']; pre=json.loads((W/'preflight_A2_writers.json').read_text(encoding='utf-8-sig'))['raw_sha256_comparison']; tester=json.loads((W/'tester_A2_release.json').read_text(encoding='utf-8-sig'))
 assert tester['result']=='PASS' and tester['passed']==69
 for rel in FOUR+[DOC]: assert sha(W/rel)==light[rel], 'source drift: '+rel
 for rel in FOUR: assert sha(C/rel)==pre[rel]['canonical'], 'canonical drift: '+rel
 for rel in A1[:2]: assert sha(C/rel)==light[rel], 'A1 drift'
 receipt['A1_before']={rel:sha(C/rel) for rel in A1}
 assert hashlib.sha256((C/A1[2]).read_bytes().replace(b'\r\n',b'\n')).hexdigest()=='b19ea8b7c2b09bfd1358ec80e0cc29c21ef20ad633327e7ec23a82e70b4c0c35'
 for rel in FOUR+[DOC]+A1:
  p=C/rel
  for parent in [p,*p.parents]:
   if parent.exists(): assert not parent.is_symlink() and not (parent.stat().st_file_attributes & 1024), 'reparse production path'
 receipt['known_process_task_checks'].append(known_check())
 records=[]
 for name,pid in [('code-orchestrator',9736),('research-orchestrator',3336),('writing-orchestrator',6740)]:
  p=C/'.meta_state'/f'{name}_daemon.identity.json'; d=json.loads(p.read_text(encoding='utf-8-sig')); assert d['pid']==pid
  records.append({k:d.get(k) for k in ['pid','script','state_dir','heartbeat']})
 receipt['known_identity_records']=records
 acl=json.loads((R/'backup_acl.json').read_text(encoding='utf-8-sig')); assert acl['inheritance_disabled']; receipt['backup_acl_assurance']=acl
 stores=[C/'.damage_basket']; override=os.environ.get('HARNESS_DAMAGE_BASKET');receipt['existing_override_set']=bool(override)
 if override:
  p=pathlib.Path(override); assert p.is_absolute(),'relative override ambiguous'
  if p not in stores: stores.append(p)
 receipt['store_identification']={'basis':'Static canonical DamageBasket default; MetaDaemon delegates basket_dir=None; canonical nightly does not override basket-dir; existing HARNESS_DAMAGE_BASKET only if set','not_claimed':'No exhaustive remote/config/argument inventory; operator attestation covers other launches'}
 data_before=[snapshot(p) for p in stores];receipt['runtime_before']=data_before
 # Access protection was established and verified before any full store copy.
 data_backups=[]
 for i,p in enumerate(stores):
  if p.exists():
   dest=B/'runtime'/str(i);dest.parent.mkdir(parents=True,exist_ok=True)
   if p.is_dir(): shutil.copytree(p,dest)
   else: shutil.copy2(p,dest)
   def signature(p):
    if p.is_file(): return sha(p)
    return {x.name:signature(x) for x in sorted(p.iterdir())}
   assert signature(p)==signature(dest); data_backups.append({'source':str(p),'backup':str(dest),'verified_full_tree_hashes':True,'metadata':snapshot(dest)})
  else: data_backups.append({'source':str(p),'exists':False,'backup_required':False})
 receipt['data_backup_manifest']=data_backups
 manifest={}
 for rel in FOUR+[DOC]:
  p=C/rel; original=p.read_bytes() if p.exists() else None; originals[rel]=original
  entry={'previously_present':original is not None}
  if original is not None:
   dest=B/'code'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(original);assert sha(dest)==sha(p);entry.update(path=str(dest),sha256=sha(dest))
  manifest[rel]=entry
 receipt['code_backup_manifest']=manifest;write(B/'manifest.json',{'code':manifest,'runtime':data_backups,'acl':acl})
 stage=R/'stage';stage.mkdir(exist_ok=False)
 for rel in FOUR+[DOC]:
  dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((W/rel).read_bytes());assert sha(dest)==light[rel]
  if rel in FOUR: compile(dest.read_bytes(),str(dest),'exec')
 receipt['compiled_without_execution']=FOUR;receipt['staged_hashes']={rel:sha(stage/rel) for rel in FOUR+[DOC]}
 assert [snapshot(p) for p in stores]==data_before
 receipt['known_process_task_checks'].append(known_check())
 for rel in FOUR: assert sha(C/rel)==pre[rel]['canonical']
 write(R/'preinstall_evidence.json',receipt)
 for rel in FOUR+[DOC]:
  assert (C/rel).read_bytes()==originals[rel] if originals[rel] is not None else not (C/rel).exists()
  os.replace(stage/rel,C/rel);changed.append(rel);assert sha(C/rel)==light[rel]
 receipt['installed_hashes']={rel:sha(C/rel) for rel in FOUR+[DOC]}
 receipt['A1_after']={rel:sha(C/rel) for rel in A1};assert receipt['A1_after']==receipt['A1_before']
 receipt['runtime_after_install']=[snapshot(p) for p in stores];assert receipt['runtime_after_install']==data_before
 # Build a new isolated mirror from actual canonical bytes, never from the old staging run.
 temp=pathlib.Path(tempfile.mkdtemp(prefix='A2-canonical-installed-',dir='C:/Temp/opencode'));mirror=temp/'mirror'
 copied={}
 for rel in FOUR+A1:
  dest=mirror/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((C/rel).read_bytes());copied[rel]={'canonical_before':sha(C/rel),'mirror_before':sha(dest)};assert copied[rel]['canonical_before']==copied[rel]['mirror_before']
 for rel in TESTS:
  assert sha(W/rel)==tester['before_after_manifest']['after'][rel], 'test drift'
  dest=mirror/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((W/rel).read_bytes())
 runner=pathlib.Path('C:/Temp/opencode/a2_scoped_runner.py');assert runner.exists()
 env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['A2_FIXTURE_ROOT']=str(mirror);env['A2_FIXTURE_RESULT']=str(temp/'tests.json')
 with (temp/'tests.log').open('w',encoding='utf-8') as log:
  test=subprocess.run([sys.executable,'-B',str(runner)],cwd=temp,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120)
 result=json.loads((temp/'tests.json').read_text(encoding='utf-8'));receipt['tests']=result;receipt['test_evidence_directory']=str(temp)
 for rel in copied:
  copied[rel].update(canonical_after=sha(C/rel),mirror_after=sha(mirror/rel));assert len(set(copied[rel].values()))==1
 receipt['canonical_to_fixture_binding']=copied;receipt['test_mode']='New isolated mirror copied FROM installed canonical; module __file__ proof in tests; AST-only daemon/CLI; NOT live activation'
 assert test.returncode==0 and result['methods']==69 and result['passed']==69 and result['failures']==0 and result['errors']==0 and result['skips']==0, 'scoped tests failed'
 receipt['known_process_task_checks'].append(known_check())
 receipt['runtime_after']=[snapshot(p) for p in stores];assert receipt['runtime_after']==data_before
 receipt['runtime_data_unchanged']=True
 assert {rel:sha(C/rel) for rel in A1}==receipt['A1_before']
 assert all(sha(C/rel)==light[rel] for rel in FOUR+[DOC])
 receipt['result']='DEPLOYED_CODE_ONLY'
except Exception as e:
 receipt['error']={'type':type(e).__name__,'message':str(e)}
 if changed:
  if data_before is not None and [snapshot(p) for p in stores]==data_before:
   try:
    for rel in FOUR+[DOC]:
     if originals[rel] is None:
      if (C/rel).exists(): (C/rel).unlink()
     else:
      dest=R/'rollback'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(originals[rel]);os.replace(dest,C/rel)
    receipt['result']='ROLLED_BACK';receipt['rollback_code_hashes']={rel:sha(C/rel) if (C/rel).exists() else None for rel in FOUR+[DOC]}
   except Exception as r: receipt['rollback_error_type']=type(r).__name__
  else: receipt['rollback_blocked']='Working data changed: no code downgrade or data restore attempted'
finally:
 receipt['finished_utc']=now();receipt['tool_budget']={'maximum':22,'note':'Tool-call count finalized separately in root receipt'}
 write(W/'deployer_A2_basket.json',receipt);write(R/'deployer_A2_basket.json',receipt)
 print(json.dumps({'result':receipt['result'],'receipt':str(W/'deployer_A2_basket.json'),'installed_hashes':receipt.get('installed_hashes'),'error':receipt.get('error'),'tests_methods':receipt.get('tests',{}).get('methods')},ensure_ascii=True))
