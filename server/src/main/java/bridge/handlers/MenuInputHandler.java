package bridge.handlers;

import bridge.proto.v1.*;
import net.runelite.api.Client;
import net.runelite.api.Menu;
import net.runelite.api.MenuEntry;
import net.runelite.api.Tile;
import net.runelite.api.WorldView;
import net.runelite.api.coords.WorldPoint;
import net.runelite.api.widgets.Widget;
import net.runelite.client.util.Text;

/**
 * MenuInputHandler - Manages menu state tracking and input events.
 *
 * Responsibilities:
 * - Track menu open/close state with dimensions
 * - Track selected widget state
 * - Track menu entries with hash-based change detection
 * - Stream menu option click events with context
 *
 * Thread Safety:
 * - All state accessed from client thread via BridgePlugin
 * - Hash-based change detection avoids redundant menu updates
 */
public class MenuInputHandler implements EventHandler {
    private final Client client;
    private final SubscribeHandler subscribeHandler;

    // Menu state tracking
    private int lastMenuHash = 0;
    private boolean lastMenuOpen = false;
    private int lastSelectedWidget = -1;
    private int lastSubMenuState = 0;

    public MenuInputHandler(Client client, SubscribeHandler subscribeHandler) {
        this.client = client;
        this.subscribeHandler = subscribeHandler;
    }

    @Override
    public void initialize() {
        lastMenuHash = 0;
        lastMenuOpen = false;
        lastSelectedWidget = -1;
        lastSubMenuState = 0;
    }

    @Override
    public void shutdown() {
        // No cleanup needed
    }

    @Override
    public String getName() {
        return "MenuInputHandler";
    }

    /**
     * Handle menu option clicked event (called from BridgePlugin.onMenuOptionClicked)
     * @param event MenuOptionClicked event from RuneLite
     */
    public void onMenuOptionClicked(net.runelite.api.events.MenuOptionClicked event) {
        int clickLocation = 0;
        if (event.getMenuAction() == net.runelite.api.MenuAction.WALK)
        {
            WorldView wv = client.getTopLevelWorldView();
            Tile tile = wv != null ? wv.getSelectedSceneTile() : null;
            if (tile != null)
            {
                WorldPoint wp = tile.getWorldLocation();
                clickLocation = packWorldPoint(wp);
            }
        }

        int widgetId = event.getWidget() != null ? event.getWidget().getId() : -1;

        MenuOptionClickUpdate msg = MenuOptionClickUpdate.newBuilder()
            .setMenuOption(Text.removeTags(event.getMenuOption()))
            .setMenuTarget(Text.removeTags(event.getMenuTarget()))
            .setId(event.getId())
            .setWidgetId(widgetId)
            .setParam0(event.getParam0())
            .setParam1(event.getParam1())
            .setMenuAction(event.getMenuAction().toString())
            .setClickLocation(clickLocation)
            .build();
        subscribeHandler.send(msg);
    }

    /**
     * Handle PostMenuSort event with hash-based change detection
     * Only sends updates when menu content actually changes
     * @param event PostMenuSort event from RuneLite
     */
    public void onPostMenuSort(net.runelite.api.events.PostMenuSort event) {
        // Don't process if menu is open (entries won't change anyway)
        if (client.isMenuOpen()) {
            return;
        }

        MenuEntry[] entries = client.getMenuEntries();

        // Compute lightweight hash of menu state (length + first/last entries + submenu presence)
        // This catches 99.9% of changes with minimal CPU cost
        int currentHash = entries.length;
        int subMenuHash = 0;
        if (entries.length > 0) {
            MenuEntry first = entries[0];
            MenuEntry last = entries[entries.length - 1];

            // XOR hash combining length, first and last entry details
            currentHash = 31 * currentHash + (first.getOption() != null ? first.getOption().hashCode() : 0);
            currentHash = 31 * currentHash + (first.getTarget() != null ? first.getTarget().hashCode() : 0);
            currentHash = 31 * currentHash + first.getType().hashCode();

            if (entries.length > 1) {
                currentHash = 31 * currentHash + (last.getOption() != null ? last.getOption().hashCode() : 0);
                currentHash = 31 * currentHash + (last.getTarget() != null ? last.getTarget().hashCode() : 0);
                currentHash = 31 * currentHash + last.getType().hashCode();
            }

            // Include submenu entry counts in hash
            for (int i = 0; i < entries.length; i++) {
                Menu subMenu = entries[i].getSubMenu();
                if (subMenu != null) {
                    MenuEntry[] subEntries = subMenu.getMenuEntries();
                    subMenuHash = 31 * subMenuHash + i;
                    subMenuHash = 31 * subMenuHash + subEntries.length;
                }
            }
        }
        currentHash = 31 * currentHash + subMenuHash;

        // Only fire event if menu actually changed
        if (currentHash == lastMenuHash) {
            return;  // No change, skip event
        }
        lastMenuHash = currentHash;

        // Menu changed - serialize and send
        PostMenuSortUpdate.Builder builder = PostMenuSortUpdate.newBuilder();
        for (int i = 0; i < entries.length; i++) {
            MenuEntry entry = entries[i];
            builder.addOptions(Text.removeTags(entry.getOption()));
            builder.addTargets(Text.removeTags(entry.getTarget()));
            builder.addMenuActions(entry.getType().toString());

            Menu subMenu = entry.getSubMenu();
            if (subMenu != null) {
                MenuEntry[] subEntries = subMenu.getMenuEntries();
                if (subEntries.length > 0) {
                    SubMenu.Builder subBuilder = SubMenu.newBuilder()
                        .setParentIndex(i);
                    for (MenuEntry subEntry : subEntries) {
                        subBuilder.addOptions(Text.removeTags(subEntry.getOption()));
                        subBuilder.addTargets(Text.removeTags(subEntry.getTarget()));
                        subBuilder.addMenuActions(subEntry.getType().toString());
                    }
                    builder.addSubMenus(subBuilder.build());
                }
            }
        }
        subscribeHandler.send(builder.build());
    }

