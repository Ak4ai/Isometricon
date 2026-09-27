from collections import defaultdict
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine

e=RobloxWearEngine(body_type='female')
for label,path in [('office reference','assets/models/clothing/wrap_cages/80307990380242.obj'),
                   ('office outer','assets/models/clothing/wrap_cages/78642992491592.obj'),
                   ('sweater reference','assets/models/clothing/wrap_cages/16184891193.obj'),
                   ('sweater outer','assets/models/clothing/wrap_cages/16184891237.obj')]:
    v,_,uv,_=e.load_obj(str(ROOT/path))
    groups=defaultdict(list)
    for p,t in zip(v,uv):groups[tuple(np.round(t,5))].append(p)
    spreads=np.asarray([np.linalg.norm(np.asarray(pts)-np.mean(pts,axis=0),axis=1).max()
                        for pts in groups.values()])
    print(label,'UVs',len(groups),'max',spreads.max(),'p99',np.quantile(spreads,.99),
          'spread>.001',int((spreads>.001).sum()))
