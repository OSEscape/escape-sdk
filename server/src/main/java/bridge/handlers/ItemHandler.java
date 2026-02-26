package bridge.handlers;

import bridge.proto.v1.*;
import net.runelite.api.Client;
import net.runelite.api.ItemComposition;
import net.runelite.api.ItemContainer;
import net.runelite.client.util.Text;
import java.util.ArrayList;
import java.util.List;

/**
 * ItemHandler - Manages item container events and conversions.
 *
 * Responsibilities:
 * - Stream inventory/equipment/bank container changes
 * - Convert ItemContainer to protobuf Item list
 * - Track special containers (93=inventory, 94=equipment, 95=bank)
 *
 * Thread Safety:
 * - Bank cache written on client thread, read on subscribe (client thread via invoke)
 * - All events handled on client thread via BridgePlugin
 */
public class ItemHandler implements EventHandler {
    // Special containers to track in detail (inventory, equipment, bank)
    private static final int[] SPECIAL_CONTAINERS = {93, 94, 95};
    private static final int BANK_CONTAINER_ID = 95;

    private final Client client;
    private final SubscribeHandler subscribeHandler;

    // Cache the last bank ItemContainerChanged so it can be replayed on subscribe
    private volatile bridge.proto.v1.ItemContainerChanged cachedBankUpdate;

    public ItemHandler(Client client, SubscribeHandler subscribeHandler) {
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
        return "ItemHandler";
    }

    public bridge.proto.v1.ItemContainerChanged getCachedBankUpdate() {
        return cachedBankUpdate;
    }

    /**
     * Handle item container changed event (called from BridgePlugin.onItemContainerChanged)
     * @param event ItemContainerChanged event from RuneLite
     */
    public void onItemContainerChanged(net.runelite.api.events.ItemContainerChanged event) {
        if (client == null) {
            return;
        }

        int containerId = event.getContainerId();
        ItemContainer container = event.getItemContainer();

        if (container == null) {
            return;
        }

        boolean isSpecial = isSpecialContainer(containerId);
        List<bridge.proto.v1.Item> items = convertItems(container);

        bridge.proto.v1.ItemContainerChanged msg = bridge.proto.v1.ItemContainerChanged.newBuilder()
            .setContainerId(containerId)
            .setIsSpecial(isSpecial)
            .addAllItems(items)
            .build();

        if (containerId == BANK_CONTAINER_ID) {
            cachedBankUpdate = msg;
        }

        subscribeHandler.send(msg);
    }

    /**
     * Convert ItemContainer to protobuf Item list
     * @param container ItemContainer from RuneLite
     * @return List of protobuf Item messages
     */
    private List<bridge.proto.v1.Item> convertItems(ItemContainer container) {
        List<bridge.proto.v1.Item> items = new ArrayList<>();
        net.runelite.api.Item[] containerItems = container.getItems();

        for (int i = 0; i < containerItems.length; i++) {
            int itemId = containerItems[i].getId();
            if (itemId == -1) continue;

            ItemComposition comp = client.getItemDefinition(itemId);
            items.add(bridge.proto.v1.Item.newBuilder()
                .setId(itemId)
                .setName(Text.removeTags(comp.getName()))
                .setQuantity(containerItems[i].getQuantity())
                .setNoted(comp.getNote() != -1)
                .setSlot(i)
                .build());
        }

        return items;
    }

    /**
     * Check if container ID is a special container (inventory/equipment/bank)
     * @param id Container ID
     * @return true if special container
     */
    private static boolean isSpecialContainer(int id) {
        for (int x : SPECIAL_CONTAINERS) {
            if (x == id) {
                return true;
            }
        }
        return false;
    }

    /**
     * Get item container RPC handler (callable from Python via bridge)
     * @param request GetItemContainerRequest with containerId
     * @return GetItemContainerResponse with items
     */
    public bridge.proto.v1.GetItemContainerResponse getItemContainer(bridge.proto.v1.GetItemContainerRequest request) {
        net.runelite.api.ItemContainer container = client.getItemContainer(request.getContainerId());

        bridge.proto.v1.GetItemContainerResponse.Builder builder = bridge.proto.v1.GetItemContainerResponse.newBuilder();

        if (container == null) {
            return builder.build();  // Return empty response if container doesn't exist
        }

        net.runelite.api.Item[] items = container.getItems();
        for (int i = 0; i < items.length; i++) {
            int itemId = items[i].getId();
            if (itemId == -1) continue;

            ItemComposition comp = client.getItemDefinition(itemId);
            builder.addItems(bridge.proto.v1.Item.newBuilder()
                .setId(itemId)
                .setName(Text.removeTags(comp.getName()))
                .setQuantity(items[i].getQuantity())
                .setNoted(comp.getNote() != -1)
                .setSlot(i)
                .build());
        }

        return builder.build();
    }
}
