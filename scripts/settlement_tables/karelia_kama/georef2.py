import numpy as np, itertools
from scipy.optimize import least_squares
cp=[('Ladoga',132,993,31.5,61.0),('Onega',291,862,35.656,61.691),('Beloye',433,975,37.633,60.167),
    ('Rybinsk',515,1120,38.433,58.367),('Pezmog',943,569,51.85,61.80),('Samara',1302,1327,50.141,53.203)]
def laea(lon,lat,l0,p0):
    l,p,l0,p0=map(np.radians,(lon,lat,l0,p0))
    k=np.sqrt(2/(1+np.sin(p0)*np.sin(p)+np.cos(p0)*np.cos(p)*np.cos(l-l0)))
    return k*np.cos(p)*np.sin(l-l0), k*(np.cos(p0)*np.sin(p)-np.sin(p0)*np.cos(p)*np.cos(l-l0))
px=np.array([[p[1],p[2]] for p in cp],float); ll=np.array([[p[3],p[4]] for p in cp])
def fit(l0,p0):
    x,y=laea(ll[:,0],ll[:,1],l0,p0)
    # similarity: px = s*R*(x,-y)+t
    A=[];b=[]
    for xi,yi,(u,v) in zip(x,y,px):
        A.append([xi,-yi,1,0]);b.append(u); A.append([-yi,-xi,0,1]);b.append(v)  # u=a x - b y + tx ; v = b x + a y + ty with y flipped
    A=np.array(A);b=np.array(b); s,res,_,_=np.linalg.lstsq(A,b,rcond=None)
    pred=A@s; return s, np.sqrt(np.mean((pred-b)**2))
best=None
for l0 in range(0,110,5):
  for p0 in range(40,80,5):
    s,r=fit(l0,p0)
    if best is None or r<best[0]: best=(r,l0,p0,s)
print(best[:3])
for r,l0,p0,s in sorted([(fit(l0,p0)[1],l0,p0,fit(l0,p0)[0]) for l0 in range(-10,110,5) for p0 in range(30,90,5)],key=lambda t:t[0])[:6]:
    print(round(r,1),l0,p0)
from scipy.optimize import brentq, fsolve
sites={'1':(943,569),'2':(1227,522),'3':(1220,545),'4-7':(1308,625),'8':(1284,641),'9':(1316,739),'10':(1359,722),'11':(1371,756),'12':(1369,781),'13':(1346,805),'14':(1332,832),'15':(1334,942),'16':(1183,979),'17':(1120,974),'18':(1269,916),'19':(1274,971),'20':(1284,1003),'21':(1448,1170),'22':(1375,983),'23':(1401,985),'24':(1330,1046),'25':(1218,1165),'26':(1061,1456),'27':(1083,1464),'28':(1078,1276),'29':(1019,1142),'30':(939,1186),'31':(964,1433),'32':(1199,1208)}
for l0,p0 in [(10,52),(15,45)]:
    s,r=fit(l0,p0); a,b,tx,ty=s
    print('proj',l0,p0,'rms px',round(r,1),'km/px',round(6371/np.hypot(a,b),2))
    def topx(lon,lat):
        x,y=laea(lon,lat,l0,p0); return np.array([a*x-b*y+tx, -b*x-a*y+ty])
    for p in cp:
        print(' ',p[0],np.round(topx(p[3],p[4])-np.array([p[1],p[2]]),1))
    print('  Perm px', np.round(topx(56.249,58.014)))
    out={}
    for k,(u,v) in sites.items():
        sol=fsolve(lambda q: topx(q[0],q[1])-np.array([u,v]), [50,57])
        out[k]=sol
    print('  '+'; '.join(f'{k}:{v[0]:.2f},{v[1]:.2f}' for k,v in out.items()))
