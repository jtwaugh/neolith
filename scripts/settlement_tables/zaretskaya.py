import csv
OUT='./zaretskaya.csv'
R05="Zaretskaya, N.E., Zhilin, M.G., Karmanov, V.N. & Uspenskaya, O.N. 2005, Radiocarbon dating of wetland Meso-Neolithic archaeological sites within the Upper Volga and Middle Vychegda, Geochronometria 24:117-131, http://www.geochronometria.pl/pdf/geo_24/Geo24_16.pdf"
R12="Zaretskaya, N.E., Hartz, S., Terberger, T., Savchenko, S.N. & Zhilin, M.G. 2012, Radiocarbon chronology of the Shigir and Gorbunovo archaeological bog sites, Middle Urals, Russia, Radiocarbon 54(3-4):783-794, https://doi.org/10.1017/S0033822200047433"
S05="Zaretskaya et al. 2005"; S12="Zaretskaya et al. 2012"
SITES={
 'Ivanovskoe-7':(39.19,56.93,'peat-bog settlement',"approximate: paper text p.117 '30 km northeastward from Pereslavl'-Zalesskiy' (Pereslavl 38.85E 56.74N, offset 30 km NE), about +-10 km"),
 'Stanovoe-4':(40.43,57.31,'peat-bog settlement',"approximate: paper text p.118 'halfway between Yaroslavl' and Ivanovo', placed at the midpoint of the two city centres, about +-20 km"),
 'Sakhtysh-14':(40.45,56.78,'peat-bog settlement',"approximate: paper text p.118 Sakhtysh peat bog 'ca 45 km southwestward from Ivanovo'; placed at the Sakhtysh 2a point of Dolbunova et al. 2023 SI_ORA (same bog), about +-3 km"),
 'Sakhtysh-2a':(40.45,56.78,'peat-bog settlement',"approximate: Dolbunova et al. 2023 SI_ORA site table 'Sakhtysh 2a' (40.45, 56.78), consistent with paper's 'ca 45 km SW of Ivanovo'; about +-2 km"),
 'Pezmog-4':(51.85,61.8,'oxbow settlement',"approximate: Dolbunova et al. 2023 SI_ORA site table 'Pezmog IV' (51.85, 61.8), consistent with paper's 'right bank of the Vychegda, 55 km eastward of Syktyvkar'; about +-3 km"),
 'Varga-2':(60.1407,57.3809,'peat-bog settlement',"approximate: paper says western part of the Shigir peat bog (Fig. 1B), ~90 km from Ekaterinburg; placed at Wikipedia 'Shigir Idol' page coordinate for the Shigir bog, about +-5 km"),
 'Anin Ostrov':(60.1407,57.3809,'peat-bog site',"approximate: paper says core near Anin Ostrov site ~1 km from Varga-2 in the Shigir bog; placed at Wikipedia 'Shigir Idol' page coordinate for the Shigir bog, about +-5 km"),
 'Beregovaya-2':(59.907,57.885,'peat-bog settlement',"approximate: paper p.787 'rocky cape of the northeastern part of the Gorbunovo peat bog, 5 km southwest from the city of Nizhniy Tagil'; offset 5 km SW from Wikipedia Nizhny Tagil (59.967E 57.917N), about +-3 km"),
}
rows=[]
def add(lab,bp,sd,site,period,mat,page,paper):
    lon,lat,typ,prec=SITES[site]
    rows.append(dict(labnr=lab,bp=bp,std=sd,lon=lon,lat=lat,site=site,type=typ,period=period,material=mat,approximate='true',precision=prec,
      source=S05 if paper==5 else S12,page=page,refs=R05 if paper==5 else R12))
