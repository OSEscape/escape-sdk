import time

from escape.client import Client

client = Client()
client.connect()

# Options
DRAW_TEXT = False
ONLY_DRAW_LARGE = True

TAG = "obj_debug"
GREEN = 0x8000FF00
RED = 0x80FF0000
WHITE = 0xFFFFFFFF

while True:
    _, _, plane = client.cache.world_position
    objects = client.objects.get(max_distance=20, plane=plane)

    with client.drawing.batch(clear_tag=TAG) as draw:
        for obj in objects:
            multi = obj.size_x > 1 or obj.size_y > 1
            color = RED if multi else GREEN
            
            if ONLY_DRAW_LARGE and not multi:
                continue

            for dx in range(obj.size_x):
                for dy in range(obj.size_y):
                    quad = client.scene.get_tile_quad(obj.sw_x + dx, obj.sw_y + dy)
                    if quad:
                        xs = [quad.p1.x, quad.p2.x, quad.p3.x, quad.p4.x]
                        ys = [quad.p1.y, quad.p2.y, quad.p3.y, quad.p4.y]
                        draw.add_polygon(xs, ys, color, filled=False, tag=TAG)

            pt = client.projection.world_tile_to_canvas(obj.sw_x, obj.sw_y, plane)
            if pt and DRAW_TEXT:
                label = f"{obj.name} ({obj.size_x}x{obj.size_y})" if multi else obj.name
                draw.add_text(label, pt.x, pt.y - 10, WHITE, tag=TAG)

    time.sleep(0.6)
