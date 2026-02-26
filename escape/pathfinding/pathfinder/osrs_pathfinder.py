import numpy as np
from numba import njit



# ---- RuneLite-style collision bits (your snippet) ----
NW = 0x1
N  = 0x2
NE = 0x4
E  = 0x8
SE = 0x10
S  = 0x20
SW = 0x40
W  = 0x80

OBJ   = 0x100
FDEC  = 0x40000
FLOOR = 0x200000

# You said: anything like floor/full/object => not walkable from all sides
FULL_MASK = OBJ | FDEC | FLOOR

# 8 directions in OSRS BFS expansion order: W, E, S, N, SW, SE, NW, NE
DX8 = np.array([-1, 1, 0, 0, -1, 1, -1, 1], dtype=np.int32)
DY8 = np.array([ 0, 0,-1, 1, -1,-1,  1, 1], dtype=np.int32)

# "from tile blocks leaving in this dir"
FROM_BIT8 = np.array([W, E, S, N, SW, SE, NW, NE], dtype=np.int32)
# "to tile blocks entering from opposite side"
TO_BIT8   = np.array([E, W, N, S, NE, NW, SE, SW], dtype=np.int32)

# Cardinal dir indices inside the 8-dir arrays
DIR_W = 0
DIR_E = 1
DIR_S = 2
DIR_N = 3


@njit(cache=True)
def _in_bounds(x: int, y: int, w: int, h: int) -> bool:
    return 0 <= x < w and 0 <= y < h


@njit(cache=True)
def _is_walkable(tile_flags: int) -> bool:
    return (tile_flags & FULL_MASK) == 0


@njit(cache=True)
def _can_step_cardinal(flags: np.ndarray, w: int, h: int, x: int, y: int, di: int) -> bool:
    nx = x + DX8[di]
    ny = y + DY8[di]
    if not _in_bounds(nx, ny, w, h):
        return False

    to_flags = int(flags[ny, nx])
    if not _is_walkable(to_flags):
        return False

    from_flags = flags[y, x]
    if (from_flags & FROM_BIT8[di]) != 0:
        return False
    if (to_flags & TO_BIT8[di]) != 0:
        return False

    return True


@njit(cache=True)
def _can_step_osrs(flags: np.ndarray, w: int, h: int, x: int, y: int, di: int) -> bool:
    """
    OSRS-style 8-way step legality:
      - destination must be walkable
      - directional bits must allow crossing (both sides)
      - diagonal step requires both adjacent cardinal steps legal too
    """
    if not _can_step_cardinal(flags, w, h, x, y, di):
        return False

    dx = DX8[di]
    dy = DY8[di]
    if dx == 0 or dy == 0:
        return True

    # Diagonal: require both adjacent cardinals legal
    if not _can_step_cardinal(flags, w, h, x, y, DIR_E if dx == 1 else DIR_W):
        return False
    if not _can_step_cardinal(flags, w, h, x, y, DIR_N if dy == 1 else DIR_S):
        return False

    return True


