package bridge.handlers;

import bridge.*;
import bridge.proto.v1.*;
import com.google.protobuf.Empty;
import net.runelite.api.Client;
import net.runelite.api.CollisionData;
import net.runelite.api.WorldEntity;
import net.runelite.api.WorldEntityConfig;
import net.runelite.api.WorldView;

import java.util.ArrayList;
import java.util.List;

/**
 * WorldHandler - Manages world state and terrain streaming.
 *
 * Responsibilities:
 * - Stream ground items (spawned/despawned/quantity changes)
 * - Stream scene objects (game objects, walls, decorative, ground objects)
 * - Handle WorldView loading with terrain data
 * - Batch object updates on game tick
 * - Own and manage GroundItemStreamer and ObjectStreamer lifecycle
 *
 * Thread Safety:
 * - Owns GroundItemStreamer and ObjectStreamer
 * - All events handled on client thread via BridgePlugin
 */
public class WorldHandler implements EventHandler {
    private final Client client;
    private final SubscribeHandler subscribeHandler;
    private final BridgePlugin plugin;

    // World state streamers (owned by WorldHandler)
    private GroundItemStreamer groundItemStreamer;
    private ObjectStreamer objectStreamer;
    private NpcStreamer npcStreamer;

    // Collision diff state
    private int[] collisionSnapshot;
    private int collisionPlanes;
    private int collisionSizeX;
    private int collisionSizeY;
    private final List<Integer> patchIndices = new ArrayList<>();
    private final List<Integer> patchFlags = new ArrayList<>();

    public WorldHandler(Client client, SubscribeHandler subscribeHandler, BridgePlugin plugin) {
        this.client = client;
        this.subscribeHandler = subscribeHandler;
        this.plugin = plugin;
    }

    @Override
    public void initialize() {
        this.groundItemStreamer = new GroundItemStreamer(client);
        this.objectStreamer = new ObjectStreamer(client);
        this.npcStreamer = new NpcStreamer(client);
        this.npcStreamer.initialize();
    }

    @Override
    public void shutdown() {
        // Streamers have no cleanup needed
    }

    @Override
    public String getName() {
        return "WorldHandler";
    }

    // ========================================================================
    // GROUND ITEM EVENTS
    // ========================================================================

    /**
     * Handle item spawned event (called from BridgePlugin.onItemSpawned)
     */
    public void onItemSpawned(net.runelite.api.events.ItemSpawned event) {
        groundItemStreamer.onItemSpawned(event);
    }

    /**
     * Handle item despawned event (called from BridgePlugin.onItemDespawned)
     */
    public void onItemDespawned(net.runelite.api.events.ItemDespawned event) {
        groundItemStreamer.onItemDespawned(event);
    }

    /**
     * Handle item quantity changed event (called from BridgePlugin.onItemQuantityChanged)
     */
    public void onItemQuantityChanged(net.runelite.api.events.ItemQuantityChanged event) {
        groundItemStreamer.onItemQuantityChanged(event);
    }

    // ========================================================================
    // SCENE OBJECT EVENTS
    // ========================================================================

    /**
     * Handle game object spawned event (called from BridgePlugin.onGameObjectSpawned)
     */
    public void onGameObjectSpawned(net.runelite.api.GameObject gameObject) {
        objectStreamer.onGameObjectSpawned(gameObject);
    }

    /**
     * Handle game object despawned event (called from BridgePlugin.onGameObjectDespawned)
     */
    public void onGameObjectDespawned(net.runelite.api.GameObject gameObject) {
        objectStreamer.onGameObjectDespawned(gameObject);
    }

    /**
     * Handle wall object spawned event (called from BridgePlugin.onWallObjectSpawned)
     */
    public void onWallObjectSpawned(net.runelite.api.WallObject wallObject) {
        objectStreamer.onWallObjectSpawned(wallObject);
    }

