package bridge;

import bridge.proto.v1.*;
import net.runelite.api.*;
import net.runelite.api.coords.*;
import net.runelite.api.events.*;
import net.runelite.client.util.Text;
import java.util.*;

/**
 * GroundItemStreamer - Streams ground items across all loaded tiles
 *
 * This class maintains a map of all ground items visible to the client.
 * It receives forwarded events from EventBusListener (not direct @Subscribe).
 *
 * Data Structure:
 * - Key: Packed WorldPoint (int) from Utils.packWorldPoint()
 * - Value: List of item maps, each containing {id, quantity, owner}
 *
 * Thread Safety:
 * - All methods are called from the client thread via EventBusListener
 * - No synchronization needed
 */
public class GroundItemStreamer {
    private final Client client;
    private boolean enabled = false;
    private boolean dirty = false;

    // Map of packed coordinates -> list of items at that tile
    // Key: int (packed WorldPoint), Value: List<Map<Object, Object>> where each map is {id, quantity, owner}
    private final Map<Object, Object> groundItems;

    /**
     * Constructor
     * @param client RuneLite Client instance
     */
    public GroundItemStreamer(Client client) {
        this.client = client;
        this.groundItems = new HashMap<>();
    }

    /**
     * Pack a WorldPoint into a single integer key
     * @param wp WorldPoint to pack
     * @return Packed coordinate as int
     */
    private int packTile(WorldPoint wp) {
        if (wp == null) return 0;
        return (wp.getX() & 0x7FFF) | ((wp.getY() & 0x7FFF) << 15) | ((wp.getPlane() & 0x3) << 30);
    }

    /**
     * Get or create the list of items for a given tile
     * @param key Packed tile coordinate
     * @return List of item maps
     */
    @SuppressWarnings("unchecked")
    private List<Map<Object, Object>> getOrCreateList(int key) {
        Object existingList = groundItems.get(key);
        if (existingList instanceof List) {
            return (List<Map<Object, Object>>) existingList;
        }

        List<Map<Object, Object>> newList = new ArrayList<>();
        groundItems.put(key, newList);
        return newList;
    }

    /**
     * Initialize by scanning all loaded tiles in the scene
     * Can be called from Python via bridge or when needed
     */
    public void rebuildFromScene() {
        groundItems.clear();

        WorldView wv = client.getTopLevelWorldView();
        Scene scene = wv != null ? wv.getScene() : null;
        if (scene == null) {
            return;
        }

        Tile[][][] tiles = scene.getTiles();
        if (tiles == null) {
            return;
        }

        for (int plane = 0; plane < tiles.length; plane++) {
            Tile[][] planeTiles = tiles[plane];
            if (planeTiles == null) {
                continue;
            }

            for (int x = 0; x < planeTiles.length; x++) {
                Tile[] row = planeTiles[x];
                if (row == null) {
                    continue;
                }

                for (int y = 0; y < row.length; y++) {
                    Tile tile = row[y];
                    if (tile == null) {
                        continue;
                    }

                    List<TileItem> items = tile.getGroundItems();
                    if (items == null || items.isEmpty()) {
                        continue;
                    }

                    WorldPoint wp = tile.getWorldLocation();
                    int key = packTile(wp);

                    List<Map<Object, Object>> list = getOrCreateList(key);
                    for (TileItem ti : items) {
                        Map<Object, Object> itemData = new HashMap<>();
                        int id = ti.getId();
                        itemData.put("id", id);
                        ItemComposition comp = client.getItemDefinition(id);
                        itemData.put("name", Text.removeTags(comp.getName()));
                        itemData.put("quantity", ti.getQuantity());
                        itemData.put("ownership", ti.getOwnership());
                        list.add(itemData);
                    }
                }
            }
        }
    }

    /**
     * Handle item spawned event (forwarded from EventBusListener)
     * Refreshes the entire tile instead of tracking individual items
     * @param event ItemSpawned event
     */
    public void onItemSpawned(ItemSpawned event) {
        refreshTile(event.getTile());
        dirty = true;
    }

    /**
     * Handle item despawned event (forwarded from EventBusListener)
     * Refreshes the entire tile instead of tracking individual items
     * @param event ItemDespawned event
     */
    public void onItemDespawned(ItemDespawned event) {
        refreshTile(event.getTile());
        dirty = true;
    }

