import sys, numpy as np
from PIL import Image
from scipy import ndimage
im=np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(int)
dark=(im.sum(2)<180)
lab,n=ndimage.label(dark)
for i,sl in enumerate(ndimage.find_objects(lab),1):
    h=sl[0].stop-sl[0].start; w=sl[1].stop-sl[1].start
    area=(lab[sl]==i).sum()
    if area>60 and 10<=w<=40 and 10<=h<=40 and area/(w*h)>0.35:
        cy,cx=ndimage.center_of_mass(lab==i)
        print(round(cx/1.5023),round(cy/1.5023),int(cx),int(cy),w,h,area)