    /**
     * Handle wall object despawned event (called from BridgePlugin.onWallObjectDespawned)
     */
    public void onWallObjectDespawned(net.runelite.api.WallObject wallObject) {
        objectStreamer.onWallObjectDespawned(wallObject);
    }

    /**
     * Handle decorative object spawned event (called from BridgePlugin.onDecorativeObjectSpawned)
     */
    public void onDecorativeObjectSpawned(net.runelite.api.DecorativeObject decorativeObject) {
        objectStreamer.onDecorativeObjectSpawned(decorativeObject);
    }

    /**
     * Handle decorative object despawned event (called from BridgePlugin.onDecorativeObjectDespawned)
     */
    public void onDecorativeObjectDespawned(net.runelite.api.DecorativeObject decorativeObject) {
        objectStreamer.onDecorativeObjectDespawned(decorativeObject);
    }

    /**
     * Handle ground object spawned event (called from BridgePlugin.onGroundObjectSpawned)
     */
    public void onGroundObjectSpawned(net.runelite.api.GroundObject groundObject) {
        objectStreamer.onGroundObjectSpawned(groundObject);
    }

    /**
     * Handle ground object despawned event (called from BridgePlugin.onGroundObjectDespawned)
     */
    public void onGroundObjectDespawned(net.runelite.api.GroundObject groundObject) {
        objectStreamer.onGroundObjectDespawned(groundObject);
    }

    // ========================================================================
    // WORLD VIEW LOADING
    // ========================================================================

    /**
     * Build WorldViewLoad message for current world view
     * @return WorldViewLoad with terrain data
     */
    public WorldViewLoad buildWorldViewLoad() {
        WorldView wv = client.getTopLevelWorldView();
        if (wv == null) {
            return WorldViewLoad.newBuilder().build();
        }
        return buildWorldViewLoad(wv);
    }

