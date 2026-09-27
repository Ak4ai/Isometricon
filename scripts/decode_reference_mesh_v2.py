"""Decode cached FileMesh 2.00 references for the cage compatibility audit."""
from pathlib import Path
import gzip
import struct

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/'artifacts/clothing_audit/reference_comparison'
for name in ('sweater_reference','pants_reference'):
    data=(DIR/(name+'.mesh')).read_bytes()
    if data.startswith(b'\x1f\x8b'):data=gzip.decompress(data)
    assert data.startswith(b'version 2.00\n')
    header_end=data.index(b'\n')+1
    header_size,vertex_size,face_size,nverts,nfaces=struct.unpack_from('<HBBII',data,header_end)
    assert header_size==12 and vertex_size==40 and face_size==12
    vertex_start=header_end+header_size
    face_start=vertex_start+nverts*vertex_size
    assert len(data)>=face_start+nfaces*face_size
    vertices=[struct.unpack_from('<8f',data,vertex_start+i*vertex_size) for i in range(nverts)]
    faces=[struct.unpack_from('<3I',data,face_start+i*face_size) for i in range(nfaces)]
    assert max(max(f) for f in faces)<nverts
    target=DIR/(name+'.obj')
    with target.open('w',encoding='utf-8') as out:
        for v in vertices:out.write(f'v {v[0]:.9f} {v[1]:.9f} {v[2]:.9f}\n')
        for v in vertices:out.write(f'vt {v[6]:.9f} {1-v[7]:.9f}\n')
        for a,b,c in faces:out.write(f'f {a+1}/{a+1} {b+1}/{b+1} {c+1}/{c+1}\n')
    print(name,nverts,nfaces,len(data)-face_start-nfaces*face_size)
