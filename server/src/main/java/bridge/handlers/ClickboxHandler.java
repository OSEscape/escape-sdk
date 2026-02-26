package bridge.handlers;

import bridge.overlay.ClickboxOverlay;
import bridge.proto.v1.*;
import com.google.protobuf.Empty;
import net.runelite.api.*;
import net.runelite.api.coords.LocalPoint;
import net.runelite.api.coords.WorldPoint;
import net.runelite.client.ui.overlay.OverlayManager;

import java.awt.Color;
import java.awt.Polygon;
import java.awt.Shape;
import java.awt.geom.PathIterator;
import java.util.ArrayList;
import java.util.List;

/**
 * ClickboxHandler - Manages real-time clickbox tracking for game entities.
 *
 * Responsibilities:
 * - Track single target at a time (NPC, Object, Tile, GroundItem)
 * - Stream clickbox vertex updates every ClientTick (~50fps)
 * - Handle target appearance/disappearance
 *
 * Thread Safety:
 * - All state accessed from client thread via BridgePlugin
 * - Tracking state is volatile for visibility
 */
public class ClickboxHandler implements EventHandler {
    private final Client client;
    private final SubscribeHandler subscribeHandler;
    private final OverlayManager overlayManager;
    private ClickboxOverlay clickboxOverlay;

    // Tracking state
    private volatile boolean trackingActive = false;
    private TargetType currentTargetType = null;

    // Target identifiers (only one active at a time)
    private int npcIndex = -1;
    private int packedLocation = 0;
    private int targetId = 0;  // For objects and ground items

    // Debug visualization state
    private volatile boolean debugEnabled = false;
    private static final Color DEBUG_COLOR_ACTIVE = new Color(0, 255, 0, 180);  // Semi-transparent green
    private static final Color DEBUG_COLOR_MISSING = new Color(255, 0, 0, 180); // Semi-transparent red

    // Shared shape for debug overlay (computed once, used by both Python stream and overlay)
    // This ensures Python receives EXACTLY the same data that's drawn on screen
    private volatile Shape debugShape = null;
    private volatile boolean debugTargetExists = true;

    public enum TargetType {
        GROUND_ITEM, NPC, OBJECT, TILE
    }

    public ClickboxHandler(Client client, SubscribeHandler subscribeHandler, OverlayManager overlayManager) {
        this.client = client;
        this.subscribeHandler = subscribeHandler;
        this.overlayManager = overlayManager;
    }

    @Override
    public void initialize() {
        // Reset tracking state
        trackingActive = false;
        currentTargetType = null;
        npcIndex = -1;
        packedLocation = 0;
        targetId = 0;
        debugEnabled = false;
        debugShape = null;
        debugTargetExists = false;

        // Create and register overlay (computes and sends in render())
        clickboxOverlay = new ClickboxOverlay(client, this);
        overlayManager.add(clickboxOverlay);
    }

    @Override
    public void shutdown() {
        trackingActive = false;
        debugShape = null;
        debugTargetExists = false;

        // Remove debug overlay
        if (clickboxOverlay != null) {
            overlayManager.remove(clickboxOverlay);
            clickboxOverlay = null;
        }
    }

    @Override
    public String getName() {
        return "ClickboxHandler";
    }

    /**
     * RPC: Start tracking a target's clickbox
     */
    public Empty startClickboxTracking(StartClickboxTrackingRequest request) {
        debugShape = null;
        debugTargetExists = false;
        debugEnabled = request.getDebug();

        // Validate and set tracking state based on oneof target type
        switch (request.getTargetCase()) {
            case GROUND_ITEM:
                GroundItemTarget groundItem = request.getGroundItem();
                if (groundItem.getPackedLocation() == 0) {
                    throw new IllegalArgumentException("Invalid packed_location for ground item");
                }
                currentTargetType = TargetType.GROUND_ITEM;
                packedLocation = groundItem.getPackedLocation();
                targetId = groundItem.getItemId();
                trackingActive = true;
                break;

            case NPC:
                NpcTarget npc = request.getNpc();
                if (npc.getNpcIndex() < 0) {
                    throw new IllegalArgumentException("Invalid npc_index: " + npc.getNpcIndex());
                }
                currentTargetType = TargetType.NPC;
                npcIndex = npc.getNpcIndex();
                trackingActive = true;
                break;

            case OBJECT:
                ObjectTarget object = request.getObject();
                if (object.getPackedLocation() == 0) {
                    throw new IllegalArgumentException("Invalid packed_location for object");
                }
                currentTargetType = TargetType.OBJECT;
                packedLocation = object.getPackedLocation();
                targetId = object.getObjectId();
                trackingActive = true;
                break;

            case TILE:
                TileTarget tile = request.getTile();
                if (tile.getPackedLocation() == 0) {
                    throw new IllegalArgumentException("Invalid packed_location for tile");
                }
                currentTargetType = TargetType.TILE;
                packedLocation = tile.getPackedLocation();
                trackingActive = true;
                break;

            case TARGET_NOT_SET:
                throw new IllegalArgumentException("No target specified in request");
        }

        return Empty.getDefaultInstance();
    }

