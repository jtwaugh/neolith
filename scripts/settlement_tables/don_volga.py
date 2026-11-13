import csv
OUT='./don_volga.csv'
R1='Tsybrij, A., Tsybrij, V., Dolbunova, E., Mazurkevich, A., Kulkova, M. & Zaitseva, G. 2017, Radiocarbon chronology of Neolithic in the Lower Don and North-eastern Azov Sea, Documenta Praehistorica 44:204-223, doi:10.4312/dp.44.13, https://journals.uni-lj.si/DocumentaPraehistorica/article/view/44.13 (PDF https://journals.uni-lj.si/DocumentaPraehistorica/article/download/44.13/7349)'
R2='Kulkova, M.A., Vybornov, A.A., Yudin, A., Doga, N. & Popov, A. 2019, New interdisciplinary research on Neolithic-Eneolithic sites in the Low Volga River region, Documenta Praehistorica 46:376-387, doi:10.4312/dp.46.23, https://journals.uni-lj.si/DocumentaPraehistorica/article/view/46.23 (PDF https://journals.uni-lj.si/DocumentaPraehistorica/article/download/46.23/8754)'
S1='Tsybrij et al. 2017'; S2='Kulkova et al. 2019'
RY='Rakushechny Yar'
# site -> (lon, lat, type, precision)
SITES={
 RY:(40.67,47.56,'settlement','approximate: Porechny island near Razdorskaya (paper text p. 205); point from Dolbunova et al. 2023 SI_ORA site table ("Rakucheshny Yar" 40.67, 47.56), ~2 km from Razdorskaya stanitsa (ru.wikipedia 47.541, 40.648); about +-3 km'),
 'Razdorskaya II':(40.59,47.53,'site','approximate: paper p. 210 says right bank of the Don 6 km downstream of Rakushechny Yar; placed ~6 km W of the Rakushechny Yar point (Dolbunova 2023), about +-5 km'),
 'Razdorskoe I':(40.648,47.541,'site','approximate: no position in text; Fig. 1 label "Razdorskaya I,II" sits at the Rakushechny Yar dot; placed at Razdorskaya stanitsa (ru.wikipedia 47°32\'27"N 40°38\'51"E), about +-5 km'),
 'Samsonovskoe':(40.7625,47.6681,'settlement','approximate: not located in the paper; placed at Samsonovskoe poselenie coordinates on ru.wikipedia (47°40\'05"N 40°45\'45"E, near khutor Krymsky, Ust-Donetsky district; matches Nominatim Krymsky 47.669, 40.771), about +-1 km'),
 'Matveev Kurgan I':(38.867,47.572,'site','approximate: paper gives only "North-Eastern Azov Sea", Mius River (p. 211) and the Fig. 1 dot; placed at Matveyev Kurgan settlement (ru.wikipedia 47°34\'20"N 38°52\'00"E), about +-10 km'),
 'Matveev Kurgan II':(38.867,47.572,'site','approximate: paper gives only "North-Eastern Azov Sea", Mius River (p. 211) and the Fig. 1 dot; placed at Matveyev Kurgan settlement (ru.wikipedia 47°34\'20"N 38°52\'00"E), about +-10 km'),
 'Kremennaya II':(41.67,48.62,'site','approximate: paper p. 211 says Gnilaya River basin near Zolotovsky village, Milyutinsky district (ru.wikipedia Milyutinsky district: 1 km NE of khutor Zolotovsky, which could not be geocoded); placed on the Gnilaya at Milyutinskaya (OSM Nominatim river point 48.616, 41.671), about +-25 km'),
 'Kremennaya III':(41.67,48.62,'site','approximate: paper p. 211 says near Kremennaya II (Gnilaya River basin near Zolotovsky, Milyutinsky district); placed on the Gnilaya at Milyutinskaya (OSM Nominatim river point 48.616, 41.671), about +-25 km'),
 'Rassypnaya VI':(41.21,46.10,'site','approximate: paper p. 213 says only "Rassypnaya valley"; placed on the Rassypnaya River, Peschanokopsky district, Rostov oblast (OSM Nominatim river point 46.0995, 41.2063); the river runs ~41.0-41.3 E, so about +-25 km; identification of the valley is mine, consistent with Fig. 1 dot south of the Don and nearby sites Rassypnaya 1, Zhukovskaya 2 named in the text'),
 'Algay':(48.53,50.16,'site','approximate: paper says right bank of the Bolshoy Uzen, Alexandrovsky district, Saratov oblast (p. 377) with a small-scale map; point from Dolbunova et al. 2023 SI_ORA site table (Algay 48.53, 50.16), which coincides with the district centre Aleksandrov Gay, about +-20 km'),
 'Oroshaemoe I':(48.53,50.16,'settlement','approximate: paper says right bank of the Bolshoy Uzen, Alexandrovsky district, Saratov oblast, beside Algay on Fig. 1 (p. 377); placed at the Algay point from Dolbunova et al. 2023 SI_ORA (48.53, 50.16), about +-20 km'),
}
rows=[]
def add(lab,bp,sd,site,period,mat,page,src=S1,ref=R1):
    lon,lat,typ,prec=SITES[site]
    rows.append(dict(labnr=lab,bp=bp,std=sd,lon=lon,lat=lat,site=site,type=typ,period=period,material=mat,approximate='true',precision=prec,source=src,page=page,refs=ref))
