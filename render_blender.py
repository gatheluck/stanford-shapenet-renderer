# A simple script that uses blender to render views of a single object by rotation the camera around it.
# Also produces depth map at the same time.
#
# Example:
# blender --background --python mytest.py -- --views 10 /path/to/my.obj
#
import os
import sys
import argparse

parser = argparse.ArgumentParser(description='Renders given obj file by rotation a camera around it.')
parser.add_argument('--views', type=int, default=24,
                    help='number of views to be rendered')
parser.add_argument('obj', type=str,
                    help='Path to the obj file to be rendered.')
parser.add_argument('--output_folder', type=str, default='/tmp',
                    help='The path the output will be dumped to.')
parser.add_argument('--scale', type=float, default=1,
                    help='Scaling factor applied to model. Depends on size of mesh.')
parser.add_argument('--remove_doubles', type=bool, default=True,
                    help='Remove double vertices to improve mesh quality.')
parser.add_argument('--edge_split', type=bool, default=True,
                    help='Adds edge split filter.')
parser.add_argument('--depth_scale', type=float, default=1.4,
                    help='Scaling that is applied to depth. Depends on size of mesh. Try out various values until you get a good result. Ignored if format is OPEN_EXR.')
parser.add_argument('--color_depth', type=str, default='8',
                    help='Number of bit per channel used for output. Either 8 or 16.')
parser.add_argument('--format', type=str, default='PNG',
                    help='Format of files generated. Either PNG or OPEN_EXR')
parser.add_argument('--resolution', type=int, default=256, 
                    help='Rendering resolution of each image.')

argv = sys.argv[sys.argv.index("--") + 1:]
args = parser.parse_args(argv)

import bpy

# Set up rendering of depth map.
bpy.context.scene.use_nodes = True
tree = bpy.context.scene.node_tree
links = tree.links

# Add passes for additionally dumping albedo and normals.
bpy.context.scene.render.layers["RenderLayer"].use_pass_normal = True
bpy.context.scene.render.layers["RenderLayer"].use_pass_color = True
bpy.context.scene.render.image_settings.file_format = args.format
bpy.context.scene.render.image_settings.color_depth = args.color_depth

# Clear default nodes
for n in tree.nodes:
    tree.nodes.remove(n)

# Create input render layer node.
render_layers = tree.nodes.new('CompositorNodeRLayers')

# depth
depth_file_output = tree.nodes.new(type="CompositorNodeOutputFile")
depth_file_output.label = 'Depth Output'
if args.format == 'OPEN_EXR':
  links.new(render_layers.outputs['Depth'], depth_file_output.inputs[0])
else:
  # Remap as other types can not represent the full range of depth.
  map = tree.nodes.new(type="CompositorNodeMapValue")
  # Size is chosen kind of arbitrarily, try out until you're satisfied with resulting depth map.
  map.offset = [-0.7]
  map.size = [args.depth_scale]
  map.use_min = True
  map.min = [0]
  links.new(render_layers.outputs['Depth'], map.inputs[0])

  links.new(map.outputs[0], depth_file_output.inputs[0])

# scale
scale_normal = tree.nodes.new(type="CompositorNodeMixRGB")
scale_normal.blend_type = 'MULTIPLY'
# scale_normal.use_alpha = True
scale_normal.inputs[2].default_value = (0.5, 0.5, 0.5, 1)
links.new(render_layers.outputs['Normal'], scale_normal.inputs[1])

# normal
bias_normal = tree.nodes.new(type="CompositorNodeMixRGB")
bias_normal.blend_type = 'ADD'
# bias_normal.use_alpha = True
bias_normal.inputs[2].default_value = (0.5, 0.5, 0.5, 0)
links.new(scale_normal.outputs[0], bias_normal.inputs[1])

normal_file_output = tree.nodes.new(type="CompositorNodeOutputFile")
normal_file_output.label = 'Normal Output'
links.new(bias_normal.outputs[0], normal_file_output.inputs[0])

# albedo
albedo_file_output = tree.nodes.new(type="CompositorNodeOutputFile")
albedo_file_output.label = 'Albedo Output'
links.new(render_layers.outputs['Color'], albedo_file_output.inputs[0])

# Delete default cube
bpy.data.objects['Cube'].select = True
bpy.ops.object.delete()

bpy.ops.import_scene.obj(filepath=args.obj)
for object in bpy.context.scene.objects:
    if object.name in ['Camera', 'Lamp']:
        continue
    bpy.context.scene.objects.active = object
    if args.scale != 1:
        bpy.ops.transform.resize(value=(args.scale,args.scale,args.scale))
        bpy.ops.object.transform_apply(scale=True)
    if args.remove_doubles:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.remove_doubles()
        bpy.ops.object.mode_set(mode='OBJECT')
    if args.edge_split:
        bpy.ops.object.modifier_add(type='EDGE_SPLIT')
        bpy.context.object.modifiers["EdgeSplit"].split_angle = 1.32645
        bpy.ops.object.modifier_apply(apply_as='DATA', modifier="EdgeSplit")

