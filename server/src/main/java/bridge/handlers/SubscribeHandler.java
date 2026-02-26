package bridge.handlers;

import bridge.*;
import bridge.proto.v1.*;
import io.grpc.stub.StreamObserver;
import net.runelite.api.Client;

import net.runelite.client.callback.ClientThread;
import net.runelite.client.util.Text;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.atomic.AtomicLong;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class SubscribeHandler {
    private static final Logger log = LoggerFactory.getLogger(SubscribeHandler.class);
    private static final int BROADCAST_QUEUE_CAPACITY = 4096;

    private final Client client;
    private final ClientThread clientThread;
    private final BridgePlugin plugin;

    private final Set<StreamObserver<ServerMessage>> subscribers = ConcurrentHashMap.newKeySet();
    private final AtomicLong lastInventoryHash = new AtomicLong(0);
    private final LinkedBlockingQueue<ServerMessage> broadcastQueue = new LinkedBlockingQueue<>(BROADCAST_QUEUE_CAPACITY);
    private volatile Thread drainThread;

    public SubscribeHandler(Client client, ClientThread clientThread, BridgePlugin plugin) {
        this.client = client;
        this.clientThread = clientThread;
        this.plugin = plugin;
    }

    public void subscribe(StreamObserver<ServerMessage> observer, SubscriptionOptions options) {
        // Don't add to subscribers yet — warmup snapshots call observer.onNext()
        // directly from the clientThread, and the drain thread also calls onNext()
        // on subscribers. StreamObserver.onNext() is not thread-safe, so we must
        // avoid concurrent calls by deferring the add until after warmup completes.
        ensureDrainThread();

        clientThread.invoke(() -> {
            try {
                sendInitialGameState(observer);
                sendVarpSnapshot(observer);
                sendChatSnapshot(observer);
                sendStatsSnapshot(observer);
                sendVarcIntSnapshot(observer);
                sendVarcStrSnapshot(observer);
                sendInterfaceSnapshot(observer);
                sendGameTickSnapshot(observer);
                sendCameraSnapshot(observer);
                sendMenuOpenSnapshot(observer);
                sendSelectedWidgetSnapshot(observer);
                sendWorldViewLoadSnapshot(observer);
                sendWorldEntitySnapshot(observer);
                sendBankSnapshot(observer);

                // Signal warmup complete - all snapshots sent
                observer.onNext(ServerMessage.newBuilder()
                    .setWarmupComplete(WarmupComplete.newBuilder().build())
                    .build());

                // Now safe to add — no more direct onNext() from this thread
                subscribers.add(observer);
                ensureDrainThread();
            } catch (Exception e) {
                observer.onError(e);
            }
        });
    }

    public void unsubscribe(StreamObserver<ServerMessage> observer) {
        subscribers.remove(observer);
        if (subscribers.isEmpty()) {
            plugin.getWorldHandler().clearSubscriptions();
        }
    }

    public boolean hasSubscribers() {
        return !subscribers.isEmpty();
    }

    private void sendInitialGameState(StreamObserver<ServerMessage> observer) {
        observer.onNext(ServerMessage.newBuilder()
            .setGameStateChange(GameStateChange.newBuilder()
                .setState(client.getGameState().toString())
                .build())
            .build());
    }

    // Snapshot builders
    private void sendVarpSnapshot(StreamObserver<ServerMessage> observer) {
        var builder = VarpSnapshot.newBuilder();
        int[] varps = client.getVarps();

        if (varps != null) {
            for (int varpId = 0; varpId < varps.length; varpId++) {
                int value = varps[varpId];
                if (value != 0) {  // Only send non-zero varps
                    builder.addVarps(Varp.newBuilder()
                        .setVarpId(varpId)
                        .setVarbitId(0)  // Varp, not varbit
                        .setValue(value)
                        .build());
                }
            }
        }

        observer.onNext(ServerMessage.newBuilder().setSnapshot(builder.build()).build());
    }

    private void sendChatSnapshot(StreamObserver<ServerMessage> observer) {
        var builder = ChatSnapshot.newBuilder();

        // Read from BridgePlugin chat history
        int count = 0;
        for (net.runelite.api.events.ChatMessage msg : plugin.getChatHistory()) {
            builder.addMessages(bridge.proto.v1.ChatMessage.newBuilder()
                .setType(msg.getType().name())
                .setSender(Text.removeTags(msg.getName()))
                .setMessage(Text.removeTags(msg.getMessage()))
                .build());
            count++;
        }

        observer.onNext(ServerMessage.newBuilder().setChatSnapshot(builder.build()).build());
    }

    private void sendStatsSnapshot(StreamObserver<ServerMessage> observer) {
        var builder = StatsSnapshot.newBuilder();

        int[] realLevels = client.getRealSkillLevels();
        int[] boostedLevels = client.getBoostedSkillLevels();
        int[] experiences = client.getSkillExperiences();

        // Handle not logged in case
        if (realLevels == null || boostedLevels == null || experiences == null) {
            observer.onNext(ServerMessage.newBuilder()
                .setStatSnapshot(builder.build())  // Empty snapshot
                .build());
            return;
        }

        // Skill enum order matches array indices
        for (net.runelite.api.Skill skill : net.runelite.api.Skill.values()) {
            int ordinal = skill.ordinal();
            builder.addStats(Stat.newBuilder()
                .setSkill(skill.getName())
                .setLevel(realLevels[ordinal])
                .setBoostedLevel(boostedLevels[ordinal])
                .setXp(experiences[ordinal])
                .build());
        }

        observer.onNext(ServerMessage.newBuilder().setStatSnapshot(builder.build()).build());
    }

    private void sendVarcIntSnapshot(StreamObserver<ServerMessage> observer) {
        var builder = VarcIntSnapshot.newBuilder();

        // Read from BridgePlugin cache
        for (var entry : plugin.getVarcIntCache().entrySet()) {
            builder.addVarcs(VarcInt.newBuilder()
                .setVarcId(entry.getKey())
                .setValue(entry.getValue())
                .build());
        }

        observer.onNext(ServerMessage.newBuilder().setVarcIntSnapshot(builder.build()).build());
    }

    private void sendVarcStrSnapshot(StreamObserver<ServerMessage> observer) {
        var builder = VarcStrSnapshot.newBuilder();

        // Read from BridgePlugin cache
        for (var entry : plugin.getVarcStrCache().entrySet()) {
            builder.addVarcs(VarcStr.newBuilder()
                .setVarcId(entry.getKey())
                .setValue(entry.getValue() == null ? "" : Text.removeTags(entry.getValue()))
                .build());
        }

        observer.onNext(ServerMessage.newBuilder().setVarcStrSnapshot(builder.build()).build());
    }

    private void sendInterfaceSnapshot(StreamObserver<ServerMessage> observer) {
        var builder = InterfaceSnapshot.newBuilder();

        // activeWidgetGroups already tracked in BridgePlugin
        for (Integer widgetId : plugin.getActiveWidgetGroups()) {
            builder.addActiveInterfaces(widgetId);
        }

        observer.onNext(ServerMessage.newBuilder().setInterfaceSnapshot(builder.build()).build());
    }

    private void sendGameTickSnapshot(StreamObserver<ServerMessage> observer) {
        GameTickUpdate update = plugin.getPlayerStateHandler().buildGameTickUpdate();
        observer.onNext(ServerMessage.newBuilder().setGameTickUpdate(update).build());
    }

    private void sendWorldViewLoadSnapshot(StreamObserver<ServerMessage> observer) {
        WorldViewLoad worldViewLoad = plugin.getWorldHandler().buildWorldViewLoad();
        observer.onNext(ServerMessage.newBuilder().setWorldViewLoad(worldViewLoad).build());
    }

    private void sendWorldEntitySnapshot(StreamObserver<ServerMessage> observer) {
        WorldEntityUpdate update = plugin.getCameraHandler().buildWorldEntityUpdate();
        if (update != null) {
            observer.onNext(ServerMessage.newBuilder().setWorldEntityUpdate(update).build());
        }
    }

    private void sendCameraSnapshot(StreamObserver<ServerMessage> observer) {
        bridge.proto.v1.CameraChanged camera = plugin.getCameraHandler().buildCameraChanged();
        observer.onNext(ServerMessage.newBuilder().setCameraChanged(camera).build());
    }

    private void sendMenuOpenSnapshot(StreamObserver<ServerMessage> observer) {
        MenuOpenUpdate menuOpen = plugin.getMenuInputHandler().buildMenuOpenUpdate();
        observer.onNext(ServerMessage.newBuilder().setMenuOpenUpdate(menuOpen).build());
    }

    private void sendBankSnapshot(StreamObserver<ServerMessage> observer) {
        bridge.proto.v1.ItemContainerChanged cached = plugin.getItemHandler().getCachedBankUpdate();
        if (cached != null) {
            observer.onNext(ServerMessage.newBuilder().setItemContainerChanged(cached).build());
        }
    }

    private void sendSelectedWidgetSnapshot(StreamObserver<ServerMessage> observer) {
        SelectedWidgetUpdate selectedWidget = plugin.getMenuInputHandler().buildSelectedWidgetUpdate();
        observer.onNext(ServerMessage.newBuilder().setSelectedWidgetUpdate(selectedWidget).build());
    }

    // Event senders - receive pre-built protobuf messages from BridgePlugin
    public void send(bridge.proto.v1.VarbitChanged event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setVarbitChanged(event).build());
    }

    public void send(bridge.proto.v1.ChatChanged event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setChatChanged(event).build());
    }

    public void send(bridge.proto.v1.StatChanged event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setStatChanged(event).build());
    }

    public void send(bridge.proto.v1.VarcIntChanged event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setVarcIntChanged(event).build());
    }

    public void send(bridge.proto.v1.VarcStrChanged event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setVarcStrChanged(event).build());
    }

    public void send(bridge.proto.v1.AnimationChanged event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setAnimationChanged(event).build());
    }

    public void send(bridge.proto.v1.ItemContainerChanged event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setItemContainerChanged(event).build());
    }

    public void send(GameTickUpdate event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setGameTickUpdate(event).build());
    }

    public void send(MenuOpenUpdate event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setMenuOpenUpdate(event).build());
    }

    public void send(SelectedWidgetUpdate event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setSelectedWidgetUpdate(event).build());
    }

    public void send(ActiveInterfacesUpdate event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setActiveInterfacesUpdate(event).build());
    }

    public void send(CameraChanged event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setCameraChanged(event).build());
    }

    public void send(WorldEntityUpdate event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setWorldEntityUpdate(event).build());
    }

    public void send(PostMenuSortUpdate event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setPostMenuSortUpdate(event).build());
    }

    public void send(MenuOptionClickUpdate event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setMenuOptionClickUpdate(event).build());
    }

    public void send(GameStateChange event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setGameStateChange(event).build());
    }

    public void send(GroundItemsUpdate event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setGroundItemsUpdate(event).build());
    }

    public void send(SceneObjectsUpdate event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setSceneObjectsUpdate(event).build());
    }

    public void send(WorldViewLoad event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setWorldViewLoad(event).build());
    }

    public void send(ClickboxUpdate event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setClickboxUpdate(event).build());
    }

    public void send(NpcUpdate event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setNpcUpdate(event).build());
    }

    public void send(CollisionUpdate event) {
        if (subscribers.isEmpty()) return;
        broadcast(ServerMessage.newBuilder().setCollisionUpdate(event).build());
    }

    // Helper methods
    private void broadcast(ServerMessage message) {
        if (!broadcastQueue.offer(message)) {
            // Queue full — drop oldest to make room (prevent game thread block)
            broadcastQueue.poll();
            broadcastQueue.offer(message);
            log.warn("Broadcast queue full, dropped oldest event");
        }
        ensureDrainThread();
    }

    private void ensureDrainThread() {
        if (drainThread != null && drainThread.isAlive()) return;
        drainThread = new Thread(() -> {
            while (!subscribers.isEmpty() || !broadcastQueue.isEmpty()) {
                try {
                    ServerMessage msg = broadcastQueue.poll(1, java.util.concurrent.TimeUnit.SECONDS);
                    if (msg == null) continue;
                    for (StreamObserver<ServerMessage> observer : subscribers) {
                        try {
                            observer.onNext(msg);
                        } catch (Exception e) {
                            subscribers.remove(observer);
                            try { observer.onError(e); } catch (Exception ignored) {}
                        }
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
            log.info("Broadcast drain thread exiting (no subscribers)");
        }, "bridge-broadcast");
        drainThread.setDaemon(true);
        drainThread.start();
    }
}