    /**
     * Handle item quantity changed event (forwarded from EventBusListener)
     * Refreshes the entire tile instead of tracking individual items
     * @param event ItemQuantityChanged event
     */
    public void onItemQuantityChanged(ItemQuantityChanged event) {
        refreshTile(event.getTile());
        dirty = true;
    }

    public boolean isDirty() {
        return dirty;
    }

    public void clearDirty() {
        dirty = false;
    }

    /**
     * Refresh a single tile by reading all ground items on it
     * If tile has no items, removes it from tracking
     * @param tile The tile to refresh
     */
    private void refreshTile(Tile tile) {
        if (tile == null) {
            return;
        }

        WorldPoint wp = tile.getWorldLocation();
        int key = packTile(wp);

        List<TileItem> items = tile.getGroundItems();

        // If no items on tile, remove it from tracking
        if (items == null || items.isEmpty()) {
            groundItems.remove(key);
            return;
        }

        // Rebuild the item list for this tile
        List<Map<Object, Object>> list = new ArrayList<>();
        for (TileItem ti : items) {
            Map<Object, Object> itemData = new HashMap<>();
            int id = ti.getId();
            itemData.put("id", id);
            ItemComposition comp = client.getItemDefinition(id);
            itemData.put("name", Text.removeTags(comp.getName()));
            itemData.put("quantity", ti.getQuantity());
            itemData.put("ownership", ti.getOwnership());
            list.add(itemData);
        }

        groundItems.put(key, list);
    }

    /**
     * Get all ground items as protobuf messages
     * @return List of GroundItem protobuf messages
     */
    @SuppressWarnings("unchecked")
    public java.util.List<GroundItem> getGroundItems() {
        java.util.List<GroundItem> result = new ArrayList<>();

        for (Map.Entry<Object, Object> entry : groundItems.entrySet()) {
            int packedLocation = (Integer) entry.getKey();
            Object listObj = entry.getValue();

            if (listObj instanceof List) {
                List<Map<Object, Object>> itemList = (List<Map<Object, Object>>) listObj;
                for (Map<Object, Object> itemData : itemList) {
                    int id = (Integer) itemData.get("id");
                    String name = (String) itemData.get("name");
                    int quantity = (Integer) itemData.get("quantity");
                    int ownership = (Integer) itemData.get("ownership");

                    GroundItem groundItem = GroundItem.newBuilder()
                        .setId(id)
                        .setQuantity(quantity)
                        .setName(name)
                        .setPackedLocation(packedLocation)
                        .setOwnership(ownership)
                        .build();

                    result.add(groundItem);
                }
            }
        }

        return result;
    }

    /**
     * Get ground items at a specific tile
     * @param packedCoord Packed coordinate from Utils.packWorldPoint()
     * @return List of item maps, or null if no items at that tile
     */
    @SuppressWarnings("unchecked")
    public List<Map<Object, Object>> getItemsAtTile(int packedCoord) {
        Object listObj = groundItems.get(packedCoord);
        if (listObj instanceof List) {
            return (List<Map<Object, Object>>) listObj;
        }
        return null;
    }

    /**
     * Get ground items at a specific WorldPoint
     * @param wp WorldPoint to query
     * @return List of item maps, or null if no items at that tile
     */
    public List<Map<Object, Object>> getItemsAtTile(WorldPoint wp) {
        return getItemsAtTile(packTile(wp));
    }

    /**
     * Clear all tracked ground items
     */
    public void clear() {
        groundItems.clear();
    }

    /**
     * Get the number of unique tiles with ground items
     * @return Count of tiles with items
     */
    public int getTileCount() {
        return groundItems.size();
    }

    /**
     * Get the total number of ground items tracked
     * @return Total item count across all tiles
     */
    @SuppressWarnings("unchecked")
    public int getTotalItemCount() {
        int count = 0;
        for (Object listObj : groundItems.values()) {
            if (listObj instanceof List) {
                count += ((List<?>) listObj).size();
            }
        }
        return count;
    }

    // --- Subscribe-as-you-go ---

    public java.util.List<GroundItem> enable() {
        enabled = true;
        rebuildFromScene();
        return getGroundItems();
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void disable() {
        enabled = false;
        groundItems.clear();
    }
}