    /**
     * Build MenuOpenUpdate for current menu state, including submenu coordinates
     * @return MenuOpenUpdate with menu state
     */
    public MenuOpenUpdate buildMenuOpenUpdate() {
        boolean menu_open = client.isMenuOpen();
        Menu menu = client.getMenu();
        MenuOpenUpdate.Builder builder = MenuOpenUpdate.newBuilder()
            .setMenuOpen(menu_open)
            .setMenuX(menu.getMenuX())
            .setMenuY(menu.getMenuY())
            .setMenuWidth(menu.getMenuWidth())
            .setMenuHeight(menu.getMenuHeight())
            .setScrollable(client.isMenuScrollable());

        if (menu_open) {
            MenuEntry[] entries = client.getMenuEntries();
            for (MenuEntry entry : entries) {
                Menu subMenu = entry.getSubMenu();
                if (subMenu != null && subMenu.getMenuWidth() > 0) {
                    builder.setHasSubMenu(true)
                        .setSubMenuX(subMenu.getMenuX())
                        .setSubMenuY(subMenu.getMenuY())
                        .setSubMenuWidth(subMenu.getMenuWidth())
                        .setSubMenuHeight(subMenu.getMenuHeight());
                    break;
                }
            }
        }

        return builder.build();
    }

    /**
     * Build SelectedWidgetUpdate for current selected widget
     * @return SelectedWidgetUpdate with selected widget state
     */
    public SelectedWidgetUpdate buildSelectedWidgetUpdate() {
        int selectedWidgetId;
        int index;
        Widget selectedWidget = client.getSelectedWidget();
        if (selectedWidget != null) {
            selectedWidgetId = selectedWidget.getId();
            index = selectedWidget.getIndex();
        } else {
            selectedWidgetId = -1;
            index = -1;
        }

        return SelectedWidgetUpdate.newBuilder()
            .setSelectedWidgetId(selectedWidgetId)
            .setIndex(index)
            .build();
    }

    /**
     * Handle ClientTick menu open/close and submenu tracking
     * Called from BridgePlugin.onClientTick
     */
    public void onClientTickMenu() {
        boolean menu_open = client.isMenuOpen();
        if (menu_open != lastMenuOpen) {
            lastMenuOpen = menu_open;
            lastSubMenuState = 0;
            subscribeHandler.send(buildMenuOpenUpdate());
        } else if (menu_open) {
            // While menu is open, detect submenu appearance/disappearance
            int subState = computeSubMenuState();
            if (subState != lastSubMenuState) {
                lastSubMenuState = subState;
                subscribeHandler.send(buildMenuOpenUpdate());
            }
        }
    }

    private int computeSubMenuState() {
        MenuEntry[] entries = client.getMenuEntries();
        for (MenuEntry entry : entries) {
            Menu subMenu = entry.getSubMenu();
            if (subMenu != null && subMenu.getMenuWidth() > 0) {
                return 31 * subMenu.getMenuX() + subMenu.getMenuY() + subMenu.getMenuWidth();
            }
        }
        return 0;
    }

    /**
     * Handle ClientTick selected widget tracking
     * Called from BridgePlugin.onClientTick
     */
    public void onClientTickSelectedWidget() {
        SelectedWidgetUpdate msg = buildSelectedWidgetUpdate();
        int selectedWidgetId = msg.getSelectedWidgetId();

        if (selectedWidgetId != lastSelectedWidget) {
            lastSelectedWidget = selectedWidgetId;
            subscribeHandler.send(msg);
        }
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
