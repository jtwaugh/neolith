import sys, numpy as np
from PIL import Image
from scipy import ndimage
for f in sys.argv[1:]:
    im=np.asarray(Image.open(f).convert('RGB')).astype(int)
    dark=im.sum(2)<120
    lab,n=ndimage.label(dark)
    print(f, im.shape)
    for i,sl in enumerate(ndimage.find_objects(lab),1):
        h=sl[0].stop-sl[0].start; w=sl[1].stop-sl[1].start; a=(lab[sl]==i).sum()
        if 3<=w<=8 and 3<=h<=8 and a/(w*h)>0.55:
            cy,cx=ndimage.center_of_mass(lab==i)
            panel='L' if cx<508 else 'R'
            print(' ',panel, round(cx,1), round(cy,1), round(cx-(0 if cx<508 else 508),1), w,h,a)