    /**
     * Build WorldViewLoad message for a specific world view
     * @param wv WorldView to build message for
     * @return WorldViewLoad with terrain data
     */
    private WorldViewLoad buildWorldViewLoad(WorldView wv) {
        int baseX = wv.getBaseX();
        int baseY = wv.getBaseY();
        int plane = wv.getPlane();
        plugin.currentWorldViewIndex = wv.getId();

        int[][][] heights = wv.getTileHeights();
        int numPlanes = heights.length;
        int sizeX = heights[0].length;
        int sizeY = heights[0][0].length;

        // Flatten 3D height array to 1D for protobuf
        int[] flattenedHeights = new int[numPlanes * sizeX * sizeY];
        int index = 0;
        for (int z = 0; z < numPlanes; z++) {
            int[][] planeHeights = heights[z];
            for (int x = 0; x < sizeX; x++) {
                System.arraycopy(planeHeights[x], 0, flattenedHeights, index, sizeY);
                index += sizeY;
            }
        }

        // Extract bridge flags from tile settings
        byte[][][] settings = wv.getTileSettings();
        int settingsSizeX = settings[1].length;
        int settingsSizeY = settings[1][0].length;
        boolean[] bridgeFlags = new boolean[settingsSizeX * settingsSizeY];

        byte[][] plane1 = settings[1];
        index = 0;
        for (int x = 0; x < settingsSizeX; x++) {
            for (int y = 0; y < settingsSizeY; y++) {
                bridgeFlags[index++] = (plane1[x][y] & 2) != 0;
            }
        }

        // Flatten collision flags from CollisionData
        // Collision is per-tile (104x104), not per-vertex like heights (105x105)
        CollisionData[] collisionMaps = wv.getCollisionMaps();
        int[] flattenedCollision = null;
        int collisionSizeX = sizeX - 1;
        int collisionSizeY = sizeY - 1;
        if (collisionMaps != null) {
            flattenedCollision = new int[numPlanes * collisionSizeX * collisionSizeY];
            index = 0;
            for (int z = 0; z < numPlanes; z++) {
                if (z < collisionMaps.length && collisionMaps[z] != null) {
                    int[][] flags = collisionMaps[z].getFlags();
                    for (int x = 0; x < collisionSizeX; x++) {
                        if (x < flags.length) {
                            System.arraycopy(flags[x], 0, flattenedCollision, index, Math.min(flags[x].length, collisionSizeY));
                        }
                        index += collisionSizeY;
                    }
                } else {
                    index += collisionSizeX * collisionSizeY;
                }
            }
        }

        // Flatten instance template chunks if instanced
        boolean isInstance = wv.isInstance();
        int[] flattenedTemplateChunks = null;
        if (isInstance) {
            int[][][] templateChunks = wv.getInstanceTemplateChunks();
            if (templateChunks != null) {
                int tPlanes = templateChunks.length;
                int tX = templateChunks[0].length;
                int tY = templateChunks[0][0].length;
                flattenedTemplateChunks = new int[tPlanes * tX * tY];
                index = 0;
                for (int z = 0; z < tPlanes; z++) {
                    for (int x = 0; x < tX; x++) {
                        System.arraycopy(templateChunks[z][x], 0, flattenedTemplateChunks, index, tY);
                        index += tY;
                    }
                }
            }
        }

        // Get WorldEntity bounds if not top-level
        int boundsX = 0;
        int boundsY = 0;
        int boundsWidth = 0;
        int boundsHeight = 0;

        if (!wv.isTopLevel()) {
            WorldView topLevel = client.getTopLevelWorldView();
            if (topLevel != null) {
                WorldEntity we = topLevel.worldEntities().byIndex(wv.getId());
                if (we != null) {
                    WorldEntityConfig config = we.getConfig();
                    boundsX = config.getBoundsX();
                    boundsY = config.getBoundsY();
                    boundsWidth = config.getBoundsWidth();
                    boundsHeight = config.getBoundsHeight();
                }
            }
        }

        WorldViewLoad.Builder builder = WorldViewLoad.newBuilder()
            .setPlane(plane)
            .setBaseX(baseX)
            .setBaseY(baseY)
            .setSizeX(sizeX)
            .setSizeY(sizeY)
            .setBoundsX(boundsX)
            .setBoundsY(boundsY)
            .setBoundsWidth(boundsWidth)
            .setBoundsHeight(boundsHeight);

        for (int height : flattenedHeights) {
            builder.addTileHeights(height);
        }
        for (boolean flag : bridgeFlags) {
            builder.addBridgeFlags(flag);
        }
        if (flattenedCollision != null) {
            for (int flag : flattenedCollision) {
                builder.addCollisionFlags(flag);
            }
        }
        builder.setIsInstance(isInstance);
        if (flattenedTemplateChunks != null) {
            for (int chunk : flattenedTemplateChunks) {
                builder.addInstanceTemplateChunks(chunk);
            }
        }

        return builder.build();
    }

    /**
     * Handle WorldView loaded event (called from BridgePlugin.onWorldViewLoaded)
     * Rebuilds ground items, scans objects, and sends terrain data
     */
    public void onWorldViewLoaded(net.runelite.api.events.WorldViewLoaded event) {
        // Clear all entity caches — stale data from previous scene must not persist
        npcStreamer.clear();

        // Rebuild ground items from scene (already clears internally)
        groundItemStreamer.rebuildFromScene();
        if (groundItemStreamer.isEnabled()) {
            GroundItemsUpdate groundMsg = GroundItemsUpdate.newBuilder()
                .addAllGroundItems(groundItemStreamer.getGroundItems())
                .build();
            subscribeHandler.send(groundMsg);
            groundItemStreamer.clearDirty();
        }

        // Scan objects in newly loaded world view (clears + rescans internally)
        objectStreamer.onWorldViewLoaded(event.getWorldView());
        if (objectStreamer.hasSubscriptions()) {
            SceneObjectsUpdate sceneMsg = SceneObjectsUpdate.newBuilder()
                .addAllObjects(objectStreamer.getFilteredObjects())
                .build();
            subscribeHandler.send(sceneMsg);
        }

        // Build and send WorldViewLoad message (always sent)
        WorldViewLoad worldViewLoad = buildWorldViewLoad(event.getWorldView());
        subscribeHandler.send(worldViewLoad);

        // Capture collision snapshot for per-tick diffing
        captureCollisionSnapshot(event.getWorldView());
    }