@njit(cache=True)
def _reconstruct(parent: np.ndarray, end_i: int, w: int):
    maxn = parent.size
    px = np.empty(maxn, dtype=np.int32)
    py = np.empty(maxn, dtype=np.int32)

    n = 0
    cur = end_i
    while cur != -1:
        px[n] = cur % w
        py[n] = cur // w
        n += 1
        cur = parent[cur]

    # reverse in-place
    for i in range(n // 2):
        j = n - 1 - i
        tx = px[i]
        ty = py[i]
        px[i] = px[j]
        py[i] = py[j]
        px[j] = tx
        py[j] = ty

    return px, py, n


@njit(cache=True)
def bfs_to_tile(flags: np.ndarray, sx: int, sy: int, gx: int, gy: int):
    """
    BFS shortest path using OSRS step rules.
    flags: np.int32[h,w]
    Returns (px, py, n). If no path: n=0 and px/py empty.
    """
    h, w = flags.shape

    if not _in_bounds(sx, sy, w, h):
        return np.empty(0, np.int32), np.empty(0, np.int32), 0
    if not _is_walkable(flags[sy, sx]):
        return np.empty(0, np.int32), np.empty(0, np.int32), 0
    if sx == gx and sy == gy:
        return np.array([sx], np.int32), np.array([sy], np.int32), 1

    maxn = w * h
    qx = np.empty(maxn, dtype=np.int32)
    qy = np.empty(maxn, dtype=np.int32)
    parent = np.full(maxn, -1, dtype=np.int32)
    visited = np.zeros(maxn, dtype=np.uint8)

    def pack(x, y):
        return y * w + x

    si = pack(sx, sy)
    visited[si] = 1
    qx[0] = sx
    qy[0] = sy
    qs = 0
    qe = 1

    while qs < qe:
        cx = qx[qs]
        cy = qy[qs]
        qs += 1
        ci = pack(cx, cy)

        for di in range(8):
            nx = cx + DX8[di]
            ny = cy + DY8[di]
            if not _in_bounds(nx, ny, w, h):
                continue
            ni = pack(nx, ny)
            if visited[ni] != 0:
                continue
            if not _can_step_osrs(flags, w, h, cx, cy, di):
                continue

            visited[ni] = 1
            parent[ni] = ci

            if nx == gx and ny == gy:
                px, py, n = _reconstruct(parent, ni, w)
                return px[:n].copy(), py[:n].copy(), n

            qx[qe] = nx
            qy[qe] = ny
            qe += 1

    return np.empty(0, np.int32), np.empty(0, np.int32), 0


@njit(cache=True)
def _rect_contains(x: int, y: int, rx0: int, ry0: int, rx1: int, ry1: int) -> bool:
    return (rx0 <= x <= rx1) and (ry0 <= y <= ry1)


@njit(cache=True)
def _edge_open_for_approach(flags: np.ndarray, sx: int, sy: int, bx: int, by: int) -> bool:
    """
    Boundary check between stand tile (sx,sy) and border tile (bx,by).
    Supports cardinal and diagonal adjacency. Does NOT require border tile walkable.
    """
    dx = bx - sx
    dy = by - sy

    if dx == 0 and dy == 1:
        di = DIR_N
    elif dx == 1 and dy == 0:
        di = DIR_E
    elif dx == 0 and dy == -1:
        di = DIR_S
    elif dx == -1 and dy == 0:
        di = DIR_W
    elif dx == -1 and dy == -1:
        di = 4  # SW
    elif dx == 1 and dy == -1:
        di = 5  # SE
    elif dx == -1 and dy == 1:
        di = 6  # NW
    elif dx == 1 and dy == 1:
        di = 7  # NE
    else:
        return False

    sf = flags[sy, sx]
    bf = flags[by, bx]

    if (sf & FROM_BIT8[di]) != 0:
        return False
    if (bf & TO_BIT8[di]) != 0:
        return False

    return True


@njit(cache=True)
def _is_object_goal(flags: np.ndarray, x: int, y: int, rx0: int, ry0: int, rx1: int, ry1: int, w: int, h: int) -> bool:
    """
    Goal: stand on a walkable tile adjacent to the object footprint, and the boundary
    edge between stand tile and footprint tile is open (both-side bit check).
    """
    if _rect_contains(x, y, rx0, ry0, rx1, ry1):
        return False
    if not _is_walkable(flags[y, x]):
        return False

    # Check all 8 neighbors as potential footprint border tiles
    for bx, by in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
        bx, by = x + bx, y + by
        if _in_bounds(bx, by, w, h) and _rect_contains(bx, by, rx0, ry0, rx1, ry1):
            if _edge_open_for_approach(flags, x, y, bx, by):
                return True

    return False


@njit(cache=True)
def bfs_to_object(
    flags: np.ndarray,
    sx: int,
    sy: int,
    root_x: int,
    root_y: int,
    size_x: int,
    size_y: int,
):
    """
    Object root is SW tile. size is given (already oriented).
    Finds path to a stand tile adjacent to the footprint with correct boundary access.

    Returns (px, py, n). If no path: n=0.
    """
    h, w = flags.shape

    if not _in_bounds(sx, sy, w, h):
        return np.empty(0, np.int32), np.empty(0, np.int32), 0
    if not _is_walkable(flags[sy, sx]):
        return np.empty(0, np.int32), np.empty(0, np.int32), 0

    rx0 = root_x
    ry0 = root_y
    rx1 = root_x + size_x - 1
    ry1 = root_y + size_y - 1

    if _is_object_goal(flags, sx, sy, rx0, ry0, rx1, ry1, w, h):
        return np.array([sx], np.int32), np.array([sy], np.int32), 1

    maxn = w * h
    qx = np.empty(maxn, dtype=np.int32)
    qy = np.empty(maxn, dtype=np.int32)
    parent = np.full(maxn, -1, dtype=np.int32)
    visited = np.zeros(maxn, dtype=np.uint8)

    def pack(x, y):
        return y * w + x

    si = pack(sx, sy)
    visited[si] = 1
    qx[0] = sx
    qy[0] = sy
    qs = 0
    qe = 1

    while qs < qe:
        cx = qx[qs]
        cy = qy[qs]
        qs += 1
        ci = pack(cx, cy)

        for di in range(8):
            nx = cx + DX8[di]
            ny = cy + DY8[di]
            if not _in_bounds(nx, ny, w, h):
                continue
            ni = pack(nx, ny)
            if visited[ni] != 0:
                continue
            if not _can_step_osrs(flags, w, h, cx, cy, di):
                continue

            visited[ni] = 1
            parent[ni] = ci

            if _is_object_goal(flags, nx, ny, rx0, ry0, rx1, ry1, w, h):
                px, py, n = _reconstruct(parent, ni, w)
                return px[:n].copy(), py[:n].copy(), n

            qx[qe] = nx
            qy[qe] = ny
            qe += 1

    return np.empty(0, np.int32), np.empty(0, np.int32), 0
