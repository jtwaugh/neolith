import csv,json,sys
C=json.load(open('dl_seits/sitecoords.json'))
C['19']=C['18']
sites={1:'Antrea Korpilahti (Vuoksenranta)',2:'Antrea Suuri Kelpojärvi',3:'Heinjoki Latukangas 1 (Veschevo 1)',5:'Heinjoki Valklampi 1',6:'Heinjoki Valklampi 2',7:'Hepojärvi',8:'Johannes Loikas',9:'Johannes Tokarevo 1:1',10:'Johannes Väntsi',11:'Joutseno Saarenoja 2',14:'Kanneljärvi Kanneljärvi 2',15:'Kaukola Juho Paavilaisen Rantapelto (Kankaanmäki)',16:'Kaukola Piiskunsalmi Lavamäki',17:'Kaukola Riukjärvi (Kyöstälänharju)',18:'Kaukola Rupunkangas 1A',19:'Kaukola Rupunkangas 3',20:'Kirvu Harjula',21:'Kirvu Juhola 2',23:'Kurkijoki Kuuppala Kalmistomäki',24:'Kurkijoki Kylliäisenlahti W-2',25:'Kurkijoki Lahdenryhmä',26:'Lavansaari Suursuonmäki',27:'Luumäki Mustaniemi',29:'Muolaa Silino 1',30:'Pyhäjärvi Kunnianniemi',31:'Pyhäjärvi Porsaanmäki 1',32:'Pyhäjärvi Ristilä 1',33:'Räisälä Hiekka 1',34:'Räisälä Juoksemajärvi Westend',35:'Räisälä Hovi Kalmistomäki',36:'Räisälä Kuusela',37:'Räisälä Peltola C',38:'Viipuri Häyrynmäki',39:'Viipuri Ozernoe 3',40:'Virolahti Meskäärtty'}
# date nr, site nr, context, material, lab, bp, sd, rating
D="""1|1|EM, net float, NM 6688|pine bark|Hel-1303|9310|140|22
2|1|EM, net float, NM 6688|pine bark|Hel-269|9230|210|22
3|1|EM, net cord, NM 6688|willow cord|Hela-404|9140|135|23
4|2|EM, cultural layer|burnt bone|Hela-931|9275|120|13
5|3|EN, CW1, charcoal concentration|charcoal|Le-6511|5770|130|17
6|3|EMP, cultural layer|charcoal|Le-6559|2400|50|18
9|5|EM, cultural layer|burnt bone|Hela-743|8765|65|14
10|6|EM, cultural layer|burnt bone|Hela-744|8720|70|13
11|7|LM/EN, hearth|charcoal|Le-1412|6480|60|20
12|7|LM/EN, hearth|charcoal|Le-1411|6380|60|20
13|7|LN, org, hearth|charcoal|Le-1410|4100|60|20
14|7|LN, org, pit feature|charcoal|Le-1408|4020|70|19
15|8|LN, cord?, hearth|charcoal|Hela-663|3860|45|16
16|9|MN, CW2, potsherd|charred crust|Ki-10298|4790|210|19
17|10|MN, Kierikki, potsherd, NM 9406:188|charred crust|Hela-465|4870|85|20
18|11|EM, cultural layer|burnt bone|Hela-728|9310|75|15
22|14|LN, charcoal concentration|charcoal|Le-2549|3890|40|17
23|14|EMP, charcoal concentration|charcoal|Le-2550|3500|40|18
24|15|EMP, potsherd, NM 7117:24|charred crust|Hela-467|3085|70|20
25|16|LN, cord, potsherd NM 6385:21|charred crust|Hela-468|4130|60|21
26|17|MN, CW3, potsherd NM 5699:9|birch bark tar|Hela-359|4780|70|20
27|18|EM, inside a house-pit|charcoal|Hela-1182|8770|85|17
28|18|EM, inside a house-pit|charcoal|Hela-1197|8130|65|13
29|18|LM, inside a house-pit|charcoal|Hela-1196|7550|75|10
30|18|LM, inside a house-pit|charcoal|Hela-1195|6595|55|11
32|19|EM, cultural layer|burnt bone|Hela-1165|8740|80|11
33|20|LN, org, hearth|burnt bone|Hela-1176|3995|40|16
34|21|EM, bone pit|burnt bone|Hela-1164|8970|75|16
36|23|MN, cultural layer|charcoal|Su-2651|4620|60|10
37|23|EMP, cultural layer|charcoal|Le-4145|2920|190|10
38|24|LM/EN, pit feature|charcoal|Le-6928|6400|600|15
39|25|LM, pit feature|charcoal|Le-6929|7900|80|16
40|25|EMP?, pit feature|charcoal|Le-6930|2230|30|16
41|26|EMP, cairn|charcoal|Su-3297|1660|50|13
42|26|EMP, cairn 1, NM 9229:2|resin|Ua-2545|1975|70|24
43|26|EMP, cairn 2, NM 9229:8|resin|Ua-2546|1960|70|24
44|26|EMP, cairn 3, NM 9229:11|resin|Ua-2547|2165|60|25
45|27|EM, hearth|burnt bone|Hel-4395|8580|140|18
50|29|LM, hearth|charcoal|Hela-524|6975|80|20
51|29|LM, charcoal concentration|charcoal|Hela-526|6860|75|19
52|29|LM, hearth|charcoal|Hela-525|6815|80|20
53|29|EN, CW1, potsherd|charred crust|Hela-554|5830|80|20
54|29|MN, CW2, potsherd|charred crust|AAR-7129|5050|100|22
55|29|MN, CW2:1, potsherd|charred crust|Hela-553|4965|80|23
56|29|MN, CW2, hearth|charcoal|Hela-591|4965|60|20
57|29|LN asb, potsherd|charred crust|AAR-7130|4430|65|21
59|30|LM, hearth|burnt bone|Hela-1842|7195|45|21
60|30|LM, bone concentration|burnt bone|Hela-2048|7077|49|21
61|30|LM, hearth|burnt bone|Hela-1843|7025|45|21
62|30|EN, CW1:2, potsherd|charred crust|Hela-1817|5635|45|22
63|30|MN, CW2, potsherd|charred crust|Hela-1816|4930|35|23
64|30|MN, netsinker|birch bark|Hela-1554|4450|35|23
65|30|LN, Pöljä, potsherd|charred crust|Hela-1819|4030|35|25
66|30|LN, Pöljä, bone pit|burnt bone|Hela-1844|3955|35|20
67|30|EMP, cultural layer|charcoal|Le-8021|1720|40|14
68|31|LN, org, pit feature, on the wall of a house-pit|charcoal|Hela-1821|4390|35|18
69|32|LM, hearth|charcoal|Hela-1822|7095|45|17
70|33|LM, next to a hearth|burnt bone|Hela-1163|6840|60|17
71|33|LM, next to a hearth|burnt bone|Hela-1256|6950|60|17
72|34|LM, cultural layer|charcoal|Le-6556|7750|180|11
73|34|MN, cultural layer|charcoal|Le-6641|4550|180|18
74|34|LN, cultural layer|charcoal|Le-6512|4150|50|18
75|34|LN, cultural layer|charcoal|Le-6601|3740|90|19
76|34|LN, cultural layer|charcoal|Le-6557|3700|320|19
77|34|LN, charcoal concentration next to a hearth in the eastern half of a house-pit|charcoal|Le-6602|3660|30|24
78|34|LN, cultural layer|charcoal|Le-6642|3450|100|20
79|34|EMP, charcoal concentration (hearth) in the western corner of a house-pit|charcoal|Le-6600|3370|30|23
82|35|EMP, potsherd, NM 2556|charred crust|Hela-8|2360|70|20
83|35|EMP, potsherd, NM 6675:42|charred crust|Hela-466|2640|70|23
84|35|EMP, potsherd, NM 6675:50|charred crust|Hela-469|2540|75|23
85|36|LM, cultural layer|burnt bone|Hela-1175|7945|60|10
86|37|MN, CW2, wall of a pithouse|resin "chewing gum"|Hela-1159|4905|45|13
87|38|MN, CW3, potsherd, NM 5620:CCXLIV|birch bark tar|Hela-358|4550|60|21
88|39|LM, cultural layer|charcoal|Le-7538|7580|50|20
89|39|LM, cultural layer|charcoal|Le-7539|7220|50|20
90|39|LM, cultural layer|charcoal|Le-7540|7680|50|20
91|39|LM, cultural layer|charcoal|Le-7541|7640|50|20
92|40|MN, CW3, potsherd, NM 37112:1|charred crust|Hela-1613|4535|35|23
93|40|MN, CW3, potsherd, NM 37112:3|charred crust|Hela-1615|4520|40|23
94|40|LN, cord, potsherd; NM 37112:2|charred crust|Hela-1614|3820|45|20"""
ctrl={38:'Vyborg (Häyrynmäki is a district of Vyborg)',26:'Moshchny Island (Lavansaari)',23:'Kurkiyoki village',30:'Lake Otradnoye (Pyhäjärvi)'}
figs={1:'3',2:'3',3:'3, 6',5:'3',6:'3',7:'3, 5',8:'5',9:'5',10:'5',11:'3',14:'5, 6',15:'6',16:'5',17:'5',18:'3',19:'3',20:'5',21:'3',23:'5, 6',24:'3',25:'3, 6',26:'6',27:'3',29:'3, 5',30:'3, 5, 6',31:'5',32:'3',33:'3',34:'3, 5, 6',35:'6',36:'3',37:'5',38:'5',39:'3',40:'5'}
refs="Seitsonen, O., Nordqvist, K., Gerasimov, D.V. & Lisitsyn, S.N. 2012. 'The good, the bad, the weird': Stone Age and Early Metal Period radiocarbon dates and chronology from the Karelian Isthmus, North-West Russia. Geochronometria 39(2): 101-121. doi:10.2478/s13386-012-0002-9. PDF: https://www.geochronometria.com/pdf-184394-105143?filename=-The-good--the-bad--the-w.pdf"
PER={'EM':'Early Mesolithic','LM':'Late Mesolithic','EN':'Early Neolithic','MN':'Middle Neolithic','LN':'Late Neolithic','EMP':'Early Metal Period','LM/EN':'Late Mesolithic/Early Neolithic','EMP?':'Early Metal Period?'}
out=[]
for line in D.splitlines():
    dn,sn,ctx,mat,lab,bp,sd,rt=line.split('|'); dn=int(dn); sn=int(sn)
    lon,lat=C[str(sn)]
    head=ctx.split(',')[0].split(' ')[0]
    per=f"{PER.get(head,head)}; context: {ctx}; usability score {rt} ({'Good' if int(rt)>=20 else 'Weird'})"
    note=" (Rupunkangas 3 is labelled beside the Rupunkangas 1A dot; same point used)" if sn==19 else ""
    if sn in ctrl:
        prec=f"approximate: site {sn} dot on Fig. {figs[sn]}; this dot is one of four georeferencing controls, placed at {ctrl[sn]} per Wikipedia; about +-5 km"
    else:
        prec=f"approximate: site {sn} dot on Fig. {figs[sn]} (pp. 108-113){note}, read off the figure, georeferenced by an affine fit to Vyborg, Moshchny Island (Lavansaari), Kurkiyoki and Lake Otradnoye (Wikipedia coordinates; control residuals <=2.5 km); about +-5 km"
    typ='net find' if sn==1 else ('cairns' if sn==26 else 'dwelling site')
    pg=105 if dn<=35 else (106 if dn<=71 else 107)
    out.append([lab,int(bp),int(sd),round(lon,4),round(lat,4),sites[sn],typ,per,mat,'true',prec,'Seitsonen et al. 2012',f"p. {pg}, Table 2, date no. {dn} (site {sn})",refs])
w=csv.writer(open(sys.argv[1],'a',newline='',encoding='utf-8')); w.writerows(out)
print(len(out),len({o[5] for o in out}),min(o[1] for o in out),max(o[1] for o in out))
