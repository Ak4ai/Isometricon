import struct
import lz4.block

with open('assets/models/teste.rbxm', 'rb') as f:
    data = f.read()

pos = 32
chunks = []
while pos < len(data):
    if pos + 16 > len(data):
        break
    tag = data[pos:pos+4].decode('ascii', errors='ignore')
    comp_len, decomp_len, res = struct.unpack('<III', data[pos+4:pos+16])
    chunk_data = data[pos+16:pos+16+comp_len]
    pos += 16 + comp_len
    decomp = lz4.block.decompress(chunk_data, uncompressed_size=decomp_len) if comp_len > 0 else chunk_data
    chunks.append((tag, decomp))

def decode_ints(b, count):
    res = []
    accum = 0
    for i in range(count):
        b0 = b[i]
        b1 = b[count + i]
        b2 = b[2*count + i]
        b3 = b[3*count + i]
        v = (b0 << 24) | (b1 << 16) | (b2 << 8) | b3
        val = (v >> 1) if (v % 2 == 0) else (-(v + 1) >> 1)
        accum += val
        res.append(accum)
    return res

def decode_strings(b, count):
    res = []
    pos = 0
    for _ in range(count):
        slen = struct.unpack('<I', b[pos:pos+4])[0]
        pos += 4
        s = b[pos:pos+slen].decode('utf-8', errors='ignore')
        pos += slen
        res.append(s)
    return res

def decode_rbx_floats(data, count):
    res = []
    for i in range(count):
        b0 = data[i]
        b1 = data[count + i]
        b2 = data[2*count + i]
        b3 = data[3*count + i]
        u = (b0 << 24) | (b1 << 16) | (b2 << 8) | b3
        val_u = (u >> 1) | ((u & 1) << 31)
        f = struct.unpack('>f', struct.pack('>I', val_u))[0]
        res.append(f)
    return res

inst_classes = {}
inst_ids_by_class = {}
for tag, p in chunks:
    if tag == 'INST':
        cid = struct.unpack('<I', p[:4])[0]
        nlen = struct.unpack('<I', p[4:8])[0]
        cname = p[8:8+nlen].decode('ascii', errors='ignore')
        off = 8 + nlen
        count = struct.unpack('<I', p[off+1:off+5])[0]
        ids = decode_ints(p[off+5:off+5+count*4], count)
        inst_classes[cid] = cname
        inst_ids_by_class[cid] = ids

names = []
xs, ys, zs = [], [], []
for tag, p in chunks:
    if tag == 'PROP' and len(p) > 8:
        cid = struct.unpack('<I', p[:4])[0]
        plen = struct.unpack('<I', p[4:8])[0]
        pname = p[8:8+plen].decode('ascii', errors='ignore')
        cname = inst_classes.get(cid, '')
        if cname == 'MeshPart':
            if pname == 'Name':
                names = decode_strings(p[9+plen:], len(inst_ids_by_class[cid]))
            elif pname == 'CFrame':
                raw = p[9+plen+15:]
                xs = decode_rbx_floats(raw[0:60], 15)
                ys = decode_rbx_floats(raw[60:120], 15)
                zs = decode_rbx_floats(raw[120:180], 15)

rbxm_parts = {}
for i in range(15):
    rbxm_parts[names[i]] = (xs[i], ys[i], zs[i])

# Load teste.obj groups
obj_groups = {}
with open('assets/models/teste.obj', 'r') as f:
    cg = None
    for line in f:
        if line.startswith('g '):
            cg = line.split()[1]
            obj_groups[cg] = []
        elif line.startswith('v ') and cg:
            obj_groups[cg].append([float(x) for x in line.split()[1:4]])

obj_centers = {}
for g, verts in obj_groups.items():
    vx = [v[0] for v in verts]
    vy = [v[1] for v in verts]
    vz = [v[2] for v in verts]
    obj_centers[g] = ((min(vx)+max(vx))/2, (min(vy)+max(vy))/2, (min(vz)+max(vz))/2)

print("RBXM parts absolute positions:")
for n, p in sorted(rbxm_parts.items()):
    print(f"  {n:15}: ({p[0]:.3f}, {p[1]:.3f}, {p[2]:.3f})")

print("\nOBJ groups absolute centers:")
for g, c in sorted(obj_centers.items()):
    print(f"  {g:15}: ({c[0]:.3f}, {c[1]:.3f}, {c[2]:.3f})")
