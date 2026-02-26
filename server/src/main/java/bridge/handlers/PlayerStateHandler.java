package bridge.handlers;

import bridge.proto.v1.*;
import net.runelite.api.Actor;
import net.runelite.api.Client;
import net.runelite.api.NPC;
import net.runelite.api.Player;
import net.runelite.api.coords.LocalPoint;
import net.runelite.api.coords.WorldPoint;
import net.runelite.client.util.Text;

/**
 * PlayerStateHandler - Manages player-related state and events.
 *
 * Responsibilities:
 * - Stream game state changes (LOGGED_IN, HOPPING, etc.)
 * - Stream stat changes (skill XP/level updates)
 * - Stream animation changes (player and NPC animations)
 * - Stream game tick updates (position, energy, target)
 *
 * Thread Safety:
 * - Stateless handler (no mutable state)
 * - All events handled on client thread via BridgePlugin
 */
public class PlayerStateHandler implements EventHandler {
    private final Client client;
    private final SubscribeHandler subscribeHandler;

    public PlayerStateHandler(Client client, SubscribeHandler subscribeHandler) {
        this.client = client;
        this.subscribeHandler = subscribeHandler;
    }

    @Override
    public void initialize() {
        // No state to initialize
    }

    @Override
    public void shutdown() {
        // No state to clean up
    }

    @Override
    public String getName() {
        return "PlayerStateHandler";
    }

    /**
     * Handle game state changed event (called from BridgePlugin.onGameStateChanged)
     * @param event GameStateChanged event from RuneLite
     */
    public void onGameStateChanged(net.runelite.api.events.GameStateChanged event) {
        bridge.proto.v1.GameStateChange msg = bridge.proto.v1.GameStateChange.newBuilder()
            .setState(event.getGameState().toString())
            .build();
        subscribeHandler.send(msg);
    }

    /**
     * Handle stat changed event (called from BridgePlugin.onStatChanged)
     * @param event StatChanged event from RuneLite
     */
    public void onStatChanged(net.runelite.api.events.StatChanged event) {
        if (client == null) {
            return;
        }

        bridge.proto.v1.StatChanged msg = bridge.proto.v1.StatChanged.newBuilder()
            .setStat(Stat.newBuilder()
                .setSkill(event.getSkill().getName())
                .setXp(event.getXp())
                .setLevel(event.getLevel())
                .setBoostedLevel(event.getBoostedLevel())
                .build())
            .build();
        subscribeHandler.send(msg);
    }

    /**
     * Handle animation changed event (called from BridgePlugin.onAnimationChanged)
     * @param event AnimationChanged event from RuneLite
     */
    public void onAnimationChanged(net.runelite.api.events.AnimationChanged event) {
        Actor actor = event.getActor();
        if (actor == null) {
            return;
        }

        WorldPoint location = actor.getWorldLocation();
        bridge.proto.v1.AnimationChanged msg = bridge.proto.v1.AnimationChanged.newBuilder()
            .setActorName(Text.removeTags(actor.getName()))
            .setAnimationId(actor.getAnimation())
            .setLocation(packWorldPoint(location))
            .build();
        subscribeHandler.send(msg);
    }

    /**
     * Build current game tick update
     * @return GameTickUpdate with current game state
     */
    public GameTickUpdate buildGameTickUpdate() {
        if (client == null) {
            return GameTickUpdate.newBuilder().build();
        }

        int sceneX = 0;
        int sceneY = 0;
        int targetX = 0;
        int targetY = 0;
        int interactingIndex = -1;

        int plane = 0;
        net.runelite.api.WorldView wv = client.getTopLevelWorldView();

        Player player = client.getLocalPlayer();
        if (player != null) {
            WorldPoint wp = player.getWorldLocation();
            if (wp != null && wv != null) {
                sceneX = wp.getX() - wv.getBaseX();
                sceneY = wp.getY() - wv.getBaseY();
                plane = wp.getPlane();
            }

            LocalPoint targetPos = client.getLocalDestinationLocation();
            if (targetPos != null) {
                targetX = targetPos.getX();
                targetY = targetPos.getY();
            }

            Actor interacting = player.getInteracting();
            if (interacting instanceof NPC) {
                interactingIndex = ((NPC) interacting).getIndex();
            }
        }

        int canvasOffsetX = 0;
        int canvasOffsetY = 0;

        if (client.getCanvas() != null) {
            java.awt.Point canvasLocation = client.getCanvas().getLocation();
            if (canvasLocation != null) {
                canvasOffsetX = canvasLocation.x;
                canvasOffsetY = canvasLocation.y;
            }
        }

        return GameTickUpdate.newBuilder()
            .setTick(client.getTickCount())
            .setEnergy(client.getEnergy())
            .setSceneX(sceneX)
            .setSceneY(sceneY)
            .setTargetX(targetX)
            .setTargetY(targetY)
            .setInteractingIndex(interactingIndex)
            .setCanvasOffsetX(canvasOffsetX)
            .setCanvasOffsetY(canvasOffsetY)
            .setPlane(plane)
            .build();
    }

    /**
     * Handle game tick event (called from BridgePlugin.onGameTick)
     * @param event GameTick event from RuneLite
     */
    public void onGameTick(net.runelite.api.events.GameTick event) {
        GameTickUpdate msg = buildGameTickUpdate();
        subscribeHandler.send(msg);
    }

    /**
     * Pack WorldPoint into a single integer
     * @param wp WorldPoint to pack
     * @return Packed coordinate as int
     */
    private static int packWorldPoint(WorldPoint wp) {
        if (wp == null) return 0;
        return (wp.getX() & 0x7FFF) | ((wp.getY() & 0x7FFF) << 15) | ((wp.getPlane() & 0x3) << 30);
    }
}