    /**
     * RPC: Stop tracking current target
     */
    public Empty stopClickboxTracking(Empty request) {
        trackingActive = false;
        currentTargetType = null;
        npcIndex = -1;
        packedLocation = 0;
        targetId = 0;
        debugEnabled = false;
        debugShape = null;
        debugTargetExists = false;
        return Empty.getDefaultInstance();
    }

    /**
     * RPC: Print all NPCs for debugging
     */
    public Empty printAllNpcs(Empty request) {
        System.out.println("=== All NPCs ===");
        WorldView wv = client.getTopLevelWorldView();
        IndexedObjectSet<? extends NPC> npcs = wv != null ? wv.npcs() : null;

        if (npcs == null) {
            System.out.println("No NPCs found");
            return Empty.getDefaultInstance();
        }

        for (NPC npc : npcs) {
            if (npc != null) {
                System.out.printf("index=%d, id=%d, name=%s%n",
                        npc.getIndex(),
                        npc.getId(),
                        npc.getName());
            }
        }

        System.out.println("=== End NPCs ===");
        return Empty.getDefaultInstance();
    }

    /**
     * Check if stream has subscribers
     */
    public boolean hasSubscribers() {
        return subscribeHandler.hasSubscribers();
    }

    /**
     * Stop tracking (called by overlay when client disconnects)
     */
    public void stopTracking() {
        trackingActive = false;
        debugShape = null;
        debugTargetExists = false;
    }

    /**
     * Send clickbox update to Python - called from overlay render() with frame-perfect shape
     */
    public void sendUpdate(Shape shape, boolean targetExists) {
        if (!trackingActive || !subscribeHandler.hasSubscribers()) {
            return;
        }

        ClickboxUpdate update;
        if (shape != null && targetExists) {
            List<Integer> vertices = shapeToVertices(shape);
            update = ClickboxUpdate.newBuilder()
                    .setTargetExists(true)
                    .addAllVertices(vertices)
                    .build();
        } else {
            update = targetNotFound();
        }

        subscribeHandler.send(update);

        // Store for debug visualization
        if (debugEnabled) {
            debugShape = shape;
            debugTargetExists = targetExists;
        }
    }

    /**
     * Getters for overlay to access target info for frame-perfect computation
     */
    public boolean isTrackingActive() {
        return trackingActive;
    }

    public TargetType getCurrentTargetType() {
        return currentTargetType;
    }

    public int getNpcIndex() {
        return npcIndex;
    }

    public int getPackedLocation() {
        return packedLocation;
    }

    public int getTargetId() {
        return targetId;
    }

    /**
     * Convert Shape to flat vertex list using PathIterator
     */
    private List<Integer> shapeToVertices(Shape shape) {
        List<Integer> vertices = new ArrayList<>();
        PathIterator pathIterator = shape.getPathIterator(null);
        float[] coords = new float[6];

        while (!pathIterator.isDone()) {
            int type = pathIterator.currentSegment(coords);
            if (type == PathIterator.SEG_MOVETO || type == PathIterator.SEG_LINETO) {
                vertices.add((int) coords[0]);
                vertices.add((int) coords[1]);
            }
            pathIterator.next();
        }

        return vertices;
    }

    /**
     * Return update indicating target not found
     */
    private ClickboxUpdate targetNotFound() {
        return ClickboxUpdate.newBuilder()
            .setTargetExists(false)
            .build();
    }

    /**
     * Store game state references for debug overlay (called in onBeforeRender)
     * Overlay will convert these to screen coordinates at render time
     */
    /**
     * Getters for ClickboxOverlay - draws the same shape that Python receives
     */
    public boolean isDebugEnabled() {
        return debugEnabled;
    }

    public Shape getDebugShape() {
        return debugShape;
    }

    public boolean isDebugTargetExists() {
        return debugTargetExists;
    }

    public Color getDebugColorActive() {
        return DEBUG_COLOR_ACTIVE;
    }

    public Color getDebugColorMissing() {
        return DEBUG_COLOR_MISSING;
    }
}
