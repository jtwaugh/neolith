import json,csv,re,collections,sys
R=json.load(open('dl_tarasov/rows.json'))
mapc={1:(34.896,61.494),2:(34.763,62.311),3:(33.178,62.024),4:(35.212,62.026),5:(33.315,63.28),6:(32.293,64.096),7:(37.087,62.427),8:(35.318,61.409),9:(35.061,62.721),10:(36.212,61.62),11:(34.595,64.471),12:(34.381,61.779),13:(37.208,62.365),14:(34.876,62.857),15:(34.274,61.879),16:(33.095,64.397),17:(30.54,61.737),18:(32.468,62.914),19:(35.517,62.592),24:(36.1,61.772),26:(31.435,61.68),27:(29.841,61.261)}
gaz={2:(34.766,62.3265,"Pegrema village, Zaonezhye, Medvezhyegorsk district, per en.wikipedia 'Pegrema'"),
8:(35.356448,61.370584,"Shyoltozero (Sheltozero) village, SW shore of Lake Onega, per ru.wikipedia 'Шёлтозеро'"),
11:(34.6748,64.4981,"the Zalavruga petroglyph site on the lower Vyg near Belomorsk, per ru.wikipedia 'Залавруга' (Besovy Sledki, Zolotets and Yerpin Pudas lie within a few km on the same lower Vyg)"),
14:(34.81667,62.85,"Povenets village at the north end of Lake Onega, per en.wikipedia 'Povenets'"),
19:(35.589832,62.589654,"Chyolmuzhi (Chelmuzhi) village on the Chelmuzhskaya spit, NE Lake Onega, per ru.wikipedia 'Чёлмужи'"),
26:(31.41583,61.65472,"Koyrinoya village, NE shore of Lake Ladoga, per ru.wikipedia 'Койриноя'"),
27:(29.88139,61.3,"Kurkiyoki village, NW Ladoga region, per ru.wikipedia 'Куркиёки'")}
where={1:"SW shore of Lake Onega between Petrozavodsk and Sheltozero",3:"shore of Lake Syamozero west of Lake Onega (the map lake matches Syamozero, en.wikipedia 61.92N 33.17E)",
4:"east shore of the Zaonezhye peninsula, Lake Onega",5:"west shore of Lake Segozero (map lake matches Segozero, en.wikipedia 63.3N 33.75E)",6:"on a river in west-central Karelia",
7:"Lake Vodlozero, eastern Karelia (map lake matches Vodlozero, en.wikipedia 62.33N 36.92E)",13:"Lake Vodlozero / upper Vodla, eastern Karelia",9:"north shore of Lake Onega (Povenets bay) east of Povenets",
10:"east shore of Lake Onega south of the Vodla mouth",12:"west shore of Lake Onega at Petrozavodsk",15:"Shuya river mouth area north of Petrozavodsk (Shuya village, ru.wikipedia 61.90N 34.24E, is ~2 km away)",
16:"a lake in the Vyg basin, north-central Karelia",17:"north of Lake Ladoga near Lake Janisjarvi",18:"shore of an elongated lake in west-central Karelia",24:"east shore of Lake Onega near the Vodla mouth"}
fix={'TA-1450':"Charcoal from 'ritual' pit in a burial, depth 0,25–0,35m",'Beta-117965':"Charcoal from a lens close to entrance of a dwelling",'TA-2271':"Charcoal from a layer buried under the embankment of a dwelling related to Orovnavolok"}
PF='Pit-Comb (singular fragments), Voynavolok, Orovnavolok'
RZ='Rhomb-Pit, Zalavruga, Orovnavolok, Palayguba'
rowtyp={'GrA-63735':'Sperrings','TA-2265':'Sperrings, Pit-Comb','TA-2266':'Sperrings, Pit-Comb',
'GrA-63547':'Säräisniemi 1','GrA-63681':'Pit-Comb','GrA-63548':'Pit-Comb','GrA-64331':'Pit-Comb',
'GrA-63539':'Comb-Pit','GrA-63538':'Comb-Pit','TA-1890':'Pit-Comb, Comb-Pit, Rhomb-Pit','GrA-63540':'Comb-Pit','GrA-63537':'Comb-Pit',
'Beta-117965':'Comb-Pit, Rhomb-Pit','Beta-117964':'Rhomb-Pit','Beta-117962':'Rhomb-Pit','Beta-117963':'Rhomb-Pit','Beta-117966':'Orovnavolok (?)','Beta-117961':'Orovnavolok (?)','TA-828':'Orovnavolok',
'TA-393':RZ,'GIN-130':RZ,'GrA-63559':'Zalavruga','GrA-63551':'Zalavruga','GrA-63555':'Zalavruga','GrA-63552':'Orovnavolok','GrA-63557':'Orovnavolok','GrA-63558':'Orovnavolok',
'SPb-784':PF,'SPb-783':PF,'GrA-62060':'Voynavolok','GrA-62059':'Orovnavolok','Poz-85971':PF,'GrA-62484':'Voynavolok','Hela-2812':'Orovnavolok','GrA-63891':PF,
'KIA-35899A':'Säräisniemi 1','KIA-35899B':'Säräisniemi 1'}
def mat(c):
    c0=c.lower()
    for k,v in [('birch bark tar','birch bark tar on pottery'),('crust','food crust on pottery'),('black paint','black paint on pottery'),('calcinated bone','calcined bone'),('bone','bone'),('birch bark','birch bark'),('charcoal','charcoal'),('unknown','unknown')]:
        if k in c0: return v
    return c