two=' (one of two dates on this sample, two-alkaline extraction)'
# ---- 2005 ----
P3='p. 125, table 3'; P4='p. 125, table 4'; P5='p. 127, table 5'; P6='p. 127, table 6'; P7='p. 127, table 7'
st='Stanovoe-4'; iv='Ivanovskoe-7'; s14='Sakhtysh-14'; s2='Sakhtysh-2a'; pz='Pezmog-4'
e=[ # lab,bp,sd,site,period,material,page,twoflag
 ('GIN-10112',10300,70,st,'Earliest Butovo Mesolithic, layer IV','silt',P3,1),
 ('GIN-10126',9970,50,st,'Earliest Butovo Mesolithic, layer IV','gyttja',P3,1),
 ('GIN-10126',9940,500,st,'Earliest Butovo Mesolithic, layer IV','gyttja',P3,1),
 ('GIN-10127',10060,120,st,'Earliest Butovo Mesolithic, layer IV','gyttja',P3,1),
 ('GIN-10127',10040,90,st,'Earliest Butovo Mesolithic, layer IV','gyttja',P3,1),
 ('GIN-10128',9680,40,st,'Earliest Butovo Mesolithic, layer IV (wood in sand above the layer; upper boundary)','wood',P3,0),
 ('GIN-8374',9620,50,st,'Ienevo Mesolithic, layer IIIa','wood (stick)',P3,0),
 ('GIN-8376',9590,40,st,'Ienevo Mesolithic, layer IIIa','wood (stick)',P3,0),
 ('GIN-8377',9620,60,st,'Ienevo Mesolithic, layer IIIa','wood (stick)',P3,0),
 ('GIN-10125',9560,40,st,'Ienevo Mesolithic, layer IIIa (overlying gyttja)','gyttja',P3,1),
 ('GIN-10111',9560,50,st,'Ienevo Mesolithic, layer IIIa (overlying deposit)','silt',P3,1),
 ('GIN-9516',9640,60,iv,'Early Butovo Mesolithic, layer IV','wood',P3,0),
 ('GIN-9520',9650,110,iv,'Early Butovo Mesolithic, layer IV','bone',P3,0),
 ('GIN-9385',9500,100,iv,'Early Butovo Mesolithic, layer IV','gyttja',P3,0),
 ('GIN-9517',9500,110,iv,'Early Butovo Mesolithic, layer IV','wood',P3,0),
 ('GIN-9367',9690,120,iv,'Early Butovo Mesolithic, layer IV','gyttja',P3,0),
 ('GIN-11177',9390,60,s14,'Early Butovo Mesolithic, layer IV','gyttja',P3,1),
 ('GIN-11179',9350,40,s14,'Early Butovo Mesolithic, layer IV','bone',P3,0),
 ('GIN-11609',9550,40,s14,'Early Butovo Mesolithic, layer IV','gyttja',P3,0),
 ('GIN-11608',9500,60,s14,'Early Butovo Mesolithic, layer IV','gyttja',P3,0),
 ('GIN-11615',9450,60,s14,'Early Butovo Mesolithic, layer IV','wood',P3,0),
 ('GIN-11616',9550,60,s14,'Early Butovo Mesolithic, layer IV','wood (reworked)',P3,0),
 ('GIN-11621',9420,40,s14,'Early Butovo Mesolithic, layer IV','wood (reworked)',P3,0),
 ('GIN-11624',9450,60,s14,'Early Butovo Mesolithic, layer IV','wood (reworked)',P3,0),
 ('GIN-11054',9400,60,s14,'Early Butovo Mesolithic, layer IV','wood (stick)',P3,0),
 ('GIN-10109',8540,180,st,'Middle Butovo Mesolithic, layer III','gyttja',P4,1),
 ('GIN-10109',8930,40,st,'Middle Butovo Mesolithic, layer III','gyttja',P4,1),
 ('GIN-10110',8500,150,st,'Middle Butovo Mesolithic, layer III','gyttja',P4,1),
 ('GIN-10110',8640,60,st,'Middle Butovo Mesolithic, layer III','gyttja',P4,1),
 ('GIN-10122',9280,240,st,'Middle Butovo Mesolithic, layer III','gyttja',P4,1),
 ('GIN-10122',8610,40,st,'Middle Butovo Mesolithic, layer III','gyttja',P4,1),
 ('GIN-8375',9220,60,st,'Middle Butovo Mesolithic, layer III','wood (stick)',P4,0),
 ('GIN-10093a',8850,90,st,'Middle Butovo Mesolithic, layer III','bone',P4,0),
 ('GIN-8854',8700,70,st,'Middle Butovo Mesolithic, layer III','wood (stick)',P4,0),
 ('GIN-8856',8670,50,st,'Middle Butovo Mesolithic, layer III','wood (stick)',P4,0),
 ('GIN-8853',8540,60,st,'Middle Butovo Mesolithic, layer III','wood (stick)',P4,0),
 ('GIN-11180',8800,100,s14,'Middle Butovo Mesolithic, layer III (text: IIIa)','bone (elk skull)',P4,0),
 ('GIN-11053',9010,60,s14,'Middle Butovo Mesolithic, layer III (text: IIIa)','wood (stick)',P4,0),
 ('GIN-9366',8550,100,iv,'Middle-to-late Butovo Mesolithic, layer III','gyttja',P5,0),
 ('GIN-9365',8540,100,iv,'Middle-to-late Butovo Mesolithic, layer III (overlying gyttja)','gyttja',P5,0),
 ('GIN-9373',8200,300,iv,'Middle-to-late Butovo Mesolithic, layer III','peat',P5,1),
 ('GIN-9373',8530,50,iv,'Middle-to-late Butovo Mesolithic, layer III','peat',P5,1),
 ('GIN-9372',8290,160,iv,'Middle-to-late Butovo Mesolithic, layer III (overlying gyttja)','gyttja',P5,0),
 ('GIN-11050',8310,60,s14,'Late Butovo Mesolithic, layer II','peat',P5,0),
 ('GIN-11602',8240,40,s14,'Late Butovo Mesolithic, layer II','peat',P5,0),
 ('GIN-11601',7990,50,s14,'Late Butovo Mesolithic, layer II','peat',P5,0),
 ('GIN-10862',8060,50,s2,'Late (Upper) Butovo Mesolithic, layer IIa','wood (small plank)',P5,0),
 ('GIN-9361',7530,150,iv,'Final Butovo Mesolithic, layer IIa','peat',P6,1),
 ('GIN-9361',7520,60,iv,'Final Butovo Mesolithic, layer IIa','peat',P6,1),
 ('GIN-11599',7200,40,s14,'Final Butovo Mesolithic, layer I','peat',P6,0),
 ('GIN-10861',7530,60,s2,'Final Butovo Mesolithic, layer II','peat',P6,0),
 ('GIN-10860',7390,40,s2,'Final Butovo Mesolithic, layer II','wood (basket trap)',P6,0),
 ('GIN-10106',6650,160,st,'Upper Volga Early Neolithic, layer II','gyttja',P7,1),
 ('GIN-10106',7080,40,st,'Upper Volga Early Neolithic, layer II','gyttja',P7,1),
 ('GIN-8378',7030,100,st,'Upper Volga Early Neolithic, layer II','wood (small plank)',P7,0),
 ('GIN-9360',7100,110,iv,'Upper Volga Early Neolithic, layer II','buried soil',P7,1),
 ('GIN-9359',6690,110,iv,'Upper Volga Early Neolithic, layer II','buried soil',P7,1),
 ('GIN-9359',6670,140,iv,'Upper Volga Early Neolithic, layer II','buried soil',P7,1),
 ('GIN-10924',6500,100,s2,'Upper Volga Early Neolithic, layer I','food crust (charred food residue)',P7,0),
 ('GIN-11915',6820,70,pz,'Kama (Kamskaya) Early Neolithic, layer I','food crust (charred food residue)',P7,0),
 ('GIN-12325',6760,50,pz,'Kama (Kamskaya) Early Neolithic, layer I','charcoal',P7,0),
 ('GIN-12322',6730,50,pz,'Kama (Kamskaya) Early Neolithic, layer I (enclosing mud)','mud (oxbow sediment)',P7,0),
]
for lab,bp,sd,site,per,mat,pg,t in e:
    add(lab,bp,sd,site,per,mat,pg+', sample '+lab.split('-')[1]+(two if t else ''),5)