EXI='excavation I (Belanovskaya)'
RYC='Rakushechny Yar culture'
T1=[ # no, bp, sd, lab, material, context, culture
 (1,5290,260,'Le-5327','charcoal',EXI+', layer 2',''),
 (2,4830,90,'Le-5387','charcoal',EXI+', layer 2',''),
 (3,6300,300,'Le-5343','ground with charcoal',EXI+', layer 2',''),
 (4,4180,100,'Le-5428','animal bone',EXI+', layer 2',''),
 (5,4360,100,'Bln-1177','charcoal',EXI+', layer 3',''),
 (6,5060,230,'Le-5340','animal bone',EXI+', layer 4',''),
 (7,6300,90,'Le-5482','animal bone',EXI+', layer 4',''),
 (8,6440,35,'Le-5582a','ground',EXI+', layer 5, square A-2',''),
 (9,6320,35,'Le-5582b','ground',EXI+', layer 5, square A-2',''),
 (10,5920,90,'Le-5479','animal bone',EXI+', layer 5',''),
 (11,5890,105,'Ki-955','charcoal',EXI+', layer 5',''),
 (12,6770,450,'Le-5481','animal bone',EXI+', under layer 5',''),
 (13,6070,100,'Bln-704','charcoal',EXI+', layer 8',''),
 # 14 Le-5344 shells excluded
 (15,6070,150,'SPb-751','organic crust (food crust)',EXI+', layer 11',RYC),
 (16,6950,150,'SPb-752','organic crust (food crust)',EXI+', layer 12',RYC),
 (17,6825,100,'Ki-6479','organic crust (food crust)',EXI+', layer 14-15',RYC),
 (18,7040,100,'Ki-6480','organic crust (food crust)',EXI+', layer 15',RYC),
 (19,6930,100,'Ki-6478','organic crust (food crust)',EXI+', layer 15',RYC),
 (20,6625,115,'SPb-747','pottery fragment',"near excavation II (2012, test-pit 2), layer XV",RYC),
 (21,6560,100,'SPb-731','animal bone',"near excavation II (2012, test-pit 2), layer XV",RYC),
 (22,6841,40,'Ua-41365','organic crust (food crust)',EXI+', layer 18',RYC),
 (23,7156,41,'Ua-41364','organic crust (food crust)',EXI+', layer 19',RYC),
 (24,7383,120,'SPb-1177','charcoal','near excavation II (2013 section), layer XV',RYC),
 (25,7475,120,'SPb-1176','organic crust (food crust)','near excavation II (2013 section), layer XVII (= layer 19-20)',RYC),
 (26,7554,169,'Ua-48460','charcoal','near excavation II (2013 section), layer XVII (= layer 19-20), shell pile',RYC),
 (27,7010,126,'Ua-48461','charcoal','near excavation II (2013 section), layer XVII (= layer 19-20), shell pile',RYC),
 (28,7482,120,'SPb-1178','charcoal','near excavation II (2013 section), layer XVII (= layer 19-20)',RYC),
 (29,8020,120,'SPb-1185','fish bones','near excavation II (2013 section), layer XVII (= layer 19-20)',RYC),
 (30,7290,50,'Ua-37097','organic crust (food crust)',EXI+', layer 20',RYC),
 (31,7690,110,'Ki-6475','organic crust (food crust)',EXI+', layer 20',RYC),
 (32,7860,130,'Ki-6477','organic crust (food crust)',EXI+', layer 20',RYC),
 (33,7930,140,'Ki-6476','organic crust (food crust)',EXI+', layer 20',RYC),
 (34,7970,110,'SPb-729','animal bone (elk)','near excavation II (2012, test-pit 1), layer XVII',RYC),
 (35,4020,90,'Le-10473','animal bone','excavation of 2010 (near exc. 16-17 of 1966), layer 2B',''),
 (36,2560,70,'Ki-15184','animal bone','excavation of 2010 (near exc. 16-17 of 1966), layer 2',''),
 (37,4120,60,'Ki-15180','animal bone','excavation of 2010 (near exc. 16 of 1966), layer 2',''),
 (38,4170,60,'Ki-15183','animal bone','trench of 2008 (near exc. 16 of 1966), layer 2',''),
]
C08='stratigraphical cut of 2008 (near exc. 16 of 1966)'
RYQ='Rakushechny Yar culture (?)'
T1+=[
 (39,4590,80,'Ki-15182','ground',C08+', layer 3',''),
 (40,5870,80,'Ki-15942','ground',C08+', layer 14',RYQ),
 (41,7580,90,'Ki-15189','pottery fragment',C08+', layer 14',RYQ),
 (42,5940,60,'Ki-15940','ground',C08+', layer 14',RYQ),
 (43,6410,90,'Ki-15944','ground with charcoal',C08+', layer 15',RYQ),
 (44,5790,90,'Ki-15947','ground with charcoal',C08+', layer 15',RYQ),
 (45,5690,100,'Ki-15941','ground with charcoal',C08+', layer 15',RYC),
 (46,7690,90,'Ki-15186','pottery fragment',C08+', layer 18',RYC),
 (47,5540,100,'Ki-15946','ground with charcoal',C08+', layer 18-19',RYC),
 (48,5670,100,'Ki-15945','ground with charcoal',C08+', layer 18-19',RYC),
 (49,6750,110,'Ki-15187','pottery fragment',C08+', layer 21-22',RYC),
 (50,6890,80,'Ki-15185','pottery fragment',C08+', layer 21-22',RYC),
 (51,7670,90,'Ki-15188','pottery fragment',C08+', layer 22',RYC),
 (52,7020,80,'Ki-15190','pottery fragment',C08+', layer 23',RYC),
 (53,7320,70,'Ki-15943','ground with charcoal',C08+', layer 23',RYC),
 (54,7380,100,'Ki-15181','ground (buried soil X)',C08+', layer 23 / buried soil X',RYC),
 (55,6450,90,'Le-8422','ground',C08+', layer 21-22',RYC),
 (56,5900,220,'Le-8468','animal bone',C08+', layer 21-22',RYC),
]
TG="Telegin's 1975 excavation (place of Belanovskaya exc. V), Telegin layer "
T1+=[
 (57,5850,150,'Ki-11092','pottery fragment',TG+'8',RYQ),
 (58,6955,160,'Ki-11091','pottery fragment',TG+'10-11',RYQ),
 (59,6810,140,'Ki-11096','pottery fragment',TG+'10-11',RYQ),
 (60,6850,160,'Ki-11095','pottery fragment',TG+'11',RYQ),
 (61,7090,110,'Ki-11090','pottery fragment',TG+'12',RYQ),
 (62,7205,150,'Ki-11093','pottery fragment',TG+'13',''),
 (63,7130,150,'Ki-11094','pottery fragment',TG+'13',RYQ),
]
def pg(n):
    p = 217 if n<=21 else 218 if n<=38 else 219 if n<=55 else 220 if n<=70 else 221 if n<=98 else 222
    return f'p. {p}, Tab. 1, no. {n}'