refs="Tarasov, A., Nordqvist, K., Mökkönen, T. & Khoroshun, T. 2017. Radiocarbon chronology of the Neolithic-Eneolithic period in the Karelian Republic (Russia). Documenta Praehistorica 44: 98-121. doi:10.4312/dp.44.7. PDF: https://journals.uni-lj.si/DocumentaPraehistorica/article/download/44.7/7341"
bands=collections.defaultdict(list)
for r in R: bands[(r['page'],r['band'])].append(r)
out=[];skipped=[]
for r in R:
    lab=r['lab'].split()[-1]
    if lab.endswith('|'): skipped.append((r['site'],r['bp'],lab)); continue
    site=re.sub(r'\s+',' ',r['site']).replace('Kylliäisen- lahti','Kylliäisenlahti').replace('\\','/')
    mno=int(r['mapno'].split()[0])
    bp,sd=r['bp'].split('±')
    ctx=fix.get(lab,r['ctx']).strip()
    band=bands[(r['page'],r['band'])]
    if lab in rowtyp: typ=rowtyp[lab]
    elif len(band)>1 and all(x['rtyp'] for x in band) and site in('Sheltozero V','Kalmozero II','Chernaya Guba IX'): typ=r['rtyp']
    else:
        typ=re.sub(r'\s+',' ',r['typ']).strip()
        if site=='Fofanovo XIII': typ='Pit-Comb (singular fragments), Voynavolok, Orovnavolok'
    typ=typ.replace('(|)','(?)').replace('Comb- Pit','Comb-Pit')
    if mno in gaz:
        lon,lat,g=gaz[mno]; prec=f"approximate: Map 1 (p. 99) locality {mno}; placed at {g}; the georeferenced Map 1 dot is within ~5 km; about +-5-10 km"
    else:
        lon,lat=mapc[mno]; prec=f"approximate: Map 1 (p. 99) locality {mno} ({where[mno]}); read off Map 1, georeferenced by an affine fit to its N63/E34 graticule cross and 8 localities placed from Wikipedia (fit residuals <=8 km); about +-8 km"
    out.append([lab,int(bp),int(sd),round(lon,4),round(lat,4),site,'site',f"Neolithic-Eneolithic; typological connection: {typ}",f"{mat(ctx)} ({ctx})",'true',prec,'Tarasov et al. 2017',f"p. {r['page']+97}, Tab. 1, map no. {mno}",refs])
w=csv.writer(open(sys.argv[1],'a',newline='',encoding='utf-8')); w.writerows(out)
print(len(out),len({o[5] for o in out}),min(o[1] for o in out),max(o[1] for o in out)); print('skipped',skipped)
print(sorted({o[5] for o in out}))
