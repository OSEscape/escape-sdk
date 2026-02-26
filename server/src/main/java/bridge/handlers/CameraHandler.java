package bridge.handlers;

import bridge.proto.v1.*;
import net.runelite.api.Client;
import net.runelite.api.Perspective;
import net.runelite.api.Player;
import net.runelite.api.WorldEntity;
import net.runelite.api.WorldView;
import net.runelite.api.coords.LocalPoint;

/**
 * CameraHandler - Manages camera state and WorldEntity position tracking.
 *
 * Responsibilities:
 * - Track camera position changes (X, Y, Z)
 * - Track camera orientation changes (pitch, yaw, scale)
 * - Track WorldEntity position/orientation changes
 * - Detect changes and stream updates
 *
 * Thread Safety:
 * - All state accessed from client thread via BridgePlugin
 * - State fields track last known values for change detection
 */
public class CameraHandler implements EventHandler {
    private final Client client;
    private final SubscribeHandler subscribeHandler;

    // Camera state tracking
    private int lastCameraX = Integer.MIN_VALUE;
    private int lastCameraY = Integer.MIN_VALUE;
    private int lastCameraZ = Integer.MIN_VALUE;
    private int lastCameraPitch = Integer.MIN_VALUE;
    private int lastCameraYaw = Integer.MIN_VALUE;
    private int lastScale = Integer.MIN_VALUE;

    // WorldEntity state tracking
    private int lastEntityX = Integer.MIN_VALUE;
    private int lastEntityY = Integer.MIN_VALUE;
    private int lastEntityOrientation = Integer.MIN_VALUE;
    private int lastGroundHeightOffset = Integer.MIN_VALUE;

    public CameraHandler(Client client, SubscribeHandler subscribeHandler) {
        this.client = client;
        this.subscribeHandler = subscribeHandler;
    }

    @Override
    public void initialize() {
        // Reset state tracking
        lastCameraX = Integer.MIN_VALUE;
        lastCameraY = Integer.MIN_VALUE;
        lastCameraZ = Integer.MIN_VALUE;
        lastCameraPitch = Integer.MIN_VALUE;
        lastCameraYaw = Integer.MIN_VALUE;
        lastScale = Integer.MIN_VALUE;
        lastEntityX = Integer.MIN_VALUE;
        lastEntityY = Integer.MIN_VALUE;
        lastEntityOrientation = Integer.MIN_VALUE;
        lastGroundHeightOffset = Integer.MIN_VALUE;
    }

    @Override
    public void shutdown() {
        // No cleanup needed
    }

    @Override
    public String getName() {
        return "CameraHandler";
    }

    /**
     * Build CameraChanged message for current camera state
     * @return CameraChanged with position and orientation
     */
    public bridge.proto.v1.CameraChanged buildCameraChanged() {
        int cameraX = client.getCameraX();
        int cameraY = client.getCameraY();
        int cameraZ = client.getCameraZ();
        int cameraPitch = client.getCameraPitch();
        int cameraYaw = client.getCameraYaw();
        int scale = client.getScale();

        return bridge.proto.v1.CameraChanged.newBuilder()
            .setCameraX(cameraX)
            .setCameraY(cameraY)
            .setCameraZ(cameraZ)
            .setPitch(cameraPitch * Math.PI / 1024.0)
            .setYaw(cameraYaw * Math.PI / 1024.0)
            .setScale(scale)
            .build();
    }

    /**
     * Handle client tick for camera tracking (called from BridgePlugin.onClientTick)
     * Detects camera position/orientation changes and streams updates
     */
    public void onClientTickCamera() {
        // Camera state change detection
        int cameraX = client.getCameraX();
        int cameraY = client.getCameraY();
        int cameraZ = client.getCameraZ();
        int cameraPitch = client.getCameraPitch();
        int cameraYaw = client.getCameraYaw();
        int scale = client.getScale();

        if (cameraX != lastCameraX || cameraY != lastCameraY || cameraZ != lastCameraZ ||
            cameraPitch != lastCameraPitch || cameraYaw != lastCameraYaw || scale != lastScale) {

            lastCameraX = cameraX;
            lastCameraY = cameraY;
            lastCameraZ = cameraZ;
            lastCameraPitch = cameraPitch;
            lastCameraYaw = cameraYaw;
            lastScale = scale;

            bridge.proto.v1.CameraChanged msg = buildCameraChanged();
            subscribeHandler.send(msg);
        }
    }

    /**
     * Build WorldEntityUpdate for current player's world entity
     * @return WorldEntityUpdate or null if not in an instanced area
     */
    public WorldEntityUpdate buildWorldEntityUpdate() {
        Player player = client.getLocalPlayer();
        if (player == null) {
            return null;
        }

        WorldView playerWv = player.getWorldView();
        if (playerWv == null || playerWv.isTopLevel()) {
            return null;
        }

        int wvId = playerWv.getId();
        WorldView topLevel = client.getTopLevelWorldView();
        if (topLevel == null) {
            return null;
        }

        WorldEntity we = topLevel.worldEntities().byIndex(wvId);
        if (we == null) {
            return null;
        }

        LocalPoint entityLoc = we.getLocalLocation();
        int entityX = entityLoc.getX();
        int entityY = entityLoc.getY();
        int orientation = we.getOrientation();
        int groundHeightOffset = Perspective.getTileHeight(
            client,
            entityLoc,
            topLevel.getPlane()
        );

        return WorldEntityUpdate.newBuilder()
            .setEntityX(entityX)
            .setEntityY(entityY)
            .setOrientation(orientation)
            .setGroundHeightOffset(groundHeightOffset)
            .build();
    }

    /**
     * Handle client tick for WorldEntity tracking (called from BridgePlugin.onClientTick)
     * Tracks WorldEntity position/orientation in instanced areas
     */
    public void onClientTickWorldEntity() {
        WorldEntityUpdate update = buildWorldEntityUpdate();
        if (update == null) {
            return;
        }

        int entityX = update.getEntityX();
        int entityY = update.getEntityY();
        int orientation = update.getOrientation();
        int groundHeightOffset = update.getGroundHeightOffset();

        // Only send if changed
        if (entityX != lastEntityX || entityY != lastEntityY ||
            orientation != lastEntityOrientation || groundHeightOffset != lastGroundHeightOffset) {
            lastEntityX = entityX;
            lastEntityY = entityY;
            lastEntityOrientation = orientation;
            lastGroundHeightOffset = groundHeightOffset;

            subscribeHandler.send(update);
        }
    }
}
