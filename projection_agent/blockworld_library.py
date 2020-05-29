"""This file contains a number of silhuoettes and sets of baseblocks."""

import numpy as np
import blockworld
import json
from io import open
from os import listdir
from os.path import isfile, join

"""A couple of premade silhuouettes."""

def load_silhuouette_from_Json(path,dimensions=(13,18)):
    """This is to load the premade structures  by Will in block_construction/stimuli/interesting_structures"""
    with open(path,'r') as file:
        data = json.loads(file.read())
        blocks = data['blocks']
    silhuouette = np.zeros(dimensions)
    for b in blocks:
        silhuouette[dimensions[0]-(b['y']+b['height']):dimensions[0]-b['y'],b['x']:b['x']+b['width']] = 1
    return silhuouette

def load_interesting_structure(number,dimensions=(8,8)):
    """Loads a JSON structure from the folder block_construction/stimuli/interesting_structures by number. There are 16."""
    path = "interesting_structures"
    files = [join(path, f) for f in listdir(path) if isfile(join(path, f))]
    return load_silhuouette_from_Json(files[number],dimensions)

def plot_interesting_figures():
    import matplotlib.pyplot as plt
    fig,axes = plt.subplots(4,4)
    i = 0
    for _,axis in np.ndenumerate(axes):
        axis.imshow(load_interesting_structure(i))
        axis.set_title(str(i))
        i += 1
    plt.tight_layout()
    plt.show()

stonehenge_18_13 = np.array([
    [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0.],
    [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0.],
    [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0.],
    [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0.],
    [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0.],
    [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0.],
    [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0.],
    [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0.],
    [0., 0., 0., 0., 0., 0., 0., 1., 1., 1., 1., 0., 0., 0., 0., 0., 0., 0.],
    [0., 0., 0., 0., 0., 0., 0., 1., 0., 0., 1., 0., 0., 0., 0., 0., 0., 0.],
    [0., 0., 0., 0., 0., 0., 0., 1., 0., 0., 1., 0., 0., 0., 0., 0., 0., 0.],
    [0., 0., 0., 0., 0., 0., 0., 1., 0., 0., 1., 0., 0., 0., 0., 0., 0., 0.],
    [0., 0., 0., 0., 0., 0., 0., 1., 0., 0., 1., 0., 0., 0., 0., 0., 0., 0.]])

stonehenge_6_4 = np.array([
    [1., 1., 1., 1.,],
    [1., 1., 1., 1.,],
    [1., 0., 0., 1.,],
    [1., 0., 0., 1.,],
    [1., 0., 0., 1.,],
    [1., 0., 0., 1.,]
])

block = np.array([
    [1., 1., 1., 0.,],
    [1., 1., 1., 0.,],
    [1., 1., 1., 0.,],
    [1., 1., 1., 0.,],

])



stonehenge_3_3 = np.array([
    [1.,1., 1.,],
    [1., 0., 1.,],
    [1., 0., 1.,]
])

t_3_3 =  np.array([
    [1.,1., 1.,],
    [0., 1., 0.,],
    [0., 1., 0.,]
])




"""Base block libraries."""
#The defaults are taken from the silhouette2 study.
bl_silhouette2_default= [
    blockworld.BaseBlock(1,2),
    blockworld.BaseBlock(2,1),
    blockworld.BaseBlock(2,2),
    blockworld.BaseBlock(2,4),
    blockworld.BaseBlock(4,2),
]

#beware, this might never finish, so don't run the agent in an infinte loop
bl_silhouette2_wait= [
    blockworld.BaseBlock(1,2),
    blockworld.BaseBlock(2,1),
    blockworld.BaseBlock(2,2),
    blockworld.BaseBlock(2,4),
    blockworld.BaseBlock(4,2),
    blockworld.BaseBlock(0,0)
]

bl_stonehenge_3_3 = [
    blockworld.BaseBlock(1,2),
    blockworld.BaseBlock(3,1),
] 

bl_stonehenge_6_4 = [
    blockworld.BaseBlock(1,2),
    blockworld.BaseBlock(4,1),
] 