    // ========================================================================
    // COLLISION DIFF
    // ========================================================================

    /**
     * Capture current collision flags into snapshot array for diff comparisons.
     * Called after WorldViewLoad is sent so the snapshot matches what Python received.
     */
    private void captureCollisionSnapshot(WorldView wv) {
        CollisionData[] collisionMaps = wv.getCollisionMaps();
        if (collisionMaps == null) {
            collisionSnapshot = null;
            return;
        }

        int[][][] heights = wv.getTileHeights();
        int numPlanes = heights.length;
        int sizeX = heights[0].length - 1;  // collision is per-tile (104), not per-vertex (105)
        int sizeY = heights[0][0].length - 1;
        int totalSize = numPlanes * sizeX * sizeY;

        // Reuse array if dimensions match
        if (collisionSnapshot == null || collisionSnapshot.length != totalSize) {
            collisionSnapshot = new int[totalSize];
        }
        collisionPlanes = numPlanes;
        collisionSizeX = sizeX;
        collisionSizeY = sizeY;

        int index = 0;
        for (int z = 0; z < numPlanes; z++) {
            if (z < collisionMaps.length && collisionMaps[z] != null) {
                int[][] flags = collisionMaps[z].getFlags();
                for (int x = 0; x < sizeX; x++) {
                    if (x < flags.length) {
                        System.arraycopy(flags[x], 0, collisionSnapshot, index, Math.min(flags[x].length, sizeY));
                    }
                    index += sizeY;
                }
            } else {
                index += sizeX * sizeY;
            }
        }
    }

    /**
     * Compare live collision flags against snapshot, send patch if anything changed.
     * Called every game tick. Zero allocation on the common no-change path.
     */
    public void onGameTickCollisionSync() {
        if (collisionSnapshot == null) return;

        WorldView wv = client.getTopLevelWorldView();
        if (wv == null) return;

        CollisionData[] collisionMaps = wv.getCollisionMaps();
        if (collisionMaps == null) return;

        patchIndices.clear();
        patchFlags.clear();

        int index = 0;
        for (int z = 0; z < collisionPlanes; z++) {
            if (z < collisionMaps.length && collisionMaps[z] != null) {
                int[][] flags = collisionMaps[z].getFlags();
                for (int x = 0; x < collisionSizeX; x++) {
                    if (x < flags.length) {
                        int[] col = flags[x];
                        for (int y = 0; y < collisionSizeY && y < col.length; y++) {
                            int live = col[y];
                            if (live != collisionSnapshot[index]) {
                                patchIndices.add(index);
                                patchFlags.add(live);
                                collisionSnapshot[index] = live;
                            }
                            index++;
                        }
                        // Skip remaining if col shorter than sizeY
                        index += Math.max(0, collisionSizeY - col.length);
                    } else {
                        index += collisionSizeY;
                    }
                }
            } else {
                index += collisionSizeX * collisionSizeY;
            }
        }

        if (patchIndices.isEmpty()) return;
        if (!subscribeHandler.hasSubscribers()) return;

        CollisionUpdate.Builder builder = CollisionUpdate.newBuilder();
        for (int i = 0; i < patchIndices.size(); i++) {
            builder.addIndices(patchIndices.get(i));
            builder.addFlags(patchFlags.get(i));
        }
        subscribeHandler.send(builder.build());
    }

    // ========================================================================
    // GAME TICK (BATCHED OBJECT UPDATES)
    // ========================================================================

    /**
     * Handle game tick for batched object updates (called from BridgePlugin.onGameTick)
     * Only sends update if objects changed since last tick and there are subscriptions
     */
    public void onGameTickObjectSync() {
        if (objectStreamer.hasSubscriptions() && objectStreamer.isDirty()) {
            SceneObjectsUpdate sceneMsg = SceneObjectsUpdate.newBuilder()
                .addAllObjects(objectStreamer.getFilteredObjects())
                .build();
            subscribeHandler.send(sceneMsg);
            objectStreamer.clearDirty();
        }
    }

