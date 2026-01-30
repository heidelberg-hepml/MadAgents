#!/usr/bin/env python3
import argparse,sys,os,math,numpy as np,uproot
def _k(t,*ks):
    for k in ks:
        if k in t.keys(): return k
    return None
def _arr(t,k):
    return t[k].array(library="ak")
def _pad(a,n):
    import awkward as ak
    return ak.to_numpy(ak.fill_none(ak.pad_none(a,n,clip=True),0))
def _scal(a):
    import awkward as ak
    x=ak.to_numpy(ak.fill_none(a,0))
    if x.ndim==0: x=np.array([x])
    return x
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--in-root",required=True)
    p.add_argument("--out-npz",required=True)
    p.add_argument("--max-jets",type=int,default=10)
    p.add_argument("--max-ele",type=int,default=4)
    p.add_argument("--max-mu",type=int,default=4)
    p.add_argument("--max-events",type=int,default=0)
    a=p.parse_args()
    f=uproot.open(a.in_root)
    if "Delphes" not in f: raise RuntimeError("Missing Delphes tree")
    t=f["Delphes"]
    jk=_k(t,"Jet/Jet.PT","Jet.PT");mk=_k(t,"MissingET/MissingET.MET","MissingET.MET")
    if not jk or not mk:
        ks=list(t.keys())
        raise RuntimeError("Missing key branches. Need Jet.PT (or Jet/Jet.PT) and MissingET.MET (or MissingET/MissingET.MET). Found: "+",".join(ks[:200]))
    jeta=_k(t,"Jet/Jet.Eta","Jet.Eta");jphi=_k(t,"Jet/Jet.Phi","Jet.Phi");jm=_k(t,"Jet/Jet.Mass","Jet.Mass");jb=_k(t,"Jet/Jet.BTag","Jet.BTag","Jet/Jet.BTag")
    ep=_k(t,"Electron/Electron.PT","Electron.PT");eeta=_k(t,"Electron/Electron.Eta","Electron.Eta");ephi=_k(t,"Electron/Electron.Phi","Electron.Phi");eq=_k(t,"Electron/Electron.Charge","Electron.Charge")
    mp=_k(t,"Muon/Muon.PT","Muon.PT");meta=_k(t,"Muon/Muon.Eta","Muon.Eta");mphi=_k(t,"Muon/Muon.Phi","Muon.Phi");mq=_k(t,"Muon/Muon.Charge","Muon.Charge")
    metphi=_k(t,"MissingET/MissingET.Phi","MissingET.Phi")
    wkey=_k(t,"Event/Event.Weight","Event.Weight")
    xskey=_k(t,"Event/Event.CrossSection","Event.CrossSection")
    n=a.max_events if a.max_events>0 else None
    import awkward as ak
    jpt=_arr(t,jk);jetaA=_arr(t,jeta) if jeta else None;jphiA=_arr(t,jphi) if jphi else None;jmA=_arr(t,jm) if jm else None;jbA=_arr(t,jb) if jb else None
    met=_arr(t,mk);metphiA=_arr(t,metphi) if metphi else None
    ept=_arr(t,ep) if ep else ak.Array([[] for _ in range(len(met))]);eetaA=_arr(t,eeta) if eeta else ak.Array([[] for _ in range(len(met))]);ephiA=_arr(t,ephi) if ephi else ak.Array([[] for _ in range(len(met))]);eqA=_arr(t,eq) if eq else ak.Array([[] for _ in range(len(met))])
    mpt=_arr(t,mp) if mp else ak.Array([[] for _ in range(len(met))]);metaA=_arr(t,meta) if meta else ak.Array([[] for _ in range(len(met))]);mphiA=_arr(t,mphi) if mphi else ak.Array([[] for _ in range(len(met))]);mqA=_arr(t,mq) if mq else ak.Array([[] for _ in range(len(met))])
    w=_arr(t,wkey) if wkey else ak.Array([1.0 for _ in range(len(met))])
    xs=_arr(t,xskey) if xskey else ak.Array([0.0 for _ in range(len(met))])
    if n is not None:
        jpt=jpt[:n];met=met[:n];w=w[:n];xs=xs[:n]
        if jetaA is not None: jetaA=jetaA[:n]
        if jphiA is not None: jphiA=jphiA[:n]
        if jmA is not None: jmA=jmA[:n]
        if jbA is not None: jbA=jbA[:n]
        if metphiA is not None: metphiA=metphiA[:n]
        ept=ept[:n];eetaA=eetaA[:n];ephiA=ephiA[:n];eqA=eqA[:n]
        mpt=mpt[:n];metaA=metaA[:n];mphiA=mphiA[:n];mqA=mqA[:n]
    out={}
    out["event_weight"]=_scal(w)
    out["event_xs_pb"]=_scal(xs)
    out["met"]= _scal(met)
    out["met_phi"]= _scal(metphiA) if metphiA is not None else np.zeros_like(out["met"])
    out["jet_pt"]=_pad(jpt,a.max_jets)
    out["jet_eta"]=_pad(jetaA,a.max_jets) if jetaA is not None else np.zeros_like(out["jet_pt"])
    out["jet_phi"]=_pad(jphiA,a.max_jets) if jphiA is not None else np.zeros_like(out["jet_pt"])
    out["jet_mass"]=_pad(jmA,a.max_jets) if jmA is not None else np.zeros_like(out["jet_pt"])
    out["jet_btag"]=_pad(jbA,a.max_jets) if jbA is not None else np.zeros_like(out["jet_pt"])
    out["ele_pt"]=_pad(ept,a.max_ele);out["ele_eta"]=_pad(eetaA,a.max_ele);out["ele_phi"]=_pad(ephiA,a.max_ele);out["ele_q"]=_pad(eqA,a.max_ele)
    out["mu_pt"]=_pad(mpt,a.max_mu);out["mu_eta"]=_pad(metaA,a.max_mu);out["mu_phi"]=_pad(mphiA,a.max_mu);out["mu_q"]=_pad(mqA,a.max_mu)
    os.makedirs(os.path.dirname(a.out_npz) or ".",exist_ok=True)
    np.savez_compressed(a.out_npz,**out)
if __name__=="__main__": main()
