import bpy, time, sys, math
engine = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
def mat(name, rgb, rough=0.5, sss=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Subsurface Weight"].default_value = sss
    return m
# skin-like character: head + eyes on a desk, Zack-D style close-up
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0,0,1.2), segments=64, ring_count=32); h=bpy.context.object
bpy.ops.object.shade_smooth(); h.data.materials.append(mat("skin",(0.85,0.6,0.48),0.45,0.3))
for x in (-0.35,0.35):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.22, location=(x,-0.88,1.35)); e=bpy.context.object; bpy.ops.object.shade_smooth()
    e.data.materials.append(mat("eye",(0.95,0.95,0.95),0.1))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=(x,-1.06,1.35)); p=bpy.context.object; bpy.ops.object.shade_smooth()
    p.data.materials.append(mat("pupil",(0.02,0.02,0.03),0.1))
bpy.ops.mesh.primitive_plane_add(size=30, location=(0,0,0.2)); bpy.context.object.data.materials.append(mat("floor",(0.25,0.35,0.55),0.7))
bpy.ops.object.light_add(type='AREA', location=(-3,-4,5)); L=bpy.context.object; L.data.energy=1500; L.data.size=4
bpy.ops.object.light_add(type='AREA', location=(4,-2,3)); L=bpy.context.object; L.data.energy=500; L.data.size=3
w = bpy.data.worlds.new("w"); sc.world=w; w.use_nodes=True; w.node_tree.nodes["Background"].inputs[0].default_value=(0.4,0.5,0.7,1); w.node_tree.nodes["Background"].inputs[1].default_value=0.6
bpy.ops.object.camera_add(location=(0,-6.5,1.6), rotation=(math.radians(88),0,0)); sc.camera=bpy.context.object; sc.camera.data.lens=50
if engine=="cycles":
    sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=24; sc.cycles.use_denoising=True
    sc.render.resolution_percentage=100
else:
    sc.render.engine='BLENDER_EEVEE'
sc.render.filepath=f"" + __import__("os").path.abspath("out") + f"/test3d_{engine}.png"
t=time.time(); bpy.ops.render.render(write_still=True); print("RENDER", engine, round(time.time()-t,1), "s")
