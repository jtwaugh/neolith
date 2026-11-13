import sys, numpy as np
from PIL import Image
from scipy import ndimage
im=np.asarray(Image.open(sys.argv[1]).convert('L')).astype(int)
dark=im<60
lab,n=ndimage.label(dark)
s=1398/910
for i,sl in enumerate(ndimage.find_objects(lab),1):
    h=sl[0].stop-sl[0].start; w=sl[1].stop-sl[1].start
    area=(lab[sl]==i).sum()
    if 15<=w<=30 and 15<=h<=30 and area/(w*h)>0.6:
        cy,cx=ndimage.center_of_mass(lab==i)
        print(round(cx/s),round(cy/s),round(cx,1),round(cy,1),w,h,area)
