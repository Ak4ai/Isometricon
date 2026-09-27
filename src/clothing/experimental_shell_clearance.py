"""Offline body-union collision constraints for an already transferred shell.

This is our diagnostic projection solver, not a Roblox algorithm. It preserves
existing coincident shell samples and prevents NEW surface reversals relative
to the input shell. It cannot repair an already folded cage or certify global
injectivity. Body components must be closed and consistently wound.
"""
import numpy as np


class ClosedBodyUnion:
    def __init__(self, vertices, faces, components):
        self.parts = []
        triangles, normals = [], []
        for ids in components:
            tri = np.asarray(vertices, float)[np.asarray(faces, int)[ids]]
            center = tri.mean(axis=(0, 1))
            volume = np.einsum('ij,ij->i', tri[:,0]-center,
                               np.cross(tri[:,1]-center, tri[:,2]-center)).sum()
            if abs(volume) < 1e-15:
                raise ValueError('Closed body component has no oriented volume')
            normal = np.cross(tri[:,1]-tri[:,0], tri[:,2]-tri[:,0])
            length = np.linalg.norm(normal, axis=1)
            normal = np.sign(volume)*normal/np.maximum(length[:,None], 1e-30)
            self.parts.append((tri, tri.min(axis=(0,1)), tri.max(axis=(0,1))))
            triangles.append(tri[length>1e-15]); normals.append(normal[length>1e-15])
        if not triangles:
            raise ValueError('No closed body components')
        self.triangles = np.concatenate(triangles)
        self.normals = np.concatenate(normals)

    def contains(self, points):
        points = np.asarray(points, float)
        inside = np.zeros(len(points), bool)
        for tri, low, high in self.parts:
            ids = np.flatnonzero((points>low).all(1)&(points<high).all(1)&~inside)
            for start in range(0, len(ids), 128):
                selected = ids[start:start+128]
                a,b,c = [tri[None,:,k]-points[selected,None,:] for k in range(3)]
                la,lb,lc = [np.linalg.norm(v, axis=2) for v in (a,b,c)]
                numerator = np.einsum('bfi,bfi->bf', a, np.cross(b,c))
                denominator = (la*lb*lc+np.einsum('bfi,bfi->bf',a,b)*lc
                    +np.einsum('bfi,bfi->bf',b,c)*la+np.einsum('bfi,bfi->bf',c,a)*lb)
                inside[selected] |= np.abs(np.arctan2(numerator,denominator).sum(1))>np.pi
        return inside

    def exterior_targets(self, points, margin):
        """Nearest valid candidate among triangle projections on the body union.

        Reject a boundary of one part if its outward offset enters another.
        Search all triangles if necessary; no fixed nearest-neighbor cutoff.
        Candidate projections are an approximation to exact union distance.
        """
        tri = self.triangles
        a,b,c = tri[:,0],tri[:,1],tri[:,2]
        ab,ac = b-a,c-a
        n = self.normals
        aa,cc,abac = (np.einsum('ij,ij->i',ab,ab), np.einsum('ij,ij->i',ac,ac),
                      np.einsum('ij,ij->i',ab,ac))
        denominator = np.maximum(aa*cc-abac**2, 1e-30)
        result = np.empty_like(points)
        for index,p in enumerate(points):
            ap = p-a
            q = p - np.einsum('ij,ij->i',ap,n)[:,None]*n
            v = q-a
            vab,vac = np.einsum('ij,ij->i',v,ab),np.einsum('ij,ij->i',v,ac)
            u = (cc*vab-abac*vac)/denominator
            w = (aa*vac-abac*vab)/denominator
            distance = np.where((u>=0)&(w>=0)&(u+w<=1),np.linalg.norm(q-p,axis=1),np.inf)
            for x,y in ((a,b),(b,c),(c,a)):
                edge = y-x
                t = np.clip(np.einsum('ij,ij->i',p-x,edge)/np.maximum(np.einsum('ij,ij->i',edge,edge),1e-30),0,1)
                candidate = x+t[:,None]*edge
                d = np.linalg.norm(candidate-p,axis=1)
                replace = d<distance
                q[replace]=candidate[replace];distance[replace]=d[replace]
            order = np.argsort(distance)
            found = False
            for start in range(0,len(order),32):
                ids = order[start:start+32]
                candidates = q[ids]+margin*n[ids]
                valid = ~self.contains(candidates)
                if valid.any():
                    result[index]=candidates[np.flatnonzero(valid)[0]]
                    found=True
                    break
            if not found:
                raise ValueError('No exposed body boundary candidate')
        return result


