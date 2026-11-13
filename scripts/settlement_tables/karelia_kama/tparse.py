import re,sys,numpy as np
from PIL import Image
html=open('dl_tarasov/bb.html',encoding='utf-8').read()
pages=re.split(r'<page ',html)[1:]
W=re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')
import html as H
def rules(f):
    im=np.asarray(Image.open(f).convert('L'))<128
    out=[]
    for x in range(im.shape[1]):
        col=im[150:1480,x]; d=np.diff(np.concatenate([[0],col.astype(int),[0]]))
        s=np.where(d==1)[0]; e=np.where(d==-1)[0]
        if len(s) and (e-s).max()>300: out.append(x*72/130)
    # merge adjacent
    m=[]
    for v in out:
        if m and v-m[-1][-1]<2: m[-1].append(v)
        else: m.append([v])
    return [np.mean(g) for g in m]
for pi,pg in enumerate(pages):
    pno=18+pi
    words=[(float(a),float(b),float(c),float(d),H.unescape(t)) for a,b,c,d,t in W.findall(pg)]
    rl=rules(f'dl_tarasov/tp-{pno}.png')
    bps=[w for w in words if re.fullmatch(r'\d{3,5}±\d{2,4}',w[4])]
    print('PAGE',pno,'rules',[round(r,1) for r in rl],'nBP',len(bps),'BP y',round(min(w[1] for w in bps)) if bps else None)
import json
allrows=[]
for pi,pg in enumerate(pages):
    pno=18+pi
    words=[(float(a),float(b),float(c),float(d),H.unescape(t)) for a,b,c,d,t in W.findall(pg)]
    rl=rules(f'dl_tarasov/tp-{pno}.png')
    rl=rl[1:]  # skip top edge (header boundary is rl[0]? check)
    def band(x):
        for i in range(len(rl)-1):
            if rl[i]<x<rl[i+1]: return i
        return None
    lines={}
    for w in words:
        if band(w[0]+4) is None: continue
        key=round(w[0])
        k=[kk for kk in lines if abs(kk-w[0])<1.5]
        k=k[0] if k else w[0]
        lines.setdefault(k,[]).append(w)
    def txt(ws): return ' '.join(w[4] for w in sorted(ws,key=lambda w:-w[1]))
    bands={}
    for k in sorted(lines):
        bands.setdefault(band(k+4),[]).append(k)
    for b,ks in sorted(bands.items()):
        site=' '.join(txt([w for w in lines[k] if 670<w[1]<752]) for k in ks).strip()
        mapno=' '.join(txt([w for w in lines[k] if w[1]>=752]) for k in ks).strip()
        typ=' '.join(txt([w for w in lines[k] if 195<w[1]<345]) for k in ks).strip()
        cur=None
        for k in ks:
            L=lines[k]
            bp=[w for w in L if re.fullmatch(r'\d{3,5}±\d{2,4}',w[4])]
            ctx=txt([w for w in L if 392<w[1]<578])
            if bp:
                lab=txt([w for w in L if 575<w[1]<629])
                ref=txt([w for w in L if w[1]<200])
                cal=txt([w for w in L if 345<w[1]<392])
                cur=dict(page=pno,band=b,mapno=mapno,site=site,bp=bp[0][4],lab=lab,ctx=ctx,cal=cal,typ=typ,rtyp=txt([w for w in L if 195<w[1]<345]),ref=ref)
                allrows.append(cur)
            elif cur and cur['band']==b and ctx:
                cur['ctx']+=' '+ctx
json.dump(allrows,open('dl_tarasov/rows.json','w'),ensure_ascii=False,indent=0)
print(len(allrows))
for r in []: print(r['page'],r['band'],r['mapno'],'|',r['site'],'|',r['bp'],r['lab'],'|',r['ctx'],'|',r['typ'][:40])
