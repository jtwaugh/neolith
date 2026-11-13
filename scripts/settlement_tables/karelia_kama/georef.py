import numpy as np
c=np.cos(np.radians(57))
cp=[('Ladoga',132,993,31.5,61.0),('Onega',291,862,35.656,61.691),('Beloye',433,975,37.633,60.167),
    ('Rybinsk',515,1120,38.433,58.367),('Pezmog',943,569,51.85,61.80),('Samara',1302,1327,50.141,53.203)]
P=np.array([[p[1],p[2],1] for p in cp]); 
# conformal-ish: fit lon,lat from px with affine
X=np.array([p[3]*c for p in cp]); Y=np.array([p[4] for p in cp])
ax,_,_,_=np.linalg.lstsq(P,X,rcond=None); ay,_,_,_=np.linalg.lstsq(P,Y,rcond=None)
def f(px,py):
    v=np.array([px,py,1]); return (v@ax)/c, v@ay
for p in cp:
    lo,la=f(p[1],p[2]); dx=(lo-p[3])*c*111; dy=(la-p[4])*111
    print(p[0],round(lo,2),round(la,2),'resid km',round(dx),round(dy))
import json,sys
sites={'1':(943,569),'2':(1227,522),'3':(1220,545),'4-7':(1308,625),'8':(1284,641),'9':(1316,739),'10':(1359,722),'11':(1371,756),'12':(1369,781),'13':(1346,805),'14':(1332,832),'15':(1334,942),'16':(1183,979),'17':(1120,974),'18':(1269,916),'19':(1274,971),'20':(1284,1003),'21':(1448,1170),'22':(1375,983),'23':(1401,985),'24':(1330,1046),'25':(1218,1165),'26':(1061,1456),'27':(1083,1464),'28':(1078,1276),'29':(1019,1142),'30':(939,1186),'31':(964,1433),'32':(1199,1208)}
for k,(x,y) in sites.items():
    lo,la=f(x,y); print(k,round(lo,2),round(la,2))