# Make light just directional, disable shadows.
lamp = bpy.data.lamps['Lamp']
lamp.type = 'SUN'
lamp.shadow_method = 'NOSHADOW'
# Possibly disable specular shading:
lamp.use_specular = False

# Add another light source so stuff facing away from light is not completely dark
bpy.ops.object.lamp_add(type='SUN')
lamp2 = bpy.data.lamps['Sun']
lamp2.shadow_method = 'NOSHADOW'
lamp2.use_specular = False
lamp2.energy = 0.015
bpy.data.objects['Sun'].rotation_euler = bpy.data.objects['Lamp'].rotation_euler
bpy.data.objects['Sun'].rotation_euler[0] += 180


def parent_obj_to_camera(b_camera):
    origin = (0, 0, 0)
    b_empty = bpy.data.objects.new("Empty", None)
    b_empty.location = origin
    b_camera.parent = b_empty  # setup parenting

    scn = bpy.context.scene
    scn.objects.link(b_empty)
    scn.objects.active = b_empty
    return b_empty


scene = bpy.context.scene
scene.render.resolution_x = args.resolution
scene.render.resolution_y = args.resolution
scene.render.resolution_percentage = 100
scene.render.alpha_mode = 'TRANSPARENT'
cam = scene.objects['Camera']
cam.location = (0, 1, 0.6)
cam_constraint = cam.constraints.new(type='TRACK_TO')
cam_constraint.track_axis = 'TRACK_NEGATIVE_Z'
cam_constraint.up_axis = 'UP_Y'
b_empty = parent_obj_to_camera(cam)
cam_constraint.target = b_empty

# In ShapeNetCore.v2, .obj file exists under,
# 'ShapeNetCore.v2/02691156/fff513f407e00e85a9ced22d91ad7027/models/model_normalized.obj'
# - class_id of above .obj file should be '02691156'
# - model_id of above .obj file should be 'fff513f407e00e85a9ced22d91ad7027'
class_id = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(args.obj))))
model_id = os.path.basename(os.path.dirname(os.path.dirname(args.obj)))

# dataset for kaolin dataloader should be like,
#
# dataset/images/02946921/fff09483.../rendering/00.png
#                                              /01.png
#                                              /02.png
#                                              ...
#                                              /rendering_metadata.txt
#                        /bde28170.../
#               /04530566/
#               ...

fp = os.path.join(args.output_folder, class_id, model_id, 'rendering')
scene.render.image_settings.file_format = 'PNG'  # set output format to .png

import math

stepsize = 360.0 / args.views
rotation_mode = 'XYZ'

for output_node in [depth_file_output, normal_file_output, albedo_file_output]:
    output_node.base_path = ''

# create rendering_metadata
# each line of 'rendering_metadata.txt' should be includes
# azimuth, elevation, in-plane rotation, distance, the field of view
# ref: https://github.com/chrischoy/3D-R2N2/issues/12
meta_path = os.path.join(fp, 'rendering_metadata.txt')
with open(meta_path, 'w') as f:

    for i in range(0, args.views):
        print("Rotation {}, {}".format((stepsize * i), math.radians(stepsize * i)))
        
        azimuth   = float(stepsize * i)
        elevation = float(math.degrees(math.atan(cam.location[2]/cam.location[1])))
        distance  = float(math.sqrt(sum((xi) ** 2.0 for xi in cam.location)))
        f.write('{} {} {} {} {}\n'.format(azimuth, elevation, 0, distance, 25))

        scene.render.filepath = os.path.join(fp, '{0:02d}'.format(int(i)))
        depth_file_output.file_slots[0].path  = scene.render.filepath + "_depth"
        normal_file_output.file_slots[0].path = scene.render.filepath + "_normal"
        albedo_file_output.file_slots[0].path = scene.render.filepath + "_albedo"

        bpy.ops.render.render(write_still=True)  # render still

        # rename depth, normal, albedo
        # output file name is like '00_albedo_0001.png'
        # change the name from '00_albedo_0001.png' to '00_albedo.png'
        for name in ['depth', 'normal', 'albedo']:
            current_path = scene.render.filepath + '_' + name + '0001.png'
            new_path = scene.render.filepath + '_' + name + '.png'
            os.rename(current_path, new_path)

        b_empty.rotation_euler[2] += math.radians(stepsize)
