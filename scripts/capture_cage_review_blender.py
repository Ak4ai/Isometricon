"""Capture three review views and restore viewport orientation afterward."""
import bpy
from pathlib import Path
from mathutils import Vector
out=Path(r'C:\Users\Henrique\Documents\GitHub\Isometricon\artifacts\clothing_audit')
spaces=[a.spaces.active for a in bpy.context.screen.areas if a.type=='VIEW_3D']
saved=[(s,s.region_3d.view_rotation.copy(),s.region_3d.view_location.copy(),s.region_3d.view_distance,s.region_3d.view_perspective) for s in spaces]
try:
    for name,direction in [('front',(0,1,0)),('back',(0,-1,0)),('side',(-1,0,0))]:
        for s in spaces:
            s.region_3d.view_rotation=Vector(direction).to_track_quat('-Z','Y')
            s.region_3d.view_location=Vector((0,0,.95));s.region_3d.view_distance=2.5;s.region_3d.view_perspective='ORTHO'
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=1)
        bpy.ops.screen.screenshot(filepath=str(out/f'stage3_{name}.png'))
finally:
    for s,rotation,location,distance,perspective in saved:
        s.region_3d.view_rotation=rotation;s.region_3d.view_location=location;s.region_3d.view_distance=distance;s.region_3d.view_perspective=perspective
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=1)
print('Captured front, back and side; restored original view.')
