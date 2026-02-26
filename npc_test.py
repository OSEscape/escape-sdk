import time

from escape.client import Client

client = Client()
client.connect()

# Options
DRAW_TEXT = True
ONLY_DRAW_LARGE = False

TAG = "NPC_debug"
GREEN = 0x8000FF00
RED = 0x80FF0000
WHITE = 0xFFFFFFFF

client.npcs.stream_all()

while True:
    _, _, plane = client.cache.world_position
    npcs = client.npcs.get(max_distance=20)
    with client.drawing.batch(clear_tag=TAG) as draw:
        for npc in npcs:
            multi = npc.size > 1
            color = RED if multi else GREEN
            
            if ONLY_DRAW_LARGE and not multi:
                continue

            for dx in range(npc.size):
                for dy in range(npc.size):
                    quad = client.scene.get_tile_quad(npc.world_x + dx, npc.world_y + dy)
                    if quad:
                        xs = [quad.p1.x, quad.p2.x, quad.p3.x, quad.p4.x]
                        ys = [quad.p1.y, quad.p2.y, quad.p3.y, quad.p4.y]
                        draw.add_polygon(xs, ys, color, filled=False, tag=TAG)

            pt = client.projection.world_tile_to_canvas(npc.world_x, npc.world_y, plane)
            if pt and DRAW_TEXT:
                label = f"{npc.name} ({npc.size}x{npc.size})" if multi else npc.name
                draw.add_text(label, pt.x, pt.y - 10, WHITE, tag=TAG)

    time.sleep(0.1)