for n,bp,sd,lab,mat,ctx,cul in T1:
    per = '; '.join(x for x in [cul or 'Neolithic-Eneolithic (no culture given)', ctx] if x)
    add(lab,bp,sd,RY,per,mat,pg(n))
add('GrN-7199',7505,210,'Matveev Kurgan I','Matveev Kurgan culture (Neolithic)','charcoal',pg(64))
add('Le-1217',7180,70,'Matveev Kurgan I','Matveev Kurgan culture (Neolithic); fireplace, depth 1.5 m','charcoal',pg(65))
add('Le-882',5400,200,'Matveev Kurgan II','Matveev Kurgan culture (Neolithic)','charcoal',pg(66))
add('IGAN-726',7460,200,'Samsonovskoe','Neolithic (Rakushechny Yar culture later phase per text p. 205; layer not given for date)','ground',pg(67))
add('IGAN-722',9470,340,'Razdorskoe I','Rakushechny Yar culture early phase per text p. 205 (layer 1); no context in table','',pg(68))
RZ='Rakushechny Yar culture (?), aceramic'
for n,bp,sd,lab,mat,ctx in [
 (69,7490,60,'Ki-15177','charcoal','2008, square A5, layer 12, fireplace'),
 (70,8210,80,'Ki-15178','charcoal','2008, square A7-B7, layer 11, fireplace'),
 (71,7840,80,'Ki-15179','charcoal','2008, layer 11, fireplace'),
 (72,8145,110,'Ua-37000','unknown (? in table); AMS','square A5, layer 12, depth -0.82-0.84'),
 (73,7920,110,'Le-84280a','hot humic acids','2008, square 7, depth 0.58-0.64'),
 (74,8130,100,'Le-84280b','cold humic acids','2008, square 7, depth 0.58-0.64'),
 (75,7640,120,'Le-6873','unknown (? in table)','2003, square AI, depth -1.35/-1.4'),
 (76,7450,100,'Le-6950','unknown (? in table)','2003, square AI'),
 (77,7930,50,'Le-6952','unknown (? in table)','2003, square AI'),
 (78,7850,50,'Le-8814','ground','2009, fireplace 2, square a6, depth 110'),
 (79,7850,50,'Le-8813','ground','2009, northern part of square B4/B5, depth 110'),
 (80,7900,60,'Le-8812','ground','2009, northern part of square B5, depth 110'),
 (81,7470,60,'Le-8811','ground','2009, northern part of square A7, depth 99'),
 (82,7100,100,'SPb-1467','charcoal','2003, square B2, depth -140')]:
    add(lab,bp,sd,'Razdorskaya II',RZ+'; '+ctx,mat,pg(n))
