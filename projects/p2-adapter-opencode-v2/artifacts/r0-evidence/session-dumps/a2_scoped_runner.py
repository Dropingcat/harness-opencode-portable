import pathlib,sys,os,json,unittest,hashlib
ROOT=pathlib.Path(os.environ['A2_FIXTURE_ROOT']).resolve()
def audit(event,args):
 def allowed(p):
  if isinstance(p,(str,bytes,os.PathLike)):
   p=pathlib.Path(os.fsdecode(p)).absolute()
   if not p.is_relative_to(pathlib.Path('C:/Temp/opencode')): raise PermissionError('fixture write outside approved temp')
 if event=='open':
  p,mode,flags=args
  if (isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)): allowed(p)
 elif event in ['os.remove','os.rmdir','os.mkdir','os.chmod','os.utime']: allowed(args[0])
 elif event in ['os.rename','os.link','os.symlink']: allowed(args[0]);allowed(args[1])
sys.addaudithook(audit)
class Recorded(unittest.TextTestResult):
 def __init__(self,*a,**kw): super().__init__(*a,**kw);self.passed=0;self.subtests=0
 def addSuccess(self,t): super().addSuccess(t);self.passed+=1
 def addSubTest(self,t,s,e): self.subtests+=1;super().addSubTest(t,s,e)
def main():
 summaries=[];paths={}; rows=[]
 for pattern in ['test_damage_basket_durability.py','test_basket_snapshot_callers.py','test_damage_basket_independent.py','test_trace_store_durability*.py']:
  suite=unittest.defaultTestLoader.discover(str(ROOT/'tests/coder'),pattern=pattern)
  for name in ['damage_basket','sleep_planner','durable_json','daemon_safety','trace_store']:
   if name in sys.modules:
    p=pathlib.Path(sys.modules[name].__file__).resolve();assert p==ROOT/'scripts/meta'/f'{name}.py';paths[name]=str(p)
  assert 'meta_daemon' not in sys.modules and 'meta_core' not in sys.modules
  r=unittest.TextTestRunner(verbosity=2,resultclass=Recorded).run(suite)
  summaries.append({'pattern':pattern,'methods':r.testsRun,'passed':r.passed,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'subtests':r.subtests})
  rows.extend({'test':t.id(),'detail':txt} for t,txt in r.failures+r.errors)
 assert 'meta_daemon' not in sys.modules and 'meta_core' not in sys.modules
 out={k:sum(s[k] for s in summaries) for k in ['methods','passed','failures','errors','skips','subtests']};out.update(suites=summaries,module_files=paths,controllers_imported=False,problems=rows,root=str(ROOT),bytecode_disabled=sys.dont_write_bytecode,write_audit_boundary='C:/Temp/opencode; synthetic spawn children use explicit temp fixtures')
 pathlib.Path(os.environ['A2_FIXTURE_RESULT']).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 return int(bool(out['failures']+out['errors']+out['skips']))
if __name__=='__main__': sys.exit(main())
