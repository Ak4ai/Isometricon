"""Sampled prism/shape guard for the offline clearance solver.

Only acceptance constraints are added: no new transfer field or binding.
Positive initial determinants retain >=10% of their value; initially invalid
samples cannot become worse than their initial determinant. Edge lengths and
inner-to-outer distances stay within [0.5,2] times the initial target values.
These are conservative experimental bounds, not Roblox parameters, and do
not certify injectivity between samples or repair existing inverted cells.
"""
import numpy as np


def determinants(low,high,bary,levels):
    section=(1-levels[:,None,None])*low+levels[:,None,None]*high
    vertical=np.einsum('ni,nij->nj',bary,high-low)
    return np.einsum('ni,ni->n',np.cross(section[:,1]-section[:,0],section[:,2]-section[:,0]),vertical)


class PrismShapeConstraints:
    def __init__(self,x,inverse,source_inner,source_outer,target_inner,active_faces,
                 binding_faces,bary,levels,parity):
        active_faces=np.asarray(active_faces,int)
        samples=[];weights=[];depths=[]
        for b in ([1/3]*3,[1,0,0],[0,1,0],[0,0,1]):
            for t in (0.,.5,1.):
                samples.append(active_faces);weights.append(np.tile(b,(len(active_faces),1)))
                depths.append(np.full(len(active_faces),t))
        samples.append(np.asarray(binding_faces,int));weights.append(np.asarray(bary));depths.append(np.asarray(levels))
        raw_faces=np.concatenate(samples);bary=np.concatenate(weights);levels=np.concatenate(depths)
        source_det=determinants(source_inner[raw_faces],source_outer[raw_faces],bary,levels)
        valid=np.abs(source_det)>1e-12*np.linalg.norm(np.ptp(source_inner,axis=0))**3
        self.sample_faces=inverse[raw_faces[valid]]
        self.low=target_inner[raw_faces[valid]]
        self.bary=bary[valid];self.levels=levels[valid]
        self.sign=parity*np.sign(source_det[valid])
        initial=self.sign*determinants(self.low,x[self.sample_faces],self.bary,self.levels)
        self.floor=np.where(initial>0,.1*initial,initial)
        self.initial_inverted=int(sum(initial<0))
        self.incident=[[] for _ in x]
        for i,f in enumerate(self.sample_faces):
            for v in np.unique(f):self.incident[v].append(i)
        self.incident=[np.asarray(ids,int) for ids in self.incident]
        active_raw=np.unique(active_faces)
        self.raw_by_group=[active_raw[inverse[active_raw]==i] for i in range(len(x))]
        self.target_inner=target_inner
        self.inverse=inverse
        self.initial_gap=np.linalg.norm(x[inverse]-target_inner,axis=1)
        faces=inverse[active_faces]
        edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
        self.edge_length=np.linalg.norm(x[edges[:,0]]-x[edges[:,1]],axis=1)
        self.edges=edges
        self.edges_by_vertex=[np.flatnonzero((edges==i).any(1)) for i in range(len(x))]
        self.epsilon=max(np.linalg.norm(np.ptp(x,axis=0))*1e-10,1e-15)
        self.rejected={'volume':0,'edge_length':0,'thickness':0}

    def accepts(self,x,vertex):
        ids=self.incident[vertex]
        if len(ids):
            det=self.sign[ids]*determinants(self.low[ids],x[self.sample_faces[ids]],self.bary[ids],self.levels[ids])
            if np.any(det<self.floor[ids]):
                self.rejected['volume']+=1;return False
        ids=self.edges_by_vertex[vertex]
        if len(ids):
            e=self.edges[ids];length=np.linalg.norm(x[e[:,0]]-x[e[:,1]],axis=1)
            base=self.edge_length[ids]
            if np.any(length<.5*base-self.epsilon) or np.any(length>2*base+self.epsilon):
                self.rejected['edge_length']+=1;return False
        ids=self.raw_by_group[vertex]
        gap=np.linalg.norm(x[vertex]-self.target_inner[ids],axis=1)
        if np.any(gap<.5*self.initial_gap[ids]-self.epsilon) or np.any(gap>2*self.initial_gap[ids]+self.epsilon):
            self.rejected['thickness']+=1;return False
        return True

    def audit(self):
        return dict(volume_samples=len(self.sample_faces),initial_inverted_samples=self.initial_inverted,
                    rejected_trial_moves=self.rejected,minimum_positive_volume_ratio=.1,
                    edge_and_thickness_bounds=[.5,2.])