CC='Caspian-Ciscaucasian cultural area'
for n,bp,sd,lab,fp in [(83,6390,100,'Ki-10955',26),(84,6830,110,'Ki-10956',28),(85,6410,70,'Ki-10957',29),(86,6600,90,'Ki-10958',33),(87,6570,100,'Ki-10959',35),(88,4600,100,'Ki-10960',38),(89,6230,100,'Ki-10961',48),(90,5370,110,'Ki-10962',48),(92,2410,100,'Ki-10963',48),(93,5700,100,'Ki-9024',15),(94,6380,100,'Ki-9025',11),(95,7600,110,'Le-6220',27),(96,7150,85,'Le-6221',28),(97,6600,170,'Le-6222',44),(98,6030,120,'Le-6223',29),(99,6770,170,'Le-6224',45),(100,7130,170,'Le-6227',40),(101,6450,160,'Le-6228',47)]:
    page = pg(n) if n!=90 else 'p. 221, Tab. 1, nos. 90-91 (one merged date cell)'
    add(lab,bp,sd,'Kremennaya II',f'{CC}; excavation 1, fireplace {fp}','charcoal',page)
for n,bp,sd,lab,ctx in [(102,7060,190,'Le-6871','excavation 1, square c10e43, bottom of cultural layer'),(103,5540,100,'Le-6868','excavation 1, square c10, bottom of cultural layer'),(104,7440,160,'Le-6956','excavation 1, square c8, bottom of cultural layer'),(105,6582,120,'SPb-1250','excavation 1, No. 214, 593, 60')]:
    add(lab,bp,sd,'Kremennaya III',f'{CC}; '+ctx,'bone',pg(n))
