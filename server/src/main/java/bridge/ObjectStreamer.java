package bridge;

import bridge.proto.v1.*;
import net.runelite.api.*;
import net.runelite.api.coords.WorldPoint;
import net.runelite.client.util.Text;
import java.util.*;

public class ObjectStreamer {
    public static final int TYPE_GAME_OBJECT = 0;
    public static final int TYPE_WALL_OBJECT = 1;
    public static final int TYPE_DECORATIVE_OBJECT = 2;
    public static final int TYPE_GROUND_OBJECT = 3;

    private final Client client;
    private final Map<TileObject, ObjectData> objects = new HashMap<>();
    private boolean dirty = false;

    // Subscribe-as-you-go tracked sets
    private final Set<Integer> subscribedIds = new HashSet<>();
    private final Set<String> subscribedNames = new HashSet<>();  // lowercase
    private boolean streamAll = false;

    private static class ObjectData {
        final int type;
        final int id;
        final int worldX;
        final int worldY;
        final int plane;
        final int orientation;
        final int sizeX;
        final int sizeY;
        final String name;
        final String[] actions;

        ObjectData(int type, int id, int worldX, int worldY, int plane,
                   int orientation, int sizeX, int sizeY,
                   String name, String[] actions) {
            this.type = type;
            this.id = id;
            this.worldX = worldX;
            this.worldY = worldY;
            this.plane = plane;
            this.orientation = orientation;
            this.sizeX = sizeX;
            this.sizeY = sizeY;
            this.name = name;
            this.actions = actions;
        }
    }

    public ObjectStreamer(Client client) {
        this.client = client;
    }

    public void scan() {
        if (client.getGameState() != GameState.LOGGED_IN) return;

        WorldView wv = client.getTopLevelWorldView();
        if (wv == null) return;

        scanWorldView(wv);
        for (WorldEntity we : wv.worldEntities()) {
            if (we.getWorldView() != null) {
                scanWorldView(we.getWorldView());
            }
        }
    }

    public void onWorldViewLoaded(WorldView wv) {
        objects.clear();
        scanWorldView(wv);
    }

    public void onGameObjectSpawned(net.runelite.api.GameObject obj) {
        if (obj == null || objects.containsKey(obj)) return;
        ObjectData data = createObjectData(obj, TYPE_GAME_OBJECT);
        if (data != null) {
            objects.put(obj, data);
            dirty = true;
        }
    }

    public void onGameObjectDespawned(net.runelite.api.GameObject obj) {
        if (obj != null && objects.remove(obj) != null) {
            dirty = true;
        }
    }

    public void onWallObjectSpawned(WallObject obj) {
        if (obj == null || objects.containsKey(obj)) return;
        ObjectData data = createObjectData(obj, TYPE_WALL_OBJECT);
        if (data != null) {
            objects.put(obj, data);
            dirty = true;
        }
    }

    public void onWallObjectDespawned(WallObject obj) {
        if (obj != null && objects.remove(obj) != null) {
            dirty = true;
        }
    }

    public void onDecorativeObjectSpawned(DecorativeObject obj) {
        if (obj == null || objects.containsKey(obj)) return;
        ObjectData data = createObjectData(obj, TYPE_DECORATIVE_OBJECT);
        if (data != null) {
            objects.put(obj, data);
            dirty = true;
        }
    }

    public void onDecorativeObjectDespawned(DecorativeObject obj) {
        if (obj != null && objects.remove(obj) != null) {
            dirty = true;
        }
    }

    public void onGroundObjectSpawned(GroundObject obj) {
        if (obj == null || objects.containsKey(obj)) return;
        ObjectData data = createObjectData(obj, TYPE_GROUND_OBJECT);
        if (data != null) {
            objects.put(obj, data);
            dirty = true;
        }
    }

    public void onGroundObjectDespawned(GroundObject obj) {
        if (obj != null && objects.remove(obj) != null) {
            dirty = true;
        }
    }

    public int[][] getAllPacked() {
        int[][] result = new int[objects.size()][];
        int i = 0;
        for (ObjectData d : objects.values()) {
            result[i++] = new int[] {
                d.type, d.id, d.worldX, d.worldY, d.plane,
                d.orientation, d.sizeX, d.sizeY
            };
        }
        return result;
    }

    public java.util.List<bridge.proto.v1.GameObject> getAllObjects() {
        java.util.List<bridge.proto.v1.GameObject> result = new ArrayList<>();

        for (ObjectData d : objects.values()) {
            int packedLocation = (d.worldX & 0x7FFF) | ((d.worldY & 0x7FFF) << 15) | ((d.plane & 0x3) << 30);

            bridge.proto.v1.GameObject.Builder builder = bridge.proto.v1.GameObject.newBuilder()
                .setType(d.type)
                .setId(d.id)
                .setPackedLocation(packedLocation)
                .setOrientation(d.orientation)
                .setSizeX(d.sizeX)
                .setSizeY(d.sizeY)
                .setName(d.name);

            for (String action : d.actions) {
                builder.addActions(action);
            }

            result.add(builder.build());
        }

        return result;
    }

