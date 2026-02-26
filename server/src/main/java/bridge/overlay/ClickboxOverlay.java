package bridge.overlay;

import bridge.handlers.ClickboxHandler;
import net.runelite.api.*;
import net.runelite.api.coords.LocalPoint;
import net.runelite.api.coords.WorldPoint;
import net.runelite.client.ui.overlay.Overlay;
import net.runelite.client.ui.overlay.OverlayLayer;
import net.runelite.client.ui.overlay.OverlayPosition;

import java.awt.*;

/**
 * Clickbox overlay - computes and sends frame-perfect clickbox data to Python, then draws it.
 *
 * Critical design: Computation happens in render() for frame-perfect coordinates:
 * 1. Compute shape with post-viewport-transform coordinates
 * 2. Send to Python immediately (minimal delay)
 * 3. Draw the same shape
 *
 * This ensures Python receives the most up-to-date screen coordinates possible.
 * Renders ABOVE_SCENE (right after 3D, before UI).
 */
public class ClickboxOverlay extends Overlay {
    private final Client client;
    private final ClickboxHandler clickboxHandler;

    public ClickboxOverlay(Client client, ClickboxHandler clickboxHandler) {
        this.client = client;
        this.clickboxHandler = clickboxHandler;
        setPosition(OverlayPosition.DYNAMIC);
        setLayer(OverlayLayer.ABOVE_SCENE);  // Draw right after 3D scene
    }

    @Override
    public Dimension render(Graphics2D g) {
        // Only compute and send if tracking is active
        if (!clickboxHandler.isTrackingActive()) {
            return null;
        }

        // Auto-stop tracking if no subscribers (client disconnected)
        if (!clickboxHandler.hasSubscribers()) {
            clickboxHandler.stopTracking();
            return null;
        }

        // Get target info
        ClickboxHandler.TargetType targetType = clickboxHandler.getCurrentTargetType();
        if (targetType == null) {
            clickboxHandler.sendUpdate(null, false);
            return null;
        }

        // Compute shape NOW with frame-perfect viewport transform
        Shape shape = null;
        boolean targetExists = true;

        switch (targetType) {
            case NPC:
                // Find NPC by server index (NOT array position!)
                NPC npc = findNpcByIndex(clickboxHandler.getNpcIndex());
                if (npc != null) {
                    shape = npc.getConvexHull();
                }
                targetExists = (shape != null);
                break;

            case GROUND_ITEM:
            case TILE:
                WorldPoint wp = unpackWorldPoint(clickboxHandler.getPackedLocation());
                if (wp != null) {
                    LocalPoint lp = LocalPoint.fromWorld(client, wp);
                    if (lp != null) {
                        shape = Perspective.getCanvasTilePoly(client, lp);
                    }
                }
                targetExists = (shape != null);
                break;

            case OBJECT:
                WorldPoint worldPoint = unpackWorldPoint(clickboxHandler.getPackedLocation());
                if (worldPoint != null) {
                    LocalPoint lp = LocalPoint.fromWorld(client, worldPoint);
                    if (lp != null) {
                        TileObject obj = findObjectAt(worldPoint, lp, clickboxHandler.getTargetId());
                        if (obj != null) {
                            shape = obj.getClickbox();
                        }
                    }
                }
                targetExists = (shape != null);
                break;
        }

        // Send frame-perfect shape to Python IMMEDIATELY
        clickboxHandler.sendUpdate(shape, targetExists);

        // Draw if debug visualization is enabled
        if (clickboxHandler.isDebugEnabled() && shape != null) {
            Color color = targetExists
                    ? clickboxHandler.getDebugColorActive()
                    : clickboxHandler.getDebugColorMissing();
            g.setColor(color);
            g.setStroke(new BasicStroke(2));
            g.draw(shape);
        }

        return null;
    }

    /**
     * Unpack WorldPoint from packed int32 (plane, x, y)
     * Must match ClickboxHandler's unpacking logic
     */
    private WorldPoint unpackWorldPoint(long packed) {
        if (packed == 0) return null;
        int packedInt = (int) packed;
        int x = packedInt & 0x7FFF;
        int y = (packedInt >> 15) & 0x7FFF;
        int plane = (packedInt >> 30) & 0x3;
        return new WorldPoint(x, y, plane);
    }

    /**
     * Find NPC by server index (not array position!)
     * NPCs are sparse in the list - must search by getIndex() value
     */
    private NPC findNpcByIndex(int serverIndex) {
        WorldView wv = client.getTopLevelWorldView();
        if (wv == null) return null;
        for (NPC npc : wv.npcs()) {
            if (npc != null && npc.getIndex() == serverIndex) {
                return npc;
            }
        }
        return null;
    }

    /**
     * Find object at world point with matching ID
     */
    private TileObject findObjectAt(WorldPoint worldPoint, LocalPoint lp, int targetId) {
        WorldView wv = client.getTopLevelWorldView();
        if (wv == null) return null;
        Scene scene = wv.getScene();
        if (scene == null) return null;

        Tile tile = scene.getTiles()[worldPoint.getPlane()][lp.getSceneX()][lp.getSceneY()];
        if (tile == null) return null;

        return findObjectOnTile(tile, targetId);
    }

    /**
     * Search tile for object with matching ID
     */
    private TileObject findObjectOnTile(Tile tile, int objectId) {
        // Check GameObject
        GameObject[] gameObjects = tile.getGameObjects();
        if (gameObjects != null) {
            for (GameObject obj : gameObjects) {
                if (obj != null && obj.getId() == objectId) {
                    return obj;
                }
            }
        }

        // Check WallObject
        WallObject wall = tile.getWallObject();
        if (wall != null && wall.getId() == objectId) {
            return wall;
        }

        // Check DecorativeObject
        DecorativeObject decor = tile.getDecorativeObject();
        if (decor != null && decor.getId() == objectId) {
            return decor;
        }

        // Check GroundObject
        GroundObject ground = tile.getGroundObject();
        if (ground != null && ground.getId() == objectId) {
            return ground;
        }

        return null;
    }
}