for n,bp,sd,lab,ctx,mat in [(106,8120,120,'Le-6869','excavation 1, square 31, conventional layer 6, No. 1557','bone'),(107,5880,150,'Le-6870','excavation 1, horizon 6-8, depth -0.6-0.8 m','bone'),(108,5160,500,'Le-6872','excavation 1, square 55, bones accumulation 1, depth -0.9 m','bone'),(109,7250,110,'Le-6955','excavation 2, sq. 12, find No. 719, depth -1.1 m','bone'),(110,5420,110,'Le-6954','excavation 2, square 13, layer 9, depth -1.05 m, No. 738','bone'),(111,6030,100,'Le-6953','excavation 2, burial 1','human bone (burial 1)')]:
    add(lab,bp,sd,'Rassypnaya VI',f'{CC}; '+ctx,mat,pg(n))
# Paper 2
AL='Orlovka Neolithic / Cis-Caspian / Khvalynsk Eneolithic multilayer site; date not assigned to a layer in Tab. 1'
for i,(bp,sd,lab,mat) in enumerate([(5875,60,'SPb-1968','animal bone'),(6245,32,'AAR-21891','food crusts'),(6284,100,'SPb-2038','animal bone'),(6318,33,'AAR-21892','animal bone'),(6490,40,'Poz-76004','charcoal'),(6479,70,'SPb-1477','animal bone'),(6360,250,'SPb-1411','charcoal'),(6605,32,'AAR-21893','charcoal'),(6577,80,'SPb-1478','animal bone'),(6654,80,'SPb-1509','animal bone'),(6820,80,'SPb-1510','animal bone'),(6800,40,'Poz-65198','food crusts'),(7284,80,'SPb-2144','humic acids')],1):
    add(lab,bp,sd,'Algay',AL,mat,f'p. 378, Tab. 1, row {i}',S2,R2)
for i,(bp,sd,lab,mat,per) in enumerate([
 (5806,26,'UGAMS-23059','animal bone (kulan)','Khvalynsk Eneolithic, upper layer (text p. 379: kulan bones c. 4725 cal BC)'),
 (5934,100,'SPb-2091','animal bone','probably Cis-Caspian culture, middle layer (text p. 380: c. 5000-4700 cal BC); layer not given in Tab. 1'),
 (7010,110,'SPb-2143','charcoal','probably Orlovka Neolithic, lower layer (text p. 380: c. 6200-5900 cal BC); layer not given in Tab. 1'),
 (7245,60,'SPb-2141','charcoal','probably Orlovka Neolithic, lower layer (text p. 380: c. 6200-5900 cal BC); layer not given in Tab. 1')],14):
    add(lab,bp,sd,'Oroshaemoe I',per,mat,f'p. 378, Tab. 1, row {i}',S2,R2)
cols='labnr,bp,std,lon,lat,site,type,period,material,approximate,precision,source,page,refs'.split(',')
labs=[r['labnr'] for r in rows]; assert len(labs)==len(set(labs))
with open(OUT,'w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(rows)
print(len(rows))