# ---- 2012 ----
v='Varga-2'; b='Beregovaya-2'; a='Anin Ostrov'
T='table 1, no. '
f=[
 (2,'GIN-13860',7010,50,v,'Early Neolithic cultural layer (peaty gyttja enclosing artefacts)','peaty gyttja','p. 785'),
 (12,'GIN-13870',5460,100,a,'Chalcolithic cultural layer apron (Fig. 2)','algae gyttja','p. 786'),
 (13,'GIN-13871',6730,160,a,'Early Neolithic cultural layer apron, level with Neolithic ceramics (Fig. 2)','Cyanophyceae gyttja','p. 786'),
 (14,'GIN-13872',8620,130,a,'Mesolithic cultural layer apron (Fig. 2)','organo-mineral gyttja','p. 786'),
 (15,'GIN-12990',6850,60,v,'Early Neolithic, cultural layer II','wood (chip)','p. 786'),
 (16,'GIN-13852',6970,40,v,'Early Neolithic, cultural layer II','wood (small charred plank)','p. 786'),
 (17,'GIN-13849',6970,70,v,'Early Neolithic, cultural layer I/II','wood (small charred plank)','p. 786'),
 (18,'GIN-13855',7080,70,v,'Early Neolithic, cultural layer II','wood (charred half-timber)','p. 786'),
 (19,'AAR-14837',7106,35,v,'Early Neolithic, cultural layer II','food crust (charred remain on rim fragment)','p. 786'),
 (20,'AAR-14548',7278,34,b,'Early Neolithic, cultural layer II','antler (elk, pick-axe insert)','p. 786'),
 (21,'KIA-42074',7325,40,b,'Early Neolithic (Koshkino-type pottery), cultural layer II','food crust (charred residue on sherd)','p. 786'),
 (22,'AAR-14833',7320,38,b,'Early Neolithic, cultural layer II','food crust (charred remain on rim sherd)','p. 786'),
 (23,'GIN-14134',7960,30,b,'Late Mesolithic, cultural layer III (trackway)','wood (trackway plank)','p. 786'),
 (24,'AAR-14549',7989,36,b,'Late Mesolithic, cultural layer III','bone (elk scapula knife)','p. 786'),
 (25,'GIN-14133',7990,30,b,'Late Mesolithic, cultural layer III (trackway)','wood (trackway plank)','p. 786'),
 (26,'GIN-14087',7990,40,b,'Late Mesolithic, cultural layer III (trackway)','wood (trackway plank fragment)','p. 786'),
 (27,'GIN-14085',8120,50,b,'Late Mesolithic, cultural layer III','wood (thin burnt trunk)','p. 786'),
 (28,'GIN-14086',8350,40,b,'Late Mesolithic, bottom of cultural layer III','wood (burnt pine stake)','p. 786'),
 (29,'AAR-14834',8405,40,b,'Middle Mesolithic, cultural layer IV','bark (willow, net-sinker binding)','p. 786'),
 (30,'KIA-42075',8445,50,b,'Middle Mesolithic, cultural layer IV','bark (willow, net-sinker binding)','p. 786'),
 (31,'GIN-14137',8490,40,b,'Middle Mesolithic, cultural layer IV','wood (stake)','p. 786'),
 (32,'GIN-14089',8670,40,b,'Middle Mesolithic, cultural layer IV','wood (worked plank)','p. 786'),
 (33,'GIN-14207',8840,70,b,'Middle Mesolithic, cultural layer IV','antler (elk)','p. 786'),
 (34,'GIN-14090',8970,60,b,'Middle Mesolithic, cultural layer IV','wood (worked larch branch)','p. 786'),
 (35,'GIN-14136',9010,40,b,'Middle Mesolithic, cultural layer IV','wood (larch stake)','p. 786'),
 (37,'GIN-14088',9800,40,b,'Early Mesolithic, cultural layer V','wood (larch stake)','p. 786'),
 (38,'GIN-14210',9830,70,b,'Early Mesolithic, cultural layer V','bone (two elk bones)','p. 787'),
 (39,'KIA-42076',9835,50,b,'Early Mesolithic, cultural layer V','bone (elk scapula knife)','p. 787'),
 (40,'GIN-14135',9850,40,b,'Early Mesolithic, cultural layer V','wood (worked larch log)','p. 787'),
 (41,'GIN-14209',10060,80,b,'Early Mesolithic, cultural layer V','bone (red deer scapula knife preform)','p. 787'),
 (42,'KIA-42077',9215,40,b,'Early Mesolithic, cultural layer V','bone (tool preform, tubular bone)','p. 787'),
 (43,'GIN-14251',8980,90,b,'Early Mesolithic, cultural layer V','wood (larch stake)','p. 787'),
 (44,'GIN-14249',9230,50,b,'Early Mesolithic, cultural layer V','wood (larch stake)','p. 787'),
 (45,'GIN-14250',9230,60,b,'Early Mesolithic, cultural layer V','wood (larch stake)','p. 787'),
 (46,'GIN-14080',8360,40,b,'Late Mesolithic, bottom of cultural layer III (section 1)','sedge peat','p. 787'),
 (48,'GIN-14082',8970,40,b,'Middle Mesolithic, top of cultural layer IV (section 1)','gyttja','p. 787'),
 (50,'GIN-14084',9610,40,b,'Early Mesolithic, cultural layer V (section 1)','peaty gyttja','p. 787'),
 (54,'GIN-14126',7990,40,b,'Late Mesolithic, cultural layer III trackway level (section 2)','sedge peat','p. 787'),
 (58,'GIN-14130',8520,100,b,'Middle Mesolithic, top of cultural layer IV (section 2)','gyttja','p. 787'),
 (59,'GIN-14131',9170,90,b,'Middle Mesolithic, bottom of cultural layer IV (section 2)','gyttja','p. 787'),
 (60,'GIN-14132',9210,40,b,'Early Mesolithic, cultural layer V (section 2)','peaty gyttja','p. 787'),
 (61,'GIN-14140',9390,40,b,'Early Mesolithic, cultural layer V','peaty gyttja','p. 787'),
]
for n,lab,bp,sd,site,per,mat,pg in f:
    add(lab,bp,sd,site,per,mat,f'{pg}, {T}{n}',12)
with open(OUT,'w',newline='',encoding='utf-8') as fh:
    w=csv.DictWriter(fh,fieldnames='labnr,bp,std,lon,lat,site,type,period,material,approximate,precision,source,page,refs'.split(','))
    w.writeheader(); w.writerows(rows)
import collections
for s in (S05,S12):
    rr=[r for r in rows if r['source']==s]
    print(s,len(rr),sorted(collections.Counter(r['site'] for r in rr).items()),min(r['bp'] for r in rr),max(r['bp'] for r in rr))
d=collections.Counter(r['labnr'] for r in rows); print('dup labnr',[k for k,c in d.items() if c>1])
