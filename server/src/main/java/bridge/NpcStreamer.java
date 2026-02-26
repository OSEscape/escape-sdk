package bridge;

import bridge.proto.v1.*;
import net.runelite.api.*;
import net.runelite.api.coords.WorldPoint;
import net.runelite.client.util.Text;
import java.util.*;

public class NpcStreamer {
    private final Client client;
    private final Map<Integer, NPCData> trackedNpcs = new HashMap<>();
    private boolean dirty = false;

    // Subscribe-as-you-go tracked sets
    private final Set<Integer> subscribedIds = new HashSet<>();
    private final Set<String> subscribedNames = new HashSet<>();  // lowercase
    private boolean streamAll = false;

    private static class NPCData {
        final int index;
        final int id;
        final String name;
        final int worldX;
        final int worldY;
        final int plane;
        final int animation;
        final int poseAnimation;
        final int orientation;
        final int combatLevel;
        final boolean isDead;
        final int healthRatio;
        final int healthScale;
        final int interactingIndex;
        final String overheadText;
        final String[] actions;
        final int size;
        final int[] spotAnimIds;
        final int[] overheadSpriteIds;
        final int[] overheadArchiveIds;

        NPCData(int index, int id, String name,
                int worldX, int worldY, int plane,
                int animation, int poseAnimation, int orientation,
                int combatLevel, boolean isDead,
                int healthRatio, int healthScale,
                int interactingIndex, String overheadText,
                String[] actions, int size, int[] spotAnimIds,
                int[] overheadSpriteIds, int[] overheadArchiveIds) {
            this.index = index;
            this.id = id;
            this.name = name;
            this.worldX = worldX;
            this.worldY = worldY;
            this.plane = plane;
            this.animation = animation;
            this.poseAnimation = poseAnimation;
            this.orientation = orientation;
            this.combatLevel = combatLevel;
            this.isDead = isDead;
            this.healthRatio = healthRatio;
            this.healthScale = healthScale;
            this.interactingIndex = interactingIndex;
            this.overheadText = overheadText;
            this.actions = actions;
            this.size = size;
            this.spotAnimIds = spotAnimIds;
            this.overheadSpriteIds = overheadSpriteIds;
            this.overheadArchiveIds = overheadArchiveIds;
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (o == null || getClass() != o.getClass()) return false;
            NPCData d = (NPCData) o;
            return index == d.index &&
                   id == d.id &&
                   worldX == d.worldX &&
                   worldY == d.worldY &&
                   plane == d.plane &&
                   animation == d.animation &&
                   poseAnimation == d.poseAnimation &&
                   orientation == d.orientation &&
                   combatLevel == d.combatLevel &&
                   isDead == d.isDead &&
                   healthRatio == d.healthRatio &&
                   healthScale == d.healthScale &&
                   interactingIndex == d.interactingIndex &&
                   size == d.size &&
                   Objects.equals(name, d.name) &&
                   Objects.equals(overheadText, d.overheadText) &&
                   Arrays.equals(actions, d.actions) &&
                   Arrays.equals(spotAnimIds, d.spotAnimIds) &&
                   Arrays.equals(overheadSpriteIds, d.overheadSpriteIds) &&
                   Arrays.equals(overheadArchiveIds, d.overheadArchiveIds);
        }

        @Override
        public int hashCode() {
            int result = Objects.hash(index, id, name, worldX, worldY, plane,
                animation, poseAnimation, orientation, combatLevel, isDead,
                healthRatio, healthScale, interactingIndex, overheadText, size);
            result = 31 * result + Arrays.hashCode(actions);
            result = 31 * result + Arrays.hashCode(spotAnimIds);
            result = 31 * result + Arrays.hashCode(overheadSpriteIds);
            result = 31 * result + Arrays.hashCode(overheadArchiveIds);
            return result;
        }
    }

    public NpcStreamer(Client client) {
        this.client = client;
    }

    public void initialize() {
        trackedNpcs.clear();
        dirty = true;
    }

    public void clear() {
        trackedNpcs.clear();
        dirty = true;
    }

    public void onGameTick() {
        Map<Integer, NPCData> currentSnapshot = new HashMap<>();
        WorldView wv = client.getTopLevelWorldView();
        IndexedObjectSet<? extends NPC> npcs = wv != null ? wv.npcs() : null;

        if (npcs != null) {
            for (NPC npc : npcs) {
                if (npc != null) {
                    currentSnapshot.put(npc.getIndex(), captureNpcData(npc));
                }
            }
        }

        if (!currentSnapshot.equals(trackedNpcs)) {
            trackedNpcs.clear();
            trackedNpcs.putAll(currentSnapshot);
            dirty = true;
        }
    }

