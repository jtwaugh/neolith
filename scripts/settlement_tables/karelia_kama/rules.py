import sys,numpy as np
from PIL import Image
for f in sys.argv[1:]:
    im=np.asarray(Image.open(f).convert('L'))<128
    H,W=im.shape
    # vertical lines: column with long dark run in table area
    cols=[]
    for x in range(W):
        col=im[150:1480,x]
        # longest run
        best=run=0
        for v in col:
            run=run+1 if v else 0; best=max(best,run)
        if best>300: cols.append((x,best))
    print(f,[c for c in cols])