    /**
     * Handle game tick for batched ground item updates (called from BridgePlugin.onGameTick)
     * Only sends update if ground items changed since last tick and streaming is enabled
     */
    public void onGameTickGroundItemSync() {
        if (groundItemStreamer.isEnabled() && groundItemStreamer.isDirty()) {
            GroundItemsUpdate msg = GroundItemsUpdate.newBuilder()
                .addAllGroundItems(groundItemStreamer.getGroundItems())
                .build();
            subscribeHandler.send(msg);
            groundItemStreamer.clearDirty();
        }
    }

    /**
     * Handle game tick for NPC streaming (called from BridgePlugin.onGameTick)
     * Polls NPCs and sends update if data changed since last tick and there are subscriptions
     */
    public void onGameTickNpcSync() {
        npcStreamer.onGameTick();

        if (npcStreamer.hasSubscriptions() && npcStreamer.isDirty()) {
            NpcUpdate msg = NpcUpdate.newBuilder()
                .addAllNpcs(npcStreamer.getFilteredNpcs())
                .build();
            subscribeHandler.send(msg);
            npcStreamer.clearDirty();
        }
    }

    // ========================================================================
    // ACCESSOR METHODS (for SubscribeHandler snapshots)
    // ========================================================================

    /**
     * Get ground item streamer for snapshot generation
     * @return GroundItemStreamer instance
     */
    public GroundItemStreamer getGroundItemStreamer() {
        return groundItemStreamer;
    }

    /**
     * Get object streamer for snapshot generation
     * @return ObjectStreamer instance
     */
    public ObjectStreamer getObjectStreamer() {
        return objectStreamer;
    }

    /**
     * Get NPC streamer for snapshot generation
     * @return NpcStreamer instance
     */
    public NpcStreamer getNpcStreamer() {
        return npcStreamer;
    }

    // ========================================================================
    // ENTITY STREAMING RPCs (auto-discovered by ReflectiveServiceBuilder)
    // ========================================================================

    public NpcUpdate streamNpcs(StreamNpcsRequest request) {
        return NpcUpdate.newBuilder()
            .addAllNpcs(npcStreamer.streamNpcs(request.getIdsList(), request.getNamesList(), request.getStreamAll()))
            .build();
    }

    public SceneObjectsUpdate streamObjects(StreamObjectsRequest request) {
        return SceneObjectsUpdate.newBuilder()
            .addAllObjects(objectStreamer.streamObjects(request.getIdsList(), request.getNamesList(), request.getStreamAll()))
            .build();
    }

    public GroundItemsUpdate streamGroundItems(Empty request) {
        return GroundItemsUpdate.newBuilder()
            .addAllGroundItems(groundItemStreamer.enable())
            .build();
    }

    // ========================================================================
    // ONE-TIME SNAPSHOT RPCs (auto-discovered by ReflectiveServiceBuilder)
    // ========================================================================

    public NpcUpdate getAllNpcs(Empty request) {
        return NpcUpdate.newBuilder()
            .addAllNpcs(npcStreamer.getAllNpcs())
            .build();
    }

    public SceneObjectsUpdate getAllObjects(Empty request) {
        return SceneObjectsUpdate.newBuilder()
            .addAllObjects(objectStreamer.getAllObjects())
            .build();
    }

    public GroundItemsUpdate getAllGroundItems(Empty request) {
        groundItemStreamer.rebuildFromScene();
        return GroundItemsUpdate.newBuilder()
            .addAllGroundItems(groundItemStreamer.getGroundItems())
            .build();
    }

    public void clearSubscriptions() {
        npcStreamer.clearSubscriptions();
        objectStreamer.clearSubscriptions();
        groundItemStreamer.disable();
    }

}