    public int getCount() {
        return objects.size();
    }

    public boolean isDirty() {
        return dirty;
    }

    public void clearDirty() {
        dirty = false;
    }

    private void scanWorldView(WorldView wv) {
        if (wv == null) return;
        Scene scene = wv.getScene();
        if (scene == null) return;

        Tile[][][] tiles = scene.getTiles();
        for (int z = 0; z < Constants.MAX_Z; z++) {
            for (int x = 0; x < wv.getSizeX(); x++) {
                for (int y = 0; y < wv.getSizeY(); y++) {
                    Tile tile = tiles[z][x][y];
                    if (tile == null) continue;
                    scanTile(tile);
                    if (tile.getBridge() != null) {
                        scanTile(tile.getBridge());
                    }
                }
            }
        }
        dirty = true;
    }

    private void scanTile(Tile tile) {
        net.runelite.api.GameObject[] gameObjects = tile.getGameObjects();
        if (gameObjects != null) {
            for (net.runelite.api.GameObject go : gameObjects) {
                if (go != null && go.getSceneMinLocation().equals(tile.getSceneLocation())) {
                    onGameObjectSpawned(go);
                }
            }
        }

        WallObject wall = tile.getWallObject();
        if (wall != null) {
            onWallObjectSpawned(wall);
        }

        DecorativeObject deco = tile.getDecorativeObject();
        if (deco != null) {
            onDecorativeObjectSpawned(deco);
        }

        GroundObject ground = tile.getGroundObject();
        if (ground != null) {
            onGroundObjectSpawned(ground);
        }
    }

    // --- Subscribe-as-you-go ---

    public java.util.List<bridge.proto.v1.GameObject> streamObjects(List<Integer> ids, List<String> names, boolean streamAll) {
        if (streamAll) this.streamAll = true;
        if (ids != null) subscribedIds.addAll(ids);
        if (names != null) {
            for (String n : names) subscribedNames.add(n.toLowerCase());
        }
        return getFilteredObjects();
    }

    public java.util.List<bridge.proto.v1.GameObject> getFilteredObjects() {
        if (streamAll) {
            return getAllObjects();
        }

        if (subscribedIds.isEmpty() && subscribedNames.isEmpty()) {
            return Collections.emptyList();
        }

        java.util.List<bridge.proto.v1.GameObject> result = new ArrayList<>();
        for (ObjectData d : objects.values()) {
            if (subscribedIds.contains(d.id) ||
                subscribedNames.contains(d.name.toLowerCase())) {
                int packedLocation = (d.worldX & 0x7FFF) | ((d.worldY & 0x7FFF) << 15) | ((d.plane & 0x3) << 30);
                bridge.proto.v1.GameObject.Builder builder = bridge.proto.v1.GameObject.newBuilder()
                    .setType(d.type)
                    .setId(d.id)
                    .setPackedLocation(packedLocation)
                    .setOrientation(d.orientation)
                    .setSizeX(d.sizeX)
                    .setSizeY(d.sizeY)
                    .setName(d.name);
                for (String action : d.actions) builder.addActions(action);
                result.add(builder.build());
            }
        }
        return result;
    }

    public boolean hasSubscriptions() {
        return streamAll || !subscribedIds.isEmpty() || !subscribedNames.isEmpty();
    }

    public void clearSubscriptions() {
        subscribedIds.clear();
        subscribedNames.clear();
        streamAll = false;
    }

    private ObjectData createObjectData(TileObject obj, int type) {
        WorldView wv = obj.getWorldView();
        if (wv == null) return null;

        WorldPoint wp = WorldPoint.fromLocalInstance(client, obj.getLocalLocation(), obj.getPlane());
        if (wp == null) return null;

        int orientation = 0, sizeX = 1, sizeY = 1;
        if (obj instanceof net.runelite.api.GameObject) {
            net.runelite.api.GameObject go = (net.runelite.api.GameObject) obj;
            orientation = go.getOrientation();
            sizeX = go.sizeX();
            sizeY = go.sizeY();
        }

        String name = "";
        String[] actions = new String[0];
        ObjectComposition def = client.getObjectDefinition(obj.getId());
        if (def != null) {
            try {
                ObjectComposition impostor = def.getImpostor();
                if (impostor != null) def = impostor;
            } catch (Exception ignored) {
                // getImpostor() can throw obfuscated exceptions wrapping NPE during scene loading
            }
            String defName = def.getName();
            if (defName != null && !defName.equals("null")) name = Text.removeTags(defName);
            String[] rawActions = def.getActions();
            if (rawActions != null) {
                actions = rawActions.clone();
                for (int i = 0; i < actions.length; i++) {
                    actions[i] = actions[i] == null ? "" : Text.removeTags(actions[i]);
                }
            }
        }

        return new ObjectData(
            type, obj.getId(),
            wp.getX(), wp.getY(), wp.getPlane(),
            orientation, sizeX, sizeY,
            name, actions
        );
    }
}
