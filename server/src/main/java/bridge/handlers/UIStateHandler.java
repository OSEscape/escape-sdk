package bridge.handlers;

import bridge.proto.v1.*;
import java.util.HashSet;
import java.util.Set;

/**
 * UIStateHandler - Manages UI state tracking and widget events.
 *
 * Responsibilities:
 * - Track open widget groups (interface IDs)
 * - Stream widget loaded/closed events
 * - Provide active widget snapshot for subscriptions
 *
 * Thread Safety:
 * - Uses HashSet for widget group tracking
 * - All methods called from client thread via BridgePlugin
 */
public class UIStateHandler implements EventHandler {
    private final SubscribeHandler subscribeHandler;
    private final Set<Integer> activeWidgetGroups;

    public UIStateHandler(SubscribeHandler subscribeHandler) {
        this.subscribeHandler = subscribeHandler;
        this.activeWidgetGroups = new HashSet<>();
    }

    @Override
    public void initialize() {
        activeWidgetGroups.clear();
    }

    @Override
    public void shutdown() {
        activeWidgetGroups.clear();
    }

    @Override
    public String getName() {
        return "UIStateHandler";
    }

    /**
     * Handle widget loaded event (called from BridgePlugin.onWidgetLoaded)
     * @param event WidgetLoaded event from RuneLite
     */
    public void onWidgetLoaded(net.runelite.api.events.WidgetLoaded event) {
        activeWidgetGroups.add(event.getGroupId());
        sendActiveWidgetGroups();
    }

    /**
     * Handle widget closed event (called from BridgePlugin.onWidgetClosed)
     * @param event WidgetClosed event from RuneLite
     */
    public void onWidgetClosed(net.runelite.api.events.WidgetClosed event) {
        activeWidgetGroups.remove(event.getGroupId());
        sendActiveWidgetGroups();
    }

    /**
     * Send current active widget groups to stream
     */
    private void sendActiveWidgetGroups() {
        ActiveInterfacesUpdate.Builder builder = ActiveInterfacesUpdate.newBuilder();
        for (Integer groupId : activeWidgetGroups) {
            builder.addActiveInterfaces(groupId);
        }
        subscribeHandler.send(builder.build());
    }

    /**
     * Get active widget groups for snapshots
     * @return Set of active widget group IDs
     */
    public Set<Integer> getActiveWidgetGroups() {
        return activeWidgetGroups;
    }
}