    private NPCData captureNpcData(NPC npc) {
        String name = npc.getName();
        if (name == null) name = "";
        else name = Text.removeTags(name);

        WorldPoint wp = npc.getWorldLocation();
        int worldX = wp != null ? wp.getX() : 0;
        int worldY = wp != null ? wp.getY() : 0;
        int plane = wp != null ? wp.getPlane() : 0;

        int interactingIndex = -1;
        Actor interacting = npc.getInteracting();
        if (interacting != null) {
            if (interacting instanceof NPC) {
                interactingIndex = ((NPC) interacting).getIndex();
            } else if (interacting instanceof Player) {
                interactingIndex = (client.getLocalPlayer() == interacting) ? -2 : -3;
            }
        }

        String overheadText = npc.getOverheadText();
        if (overheadText == null) overheadText = "";
        else overheadText = Text.removeTags(overheadText);

        // Actions from transformed composition
        String[] actions = new String[0];
        int size = 1;
        NPCComposition comp;
        try {
            comp = npc.getTransformedComposition();
        } catch (NullPointerException ignored) {
            // getTransformedComposition() throws when varps aren't loaded yet
            comp = null;
        }
        if (comp != null) {
            String[] rawActions = comp.getActions();
            if (rawActions != null) {
                actions = rawActions.clone();
                for (int i = 0; i < actions.length; i++) {
                    actions[i] = actions[i] == null ? "" : Text.removeTags(actions[i]);
                }
            }
            size = comp.getSize();
        }

        // Spot anims
        List<Integer> spotAnimList = new ArrayList<>();
        net.runelite.api.IterableHashTable<net.runelite.api.ActorSpotAnim> spotAnims = npc.getSpotAnims();
        if (spotAnims != null) {
            for (net.runelite.api.ActorSpotAnim anim : spotAnims) {
                spotAnimList.add(anim.getId());
            }
        }
        int[] spotAnimIds = spotAnimList.stream().mapToInt(Integer::intValue).toArray();

        // Overhead sprites
        short[] spriteIdsShort = npc.getOverheadSpriteIds();
        int[] spriteIds;
        if (spriteIdsShort != null) {
            spriteIds = new int[spriteIdsShort.length];
            for (int i = 0; i < spriteIdsShort.length; i++) {
                spriteIds[i] = spriteIdsShort[i];
            }
        } else {
            spriteIds = new int[0];
        }

        int[] archiveIds;
        int[] archiveIdsSource = npc.getOverheadArchiveIds();
        if (archiveIdsSource != null) {
            archiveIds = archiveIdsSource.clone();
        } else {
            archiveIds = new int[0];
        }

        return new NPCData(
            npc.getIndex(),
            npc.getId(),
            name,
            worldX, worldY, plane,
            npc.getAnimation(),
            npc.getPoseAnimation(),
            npc.getOrientation(),
            npc.getCombatLevel(),
            npc.isDead(),
            npc.getHealthRatio(),
            npc.getHealthScale(),
            interactingIndex,
            overheadText,
            actions,
            size,
            spotAnimIds,
            spriteIds,
            archiveIds
        );
    }

    public List<bridge.proto.v1.NpcData> getAllNpcs() {
        List<bridge.proto.v1.NpcData> result = new ArrayList<>();
        for (NPCData d : trackedNpcs.values()) {
            result.add(buildNpcData(d));
        }
        return result;
    }

    public int getCount() {
        return trackedNpcs.size();
    }

    public boolean isDirty() {
        return dirty;
    }

    public void clearDirty() {
        dirty = false;
    }

    // --- Subscribe-as-you-go ---

    public List<bridge.proto.v1.NpcData> streamNpcs(List<Integer> ids, List<String> names, boolean streamAll) {
        if (streamAll) this.streamAll = true;
        if (ids != null) subscribedIds.addAll(ids);
        if (names != null) {
            for (String n : names) subscribedNames.add(n.toLowerCase());
        }
        return getFilteredNpcs();
    }

    public List<bridge.proto.v1.NpcData> getFilteredNpcs() {
        if (streamAll) {
            return getAllNpcs();
        }

        if (subscribedIds.isEmpty() && subscribedNames.isEmpty()) {
            return Collections.emptyList();
        }

        List<bridge.proto.v1.NpcData> result = new ArrayList<>();
        for (NPCData d : trackedNpcs.values()) {
            if (subscribedIds.contains(d.id) ||
                subscribedNames.contains(d.name.toLowerCase())) {
                result.add(buildNpcData(d));
            }
        }
        return result;
    }

    public boolean hasSubscriptions() {
        return streamAll || !subscribedIds.isEmpty() || !subscribedNames.isEmpty();
    }

    public void clearSubscriptions() {
        subscribedIds.clear();
        subscribedNames.clear();
        streamAll = false;
    }

    private bridge.proto.v1.NpcData buildNpcData(NPCData d) {
        bridge.proto.v1.NpcData.Builder builder = bridge.proto.v1.NpcData.newBuilder()
            .setIndex(d.index)
            .setId(d.id)
            .setName(d.name)
            .setWorldX(d.worldX)
            .setWorldY(d.worldY)
            .setPlane(d.plane)
            .setAnimation(d.animation)
            .setPoseAnimation(d.poseAnimation)
            .setOrientation(d.orientation)
            .setCombatLevel(d.combatLevel)
            .setIsDead(d.isDead)
            .setHealthRatio(d.healthRatio)
            .setHealthScale(d.healthScale)
            .setInteractingIndex(d.interactingIndex)
            .setOverheadText(d.overheadText)
            .setSize(d.size);

        for (String action : d.actions) builder.addActions(action);
        for (int id : d.spotAnimIds) builder.addSpotAnimIds(id);
        for (int id : d.overheadSpriteIds) builder.addOverheadSpriteIds(id);
        for (int id : d.overheadArchiveIds) builder.addOverheadArchiveIds(id);

        return builder.build();
    }
}
