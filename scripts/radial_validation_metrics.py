"""Offline geometric measurements; no renderer visibility used as penetration."""
import numpy as np


def normals(vertices, faces):
    p = vertices[faces]
    return np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])


def distortion(source, fitted, faces, scale, expected_vertex_frames=None, parity=1):
    edges = np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
    lengths = [np.linalg.norm(v[edges[:,0]]-v[edges[:,1]],axis=1) for v in (source,fitted)]
    # Retain historical 0.01 native-unit mask for comparison; also report all nonzero edges.
    result = {}
    for label, mask in [('historical_length_mask',lengths[0]>=.01),('all_nondegenerate',lengths[0]>1e-8)]:
        ratios = lengths[1][mask]/(lengths[0][mask]*scale)
        result[label] = dict(count=int(mask.sum()),over_3=int(sum(ratios>3)),under_third=int(sum(ratios<1/3)),
                            quantiles=np.quantile(ratios,[0,.01,.5,.99,1]).tolist())
    n0,n1 = normals(source,faces),normals(fitted,faces)
    a0,a1 = np.linalg.norm(n0,axis=1),np.linalg.norm(n1,axis=1)
    valid = a0>1e-9
    ratios = a1[valid]/(a0[valid]*scale**2)
    result['area'] = dict(count=int(sum(valid)),under_tenth=int(sum(ratios<.1)),over_nine=int(sum(ratios>9)),
                          quantiles=np.quantile(ratios,[0,.01,.5,.99,1]).tolist())
    if expected_vertex_frames is not None:
        frame = expected_vertex_frames[faces].mean(1)
        expected = parity * np.einsum('ni,nij->nj',n0,frame)
        result['orientation_disagreements_with_inner_frame'] = int(sum(valid & (np.einsum('ij,ij->i',expected,n1)<0)))
    return result


def seam_report(source, target, uv_ids):
    """Separate identical UV copies from coincident positions on different charts.

    Different-UV coincidences are candidates, NOT automatically authored seams.
    """
    result = {}
    for label, keys in [('same_uv',np.asarray(uv_ids)[:,None]),('coincident_outer',np.round(source,5))]:
        _, inverse, counts = np.unique(keys,axis=0,return_inverse=True,return_counts=True)
        sums = np.zeros((len(counts),3))
        np.add.at(sums,inverse,target)
        distance = np.linalg.norm(target-sums[inverse]/counts[inverse,None],axis=1)
        spreads = np.zeros(len(counts))
        np.maximum.at(spreads,inverse,distance)
        spreads = spreads[counts>1]
        result[label] = dict(groups=len(spreads),max_radius=float(spreads.max(initial=0)),
                            over_1e_minus_5=int(sum(spreads>1e-5)),over_1e_minus_3=int(sum(spreads>1e-3)))
    return result


def body_components(vertices,faces):
    # Keep touching body parts separate: global position welding falsely makes
    # their shared joint rings nonmanifold. OBJ/FBX part indices remain distinct.
    parent=np.arange(len(vertices))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]; i=parent[i]
        return i
    for a,b,c in faces:
        parent[root(b)]=root(a); parent[root(c)]=root(a)
    labels=np.array([root(f[0]) for f in faces])
    groups=[]
    for label in np.unique(labels):
        ids=np.flatnonzero(labels==label)
        raw=faces[ids]
        _,inv=np.unique(np.round(vertices[raw.ravel()],7),axis=0,return_inverse=True)
        f=inv.reshape(-1,3)
        edges=np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1)
        _,counts=np.unique(edges,axis=0,return_counts=True)
        groups.append((ids,bool(np.all(counts==2))))
    return groups


