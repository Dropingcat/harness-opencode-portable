#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math

def parse_vars(items):
    out={}
    for x in items or []:
        k,v=x.split('=',1); out[k]=float(v)
    return out

def expression(expr,vars):
    import sympy as sp
    symbols={k:sp.Symbol(k) for k in vars}
    e=sp.sympify(expr,locals=symbols)
    val=sp.N(e.subs({symbols[k]:v for k,v in vars.items()}),16)
    return {'expression':str(e),'value':float(val) if val.is_real else str(val)}

def solve(eq,var):
    import sympy as sp
    s=sp.Symbol(var); left,right=(eq.split('=',1)+['0'])[:2] if '=' in eq else (eq,'0')
    sols=sp.solve(sp.Eq(sp.sympify(left),sp.sympify(right)),s)
    return {'equation':eq,'variable':var,'solutions':[str(x) for x in sols]}

def uncertainty(expr,values,unc):
    import sympy as sp
    syms={k:sp.Symbol(k) for k in values}; e=sp.sympify(expr,locals=syms)
    subs={syms[k]:v for k,v in values.items()}
    terms=[]
    for k,u in unc.items():
        d=sp.diff(e,syms[k]); dv=float(sp.N(d.subs(subs))); terms.append({'variable':k,'derivative':dv,'u':u,'variance_term':(dv*u)**2})
    uc=math.sqrt(sum(t['variance_term'] for t in terms)); val=float(sp.N(e.subs(subs)))
    return {'expression':str(e),'value':val,'combined_standard_uncertainty':uc,'terms':terms,'method':'first_order_independent'}

def equivalent(a,b):
    import sympy as sp
    d=sp.simplify(sp.sympify(a)-sp.sympify(b)); return {'a':a,'b':b,'equivalent':d==0,'difference':str(d)}

ATOMIC={'H':1.00794,'He':4.002602,'Li':6.941,'Be':9.012182,'B':10.811,'C':12.0107,'N':14.0067,'O':15.9994,'F':18.9984032,'Ne':20.1797,'Na':22.98976928,'Mg':24.3050,'Al':26.9815386,'Si':28.0855,'P':30.973762,'S':32.065,'Cl':35.453,'Ar':39.948,'K':39.0983,'Ca':40.078,'Ti':47.867,'V':50.9415,'Cr':51.9961,'Mn':54.938045,'Fe':55.845,'Co':58.933195,'Ni':58.6934,'Cu':63.546,'Zn':65.38,'Mo':95.96,'W':183.84,'Pb':207.2}
def molar_mass(formula):
    import re
    toks=re.findall(r'([A-Z][a-z]?)(\d*(?:\.\d+)?)',formula)
    if ''.join(e+n for e,n in toks)!=formula: raise ValueError('formula parser supports simple non-parenthesized formulas only')
    parts=[]; total=0.0
    for el,n in toks:
        if el not in ATOMIC: raise ValueError(f'unknown element:{el}')
        c=float(n) if n else 1.0; m=ATOMIC[el]*c; total+=m; parts.append({'element':el,'count':c,'mass':m})
    return {'formula':formula,'molar_mass_g_mol':total,'parts':parts,'table':'embedded_common_elements'}

def main()->int:
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='mode',required=True)
    p=sub.add_parser('expr'); p.add_argument('expression'); p.add_argument('--var',action='append',default=[])
    p=sub.add_parser('solve'); p.add_argument('equation'); p.add_argument('--for',dest='var',required=True)
    p=sub.add_parser('uncertainty'); p.add_argument('expression'); p.add_argument('--value',action='append',default=[]); p.add_argument('--u',action='append',default=[])
    p=sub.add_parser('equivalent'); p.add_argument('a'); p.add_argument('b')
    p=sub.add_parser('molar-mass'); p.add_argument('formula')
    a=ap.parse_args()
    try:
        if a.mode=='expr': r=expression(a.expression,parse_vars(a.var))
        elif a.mode=='solve': r=solve(a.equation,a.var)
        elif a.mode=='uncertainty': r=uncertainty(a.expression,parse_vars(a.value),parse_vars(a.u))
        elif a.mode=='equivalent': r=equivalent(a.a,a.b)
        else: r=molar_mass(a.formula)
        print(json.dumps({'ok':True,'schema':'science_computation.v1','mode':a.mode,'result':r},ensure_ascii=False,indent=2)); return 0
    except Exception as e:
        print(json.dumps({'ok':False,'schema':'science_computation.v1','mode':a.mode,'error':f'{e.__class__.__name__}: {e}'},ensure_ascii=False,indent=2)); return 2
if __name__=='__main__': raise SystemExit(main())
