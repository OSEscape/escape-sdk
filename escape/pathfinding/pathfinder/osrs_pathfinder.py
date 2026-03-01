import numpy as np

# ---- RuneLite-style collision bits (your snippet) ----
NW = 0x1
N = 0x2
NE = 0x4
E = 0x8
SE = 0x10
S = 0x20
SW = 0x40
W = 0x80

OBJ = 0x100
FDEC = 0x40000
FLOOR = 0x200000

# You said: anything like floor/full/object => not walkable from all sides
FULL_MASK = OBJ | FDEC | FLOOR

# 8 directions in OSRS BFS expansion order: W, E, S, N, SW, SE, NW, NE
DX8 = np.array([-1, 1, 0, 0, -1, 1, -1, 1], dtype=np.int32)
DY8 = np.array([0, 0, -1, 1, -1, -1, 1, 1], dtype=np.int32)

# "from tile blocks leaving in this dir"
FROM_BIT8 = np.array([W, E, S, N, SW, SE, NW, NE], dtype=np.int32)
# "to tile blocks entering from opposite side"
TO_BIT8 = np.array([E, W, N, S, NE, NW, SE, SW], dtype=np.int32)

# Cardinal dir indices inside the 8-dir arrays
DIR_W = 0
DIR_E = 1
DIR_S = 2
DIR_N = 3

from escape.pathfinding._native import (
    bfs_to_object,
    bfs_to_tile,
    can_step_osrs as _can_step_osrs,
)