def body_penetration(points,vertices,faces,return_samples=False):
    """Union of |winding| > .5 for closed connected body components.

    Open components are reported separately and never silently closed. Minimum
    distance is exact point/triangle distance; surface samples are finite.
    """
    tri=vertices[faces]
    inside=np.zeros(len(points),dtype=bool)
    open_inside=np.zeros(len(points),dtype=bool)
    groups=body_components(vertices,faces)
    minimum=np.full(len(points),np.inf)
    for start in range(0,len(points),128):
        p=points[start:start+128,None,:]
        a,b,c=tri[:,0][None]-p,tri[:,1][None]-p,tri[:,2][None]-p
        la,lb,lc=[np.linalg.norm(x,axis=2) for x in (a,b,c)]
        numerator=np.einsum('bfi,bfi->bf',a,np.cross(b,c))
        denominator=la*lb*lc+np.einsum('bfi,bfi->bf',a,b)*lc+np.einsum('bfi,bfi->bf',b,c)*la+np.einsum('bfi,bfi->bf',c,a)*lb
        angles=2*np.arctan2(numerator,denominator)
        for ids,closed in groups:
            hit=np.abs(angles[:,ids].sum(1))/(4*np.pi)>.5
            (inside if closed else open_inside)[start:start+len(p)] |= hit
        ab=tri[:,1]-tri[:,0]; ac=tri[:,2]-tri[:,0]
        n=np.cross(ab,ac); nn=np.einsum('fi,fi->f',n,n)
        d=np.einsum('bfi,fi->bf',a,n)
        projected=-a+d[:,:,None]*n/np.maximum(nn[None,:,None],1e-30)
        aa=np.einsum('fi,fi->f',ab,ab); cc=np.einsum('fi,fi->f',ac,ac); abac=np.einsum('fi,fi->f',ab,ac)
        pab=np.einsum('bfi,fi->bf',projected,ab); pac=np.einsum('bfi,fi->bf',projected,ac)
        denom=np.maximum(aa*cc-abac**2,1e-30)
        u=(cc*pab-abac*pac)/denom; v=(aa*pac-abac*pab)/denom
        dist=np.where((u>=0)&(v>=0)&(u+v<=1)&(nn>1e-24),d*d/np.maximum(nn,1e-30),np.inf)
        for x,y in ((a,b),(b,c),(c,a)):
            direction=y-x
            t=np.clip(-np.einsum('bfi,bfi->bf',x,direction)/np.maximum(np.einsum('bfi,bfi->bf',direction,direction),1e-30),0,1)
            delta=x+t[:,:,None]*direction
            dist=np.minimum(dist,np.einsum('bfi,bfi->bf',delta,delta))
        minimum[start:start+len(p)]=np.sqrt(dist.min(1))
    height=float(np.ptp(vertices[:,2])); tolerance=height*1e-4
    mask=inside&(minimum>tolerance)
    report=dict(samples=len(points),closed_components=sum(c for _,c in groups),open_components=sum(not c for _,c in groups),
                penetrating_samples=int(mask.sum()),penetrating_fraction=float(mask.mean()),
                depth_max_over_body_height=float(minimum[mask].max(initial=0)/height),
                depth_p95_over_body_height=float(np.quantile(minimum[mask],.95)/height) if mask.any() else 0,
                open_component_inside_candidates=int(sum(open_inside)),surface_tolerance_over_height=1e-4)
    return (report,mask,minimum) if return_samples else report


def prism_jacobians(inner,outer,target_inner,target_outer,faces,parity):
    """Signed volumetric Jacobians at 4 barycentric locations x 3 layer depths.

    Counts inversion relative to source and explicit frame parity. Source
    degeneracies are excluded; this is a sample audit, not injectivity proof.
    """
    i,o,ti,to=[v[faces] for v in (inner,outer,target_inner,target_outer)]
    ratios=[]; excluded=0
    source_epsilon=1e-12*max(float(np.linalg.norm(np.ptp(inner,axis=0)))**3,1e-30)
    for bary in ([1/3]*3,[1,0,0],[0,1,0],[0,0,1]):
        for level in (0.,.5,1.):
            dets=[]
            for low,high in ((i,o),(ti,to)):
                s=(1-level)*low+level*high
                vertical=np.einsum('k,fkj->fj',bary,high-low)
                dets.append(np.einsum('fi,fi->f',np.cross(s[:,1]-s[:,0],s[:,2]-s[:,0]),vertical))
            valid=np.abs(dets[0])>source_epsilon
            excluded+=int(sum(~valid))
            ratios.extend((parity*dets[1][valid]/dets[0][valid]).tolist())
    values=np.array(ratios)
    return dict(samples=len(values),source_degenerate_samples=excluded,inverted_samples=int(sum(values<0)),
                inverted_fraction=float(np.mean(values<0)))