def _normals(x,f):
    return np.cross(x[f[:,1]]-x[f[:,0]],x[f[:,2]]-x[f[:,0]])


def project_shell_clearance(source_outer, shell, faces, active_faces, body,
                            *, margin, iterations=20, local_steps=True, constraint_factory=None,
                            linked_samples=None):
    """Sampled collision projection with fixed topology and an orientation guard.

    Surface samples: active vertices, edge midpoints, face centroids. Updates
    minimize each sample displacement in its three barycentric variables;
    Jacobi smoothing distributes corrections over cage adjacency. No asset or
    clothing category enters the solver. An unsuccessful solve is reported.
    """
    shell = np.asarray(shell, float)
    keys = np.column_stack((np.round(source_outer,8),np.round(shell,10)))
    _,first,inverse = np.unique(keys, axis=0, return_index=True,return_inverse=True)
    x = shell[first].copy()
    if constraint_factory is not None and not local_steps:
        raise ValueError('Additional constraints require local steps')
    constraint = constraint_factory(x,inverse) if constraint_factory is not None else None
    f = inverse[np.asarray(faces, int)]
    _,unique = np.unique(np.sort(f,axis=1),axis=0,return_index=True)
    f = f[unique]
    active = inverse[np.asarray(active_faces, int)]
    linked_ids = linked_weights = linked_offsets = None
    if linked_samples is not None:
        linked_ids = inverse[np.asarray(linked_samples['indices'], int)]
        linked_weights = np.asarray(linked_samples['weights'], float)
        linked_offsets = np.asarray(linked_samples['offsets'], float)
        if (linked_ids.ndim != 2 or linked_weights.shape != linked_ids.shape or
                linked_offsets.shape != (len(linked_ids), 3) or
                not np.isfinite(linked_weights).all() or not np.isfinite(linked_offsets).all()):
            raise ValueError('Linked samples require finite NxK indices/weights and Nx3 offsets')
        if np.any(linked_ids < 0) or np.any(linked_ids >= len(x)):
            raise ValueError('Linked sample index is outside the deduplicated shell')
    edges = np.unique(np.sort(np.concatenate((active[:,[0,1]],active[:,[1,2]],active[:,[2,0]])),axis=1),axis=0)
    vertices = np.unique(active)
    sample_ids = np.concatenate((np.repeat(vertices[:,None],3,axis=1),
                                 np.column_stack((edges,edges[:,1])),active))
    bary = np.concatenate((np.tile([1.,0,0],(len(vertices),1)),
                           np.tile([.5,.5,0],(len(edges),1)),np.full((len(active),3),1/3)))
    base_n = _normals(x,f)
    base_area = np.linalg.norm(base_n,axis=1)
    good = base_area>max(np.linalg.norm(np.ptp(x,axis=0))**2*1e-10,1e-16)
    graph = np.unique(np.sort(np.concatenate((f[:,[0,1]],f[:,[1,2]],f[:,[2,0]])),axis=1),axis=0)
    graph = graph[graph[:,0]!=graph[:,1]]
    degree = np.bincount(graph.ravel(),minlength=len(x))
    incident=[[] for _ in x]
    for fid,triangle in enumerate(f):
        if good[fid]:
            for vertex in np.unique(triangle):incident[vertex].append(fid)
    history = []
    reason = 'iteration_limit'
    for iteration in range(iterations):
        shell_samples = np.einsum('ni,nij->nj',bary,x[sample_ids])
        linked_positions = (linked_offsets + np.einsum('nk,nkj->nj',linked_weights,
                                                        x[linked_ids])) if linked_ids is not None else np.empty((0,3))
        samples = np.vstack((shell_samples, linked_positions))
        hit = body.contains(samples)
        if not hit.any():
            reason='sampled_surface_clear';break
        goals = body.exterior_targets(samples[hit],margin)
        correction = goals-samples[hit]
        row = dict(iteration=iteration,penetrating_samples=int(hit.sum()),
                   penetrating_shell_samples=int(hit[:len(shell_samples)].sum()),
                   penetrating_linked_samples=int(hit[len(shell_samples):].sum()),
                   maximum_correction=float(np.linalg.norm(correction,axis=1).max()))
        history.append(row)
        rhs,counts = np.zeros_like(x),np.zeros(len(x))
        shell_hit = hit[:len(shell_samples)]
        shell_correction = correction[:int(shell_hit.sum())]
        b = bary[shell_hit];ids = sample_ids[shell_hit]
        for corner in range(3):
            weight = b[:,corner]
            nonzero = weight>0
            np.add.at(rhs,ids[nonzero,corner],shell_correction[nonzero]*
                      (weight[nonzero]/np.sum(b[nonzero]**2,axis=1))[:,None])
            np.add.at(counts,ids[nonzero,corner],1)
        linked_hit = hit[len(shell_samples):]
        linked_correction = correction[int(shell_hit.sum()):]
        unmovable_linked = 0
        if linked_ids is not None and linked_hit.any():
            coefficients = linked_weights[linked_hit]
            denominator = np.sum(coefficients**2,axis=1)
            movable = denominator > 1e-12
            unmovable_linked = int(sum(~movable))
            if movable.any():
                ids = linked_ids[linked_hit][movable]
                weights = coefficients[movable] / denominator[movable,None]
                linked_correction_move = linked_correction[movable]
                for corner in range(ids.shape[1]):
                    active_corner = np.abs(weights[:,corner]) > 1e-12
                    np.add.at(rhs,ids[active_corner,corner],
                              linked_correction_move[active_corner] * weights[active_corner,corner,None])
                    np.add.at(counts,ids[active_corner,corner],1)
        row['unmovable_linked_samples'] = unmovable_linked
        rhs /= np.maximum(counts[:,None],1)
        delta = rhs.copy()
        for _ in range(8):
            neighbors = np.zeros_like(x)
            np.add.at(neighbors,graph[:,0],delta[graph[:,1]])
            np.add.at(neighbors,graph[:,1],delta[graph[:,0]])
            delta = (rhs+.25*neighbors)/(1+.25*degree[:,None])
        if local_steps:
            # One binding constraint must not freeze unrelated cage regions.
            # Sequential block-coordinate line searches keep every incident
            # triangle feasible as the remaining variables continue moving.
            maximum_move=0.; blocked=0; limiting=set()
            for vertex in np.argsort(-np.linalg.norm(delta,axis=1),kind='stable'):
                size=float(np.linalg.norm(delta[vertex]))
                if size<margin*.01:continue
                ids=np.asarray(incident[vertex],int)
                prior=x[vertex].copy();step=1.
                for _ in range(18):
                    x[vertex]=prior+step*delta[vertex]
                    n=_normals(x,f[ids])
                    valid=(np.einsum('ij,ij->i',n,base_n[ids])>0)&(np.linalg.norm(n,axis=1)>=.25*base_area[ids])
                    if valid.all() and (constraint is None or constraint.accepts(x,vertex)):break
                    limiting.update(unique[ids[~valid]].tolist())
                    step*=.5
                else:
                    x[vertex]=prior;step=0.;blocked+=1
                maximum_move=max(maximum_move,step*size)
            row.update(maximum_move=maximum_move,blocked_vertices=blocked,
                       limiting_original_face_ids=sorted(limiting))
            if maximum_move<margin*.01:
                reason='orientation_guard_stalled';break
            continue
        step=1.
        for _ in range(18):
            proposal=x+step*delta
            n=_normals(proposal,f)
            valid=(np.einsum('ij,ij->i',n,base_n)>0)&(np.linalg.norm(n,axis=1)>=.25*base_area)
            if np.all(valid[good]):break
            step*=.5
        else:
            reason='orientation_guard_blocked';row['step']=0.;break
        row['step']=step
        x=proposal
        if np.max(np.linalg.norm(step*delta,axis=1))<margin*.01:
            reason='orientation_guard_stalled';break
    shell_samples = np.einsum('ni,nij->nj',bary,x[sample_ids])
    linked_positions = (linked_offsets + np.einsum('nk,nkj->nj',linked_weights,
                                                    x[linked_ids])) if linked_ids is not None else np.empty((0,3))
    remaining_shell=int(body.contains(shell_samples).sum())
    remaining_linked=int(body.contains(linked_positions).sum()) if len(linked_positions) else 0
    return x[inverse],dict(reason=reason,remaining_penetrating_samples=remaining_shell+remaining_linked,
        remaining_penetrating_shell_samples=remaining_shell,
        remaining_penetrating_linked_samples=remaining_linked,
        samples=len(sample_ids)+(len(linked_ids) if linked_ids is not None else 0),history=history,margin=margin,
        max_vertex_displacement=float(np.linalg.norm(x-shell[first],axis=1).max()),
        local_steps=local_steps,
        linked_sample_count=int(len(linked_ids)) if linked_ids is not None else 0,
        additional_constraints=constraint.audit() if constraint is not None else None,
        input_valid_faces=int(good.sum()),input_degenerate_faces=int((~good).sum()),
        note='Sampled surface constraints only; no volume/extrapolation guarantee')
