package bridge.handlers;

import bridge.proto.v1.*;
import net.runelite.api.Client;
import net.runelite.client.util.Text;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * VariableStateHandler - Manages game variable state tracking.
 *
 * Responsibilities:
 * - Track VarcInt (client integer variables) changes
 * - Track VarcStr (client string variables) changes
 * - Track Varbit (bit-packed variables) changes
 * - Maintain caches for snapshots
 * - Detect changes to avoid redundant events
 *
 * Thread Safety:
 * - Uses ConcurrentHashMap for caches (accessed from multiple threads)
 * - Uses HashMap for last value tracking (client thread only)
 */
public class VariableStateHandler implements EventHandler {
    private final Client client;
    private final SubscribeHandler subscribeHandler;

    // Change detection maps (client thread only)
    private final Map<Integer, Integer> lastVarc;
    private final Map<Integer, String> lastVarcStr;

    // Caches for snapshots (thread-safe)
    private final Map<Integer, Integer> varcIntCache;
    private final Map<Integer, String> varcStrCache;

    public VariableStateHandler(Client client, SubscribeHandler subscribeHandler) {
        this.client = client;
        this.subscribeHandler = subscribeHandler;
        this.lastVarc = new HashMap<>();
        this.lastVarcStr = new HashMap<>();
        this.varcIntCache = new ConcurrentHashMap<>();
        this.varcStrCache = new ConcurrentHashMap<>();
    }

    @Override
    public void initialize() {
        varcIntCache.clear();
        varcStrCache.clear();
        lastVarc.clear();
        lastVarcStr.clear();
    }

    @Override
    public void shutdown() {
        varcIntCache.clear();
        varcStrCache.clear();
        lastVarc.clear();
        lastVarcStr.clear();
    }

    @Override
    public String getName() {
        return "VariableStateHandler";
    }

    /**
     * Handle VarcInt changed event (called from BridgePlugin.onVarClientIntChanged)
     * @param event VarClientIntChanged event from RuneLite
     */
    public void onVarClientIntChanged(net.runelite.api.events.VarClientIntChanged event) {
        int index = event.getIndex();
        int value = client.getVarcIntValue(index);
        int prev = lastVarc.getOrDefault(index, Integer.MIN_VALUE);

        if (value == prev) {
            return;  // No change, skip event
        }
        lastVarc.put(index, value);

        // Update cache for snapshots
        varcIntCache.put(index, value);

        bridge.proto.v1.VarcIntChanged msg = bridge.proto.v1.VarcIntChanged.newBuilder()
            .setVarcIntChanged(bridge.proto.v1.VarcInt.newBuilder()
                .setVarcId(index)
                .setValue(value)
                .build())
            .build();
        subscribeHandler.send(msg);
    }

    /**
     * Handle VarcStr changed event (called from BridgePlugin.onVarClientStrChanged)
     * @param event VarClientStrChanged event from RuneLite
     */
    public void onVarClientStrChanged(net.runelite.api.events.VarClientStrChanged event) {
        int index = event.getIndex();
        String prev = lastVarcStr.getOrDefault(index, null);
        String value = client.getVarcStrValue(index);

        if (value == null ? prev == null : value.equals(prev)) {
            return;  // No change, skip event
        }
        lastVarcStr.put(index, value);

        // Update cache for snapshots
        varcStrCache.put(index, value);

        bridge.proto.v1.VarcStrChanged msg = bridge.proto.v1.VarcStrChanged.newBuilder()
            .setVarcStrChanged(bridge.proto.v1.VarcStr.newBuilder()
                .setVarcId(index)
                .setValue(value == null ? "" : Text.removeTags(value))
                .build())
            .build();
        subscribeHandler.send(msg);
    }

    /**
     * Handle Varbit changed event (called from BridgePlugin.onVarbitChanged)
     * @param event VarbitChanged event from RuneLite
     */
    public void onVarbitChanged(net.runelite.api.events.VarbitChanged event) {
        bridge.proto.v1.VarbitChanged msg = bridge.proto.v1.VarbitChanged.newBuilder()
            .setVarbitChanged(Varp.newBuilder()
                .setVarpId(event.getVarpId())
                .setVarbitId(event.getVarbitId())
                .setValue(event.getValue())
                .build())
            .build();
        subscribeHandler.send(msg);
    }

    /**
     * Get VarcInt cache for snapshots
     * @return Map of VarcInt values
     */
    public Map<Integer, Integer> getVarcIntCache() {
        return varcIntCache;
    }

    /**
     * Get VarcStr cache for snapshots
     * @return Map of VarcStr values
     */
    public Map<Integer, String> getVarcStrCache() {
        return varcStrCache;
    }
}
