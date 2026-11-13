import csv,re,sys
txt=open('dl_kama/kama.txt').read().splitlines()
start=[i for i,l in enumerate(txt) if l.startswith('Tab. 1. Radiocarbon')][0]
rows=[]
for l in txt[start+2:start+70]:
    m=re.match(r'\s*(\d+)\s+(.+?)\s{2,}(\d+)±(\d+)\s+(?:1σ\s+)?\d+–\d+\s+(\S+)\s+(.+?)\s*$',l)
    if m: rows.append(m.groups())
assert len(rows)==57,len(rows)
mapno={'Pezmog IV':1,'Chirva II':2,'Vasjukovo II':3,'Khutorskaya':4,'Lake Chashkinskoye I':5,'Lake Chashkinskoye IIIa':6,'Lake Chashkinskoye VI':7,'Ust-Zalaznushka II':8,'Posyor':9,'Lake Borovoe I':10,'Lyovshino':11,'Mokino':12,'Krjazhskaya':13,'Chernashka':14,'Chernushka':15,'Tarhan I':16,'Ust-Shizhma':17,'Srednee Shadbegovo':18,'Kyilud III':19,'Chumoytlo':20,'Mullino':21,'Ziarat':22,'Sauz II':23,'Caen-Tubinskaya':24,'II Lebedinskaya':25,'Podlesnoe III':26,'Podlesnoe IV':27,'Lake Molebnoe I':28,'Otarskaya VI':29,'Nizhnaya strelka V':30,'Ozimenki II':31,'Lesnoe-Nikolskoe III':32}
geo={'1':(51.79,61.79),'2':(57.61,60.60),'3':(57.18,60.45),'4-7':(57.67,59.26),'8':(57.06,59.27),'9':(56.40,58.26),'10':(57.32,58.15),'11':(57.11,57.80),'12':(56.78,57.60),'13':(56.12,57.53),'14':(55.58,57.38),'15':(54.40,56.42),'16':(51.51,56.89),'17':(50.49,57.26),'18':(53.61,57.00),'19':(53.11,56.49),'20':(52.94,56.16),'21':(53.90,53.82),'22':(54.63,55.84),'23':(55.03,55.68),'24':(53.26,55.53),'25':(50.28,55.05),'26':(45.29,53.08),'27':(45.59,52.91),'28':(47.00,54.69),'29':(47.17,56.21),'30':(45.41,56.15),'31':(43.89,53.71),'32':(49.58,54.75)}
reject={19,20,21,26,27,28,32}
refs="Lychagina, E.L. & Vybornov, A.A. 2017. Chronology of Kama Neolithic culture. Documenta Praehistorica 44: 152-161. doi:10.4312/dp.44.9. PDF: https://revije.ff.uni-lj.si/DocumentaPraehistorica/article/download/44.9/7343"
mat={'Pottery carbon':'pottery (organic carbon in fabric)','Crust':'food crust on pottery','Charcoal':'charcoal','Cultural deposit':'cultural deposit'}
out=[]
for no,site,bp,sd,lab,m in rows:
    no=int(no)
    if no in reject: continue
    site=site.replace('–','-').strip()
    n=mapno[site]
    phase='Kama culture, early phase' if no<=14 else ('Kama culture, middle (Khutorskaya) phase' if no<=43 else 'Kama culture, late (Lyovshinskaya) phase')
    key='4-7' if 4<=n<=7 else str(n)
    lon,lat=geo[key]
    if n==1:
        lon,lat=51.85,61.80
        prec="approximate: Fig. 1 locality 1 (Pezmog IV, Vychegda basin); coordinates from Dolbunova et al. 2023 SI_ORA site table (Pezmog IV), consistent with the map placement within ~10 km"
    elif n==11:
        lon,lat=56.24889,58.01389
        prec="approximate: Fig. 1 locality 11 (Lyovshino, the Levshino station site at Perm); placed at Perm city per ru.wikipedia 'Perm' (58.01389 N, 56.24889 E), about +-15 km"
    else:
        lab_loc='localities 4-7 (Khutorskaya and Lake Chashkinskoye I, IIIa, VI, one cluster on the Lake Chashkinskoye oxbow, left bank of the upper Kama)' if key=='4-7' else f'locality {n} ({site})'
        prec=f"approximate: Fig. 1 (p. 153) {lab_loc}; read off the small-scale relief map, georeferenced by a Lambert azimuthal equal-area fit (centre 15E 45N) to Ladoga, Onega, Beloye, Rybinsk Reservoir, Samara (Wikipedia coordinates) and Pezmog IV; fit rms ~6 km, map-drawing error ~25 km, so about +-40 km"
    typ='camp' if no>=44 else 'site'
    out.append([lab,int(bp),int(sd),round(lon,4),round(lat,4),site,typ,phase,mat[m],'true',prec,'Lychagina & Vybornov 2017',f'p. 161, Tab. 1, no. {no}',refs])
w=csv.writer(open(sys.argv[1],'w',newline='',encoding='utf-8'))
w.writerow('labnr,bp,std,lon,lat,site,type,period,material,approximate,precision,source,page,refs'.split(','))
w.writerows(out)
print(len(out),len({r[5] for r in out}),min(r[1] for r in out),max(r[1] for r in out))
