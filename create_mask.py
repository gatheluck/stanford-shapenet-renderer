import os
import sys
import glob

import numpy as np
from PIL import Image
import argparse
from tqdm import tqdm

parser = argparse.ArgumentParser(description='Create mask')
parser.add_argument('--dir', type=str, default=None, required=True)

args = parser.parse_args()

# dataset for kaolin dataloader should be like,
#
# dataset/images/02946921/fff09483.../rendering/00.png
#                                              /00_depth.png
#                                              ...
#                                              /rendering_metadata.txt
#                        /bde28170.../
#               /04530566/
#               ...

target_path = os.path.join(args.dir, '**', '??.png')
path_list = glob.glob(target_path, recursive=True)
print(path_list)

if len(path_list)==0:
    raise ValueError('specified directory does not include depth image')

bar = tqdm(range(len(path_list)))
for img_path in path_list:
    img = np.array(Image.open(img_path).split()[-1])
    
    mask = Image.fromarray(img).convert('L')
    mask_path = '_'.join([img_path.rsplit('_', 1)[0], 'mask.png'])
    mask.save(mask_path, cmap='gray')

    bar.update(1)