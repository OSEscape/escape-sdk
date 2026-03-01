package bridge;

import bridge.handlers.*;
import bridge.proto.v1.*;
import bridge.interceptors.ExceptionInterceptor;
import bridge.interceptors.LoggingInterceptor;
import bridge.interceptors.MetadataInterceptor;
import io.grpc.Server;
import io.grpc.ServerServiceDefinition;
import io.grpc.health.v1.HealthCheckResponse.ServingStatus;
import io.grpc.netty.shaded.io.grpc.netty.NettyServerBuilder;
import io.grpc.netty.shaded.io.netty.channel.ChannelOption;
import io.grpc.netty.shaded.io.netty.channel.epoll.EpollEventLoopGroup;
import io.grpc.netty.shaded.io.netty.channel.epoll.EpollServerDomainSocketChannel;
import io.grpc.netty.shaded.io.netty.channel.unix.DomainSocketAddress;
import io.grpc.protobuf.services.HealthStatusManager;
import io.grpc.protobuf.services.ProtoReflectionService;
import net.runelite.api.Client;
import net.runelite.api.events.*;
import net.runelite.client.callback.ClientThread;
import net.runelite.client.eventbus.Subscribe;
import net.runelite.client.plugins.Plugin;
import net.runelite.client.plugins.PluginDescriptor;
import net.runelite.client.ui.overlay.OverlayManager;

import javax.inject.Inject;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.Set;
import java.util.Deque;

@PluginDescriptor(
    name = "Bridge",
    description = "Internal bridge service",
    enabledByDefault = true,
    hidden = true
)
public class BridgePlugin extends Plugin {
    private static final String SOCKET_PATH = System.getenv().getOrDefault("BRIDGE_SOCKET",
            System.getenv("XDG_RUNTIME_DIR") + "/bridge.sock");

    @Inject
    private Client client;

    @Inject
    private ClientThread clientThread;

    @Inject
    private OverlayManager overlayManager;

    private Server grpcServer;
    private HealthStatusManager healthManager;
    private EpollEventLoopGroup bossGroup;
    private EpollEventLoopGroup workerGroup;

    // Current world view index (accessed by WorldHandler)
    public int currentWorldViewIndex = -1;

    private SubscribeHandler subscribeHandler;
    private WidgetHandler widgetHandler;

    // Domain-based event handlers
    private EventHandler menuInputHandler;
    private EventHandler variableStateHandler;
    private EventHandler chatHandler;
    private EventHandler itemHandler;
    private EventHandler worldHandler;
    private EventHandler cameraHandler;
    private EventHandler playerStateHandler;
    private EventHandler uiStateHandler;
    private EventHandler clickboxHandler;
    private EventHandler drawingHandler;
    private EventHandler loginHandler;
    private EventHandler scriptHandler;

    @Override
    protected void startUp() {
        widgetHandler = new WidgetHandler(client);
        subscribeHandler = new SubscribeHandler(client, clientThread, this);

        // Initialize handlers
        chatHandler = new ChatHandler(subscribeHandler);
        itemHandler = new ItemHandler(client, subscribeHandler);
        playerStateHandler = new PlayerStateHandler(client, subscribeHandler);
        uiStateHandler = new UIStateHandler(subscribeHandler);
        variableStateHandler = new VariableStateHandler(client, subscribeHandler);
        cameraHandler = new CameraHandler(client, subscribeHandler);
        menuInputHandler = new MenuInputHandler(client, subscribeHandler);
        worldHandler = new WorldHandler(client, subscribeHandler, this);
        drawingHandler = new DrawingHandler(overlayManager);
        clickboxHandler = new ClickboxHandler(client, subscribeHandler, overlayManager);
        loginHandler = new LoginHandler(client);
        scriptHandler = new ScriptHandler(client);

        // Initialize all handlers
        chatHandler.initialize();
        itemHandler.initialize();
        playerStateHandler.initialize();
        uiStateHandler.initialize();
        variableStateHandler.initialize();
        cameraHandler.initialize();
        menuInputHandler.initialize();
        worldHandler.initialize();
        drawingHandler.initialize();
        clickboxHandler.initialize();
        loginHandler.initialize();
        scriptHandler.initialize();

        // Build service via reflection - handlers are auto-discovered by method name convention
        ServerServiceDefinition service = new ReflectiveServiceBuilder(clientThread)
            .setSubscribeHandler(subscribeHandler)
            .addHandler(widgetHandler)
            .addHandler((ItemHandler) itemHandler)
            .addHandler((ClickboxHandler) clickboxHandler)
            .addHandler((DrawingHandler) drawingHandler)
            .addHandler((WorldHandler) worldHandler)
            .addHandler((LoginHandler) loginHandler)
            .addHandler((ScriptHandler) scriptHandler)
            .build();

        ClassLoader pluginClassLoader = this.getClass().getClassLoader();

        Thread serverThread = new Thread(() -> {
            try {
                Path socketPath = Path.of(SOCKET_PATH);
                Files.deleteIfExists(socketPath);

                healthManager = new HealthStatusManager();

                // Use ThreadFactory that sets context classloader for proto class loading
                java.util.concurrent.ThreadFactory threadFactory = r -> {
                    Thread t = new Thread(r);
                    t.setContextClassLoader(pluginClassLoader);
                    return t;
                };

                // Suppress harmless SO_KEEPALIVE warning on Unix domain sockets (grpc-java #10408)
                java.util.logging.Logger.getLogger("io.grpc.netty.shaded.io.netty.bootstrap.AbstractBootstrap")
                    .setLevel(java.util.logging.Level.SEVERE);

                bossGroup = new EpollEventLoopGroup(1, threadFactory);
                workerGroup = new EpollEventLoopGroup(0, threadFactory);

                grpcServer = NettyServerBuilder.forAddress(new DomainSocketAddress(SOCKET_PATH))
                        .bossEventLoopGroup(bossGroup)
                        .workerEventLoopGroup(workerGroup)
                        .channelType(EpollServerDomainSocketChannel.class)
                        .addService(service)
                        .addService(healthManager.getHealthService())
                        .addService(ProtoReflectionService.newInstance())
                        .intercept(new ExceptionInterceptor())
                        .intercept(new LoggingInterceptor())
                        .intercept(new MetadataInterceptor())

                        .withChildOption(ChannelOption.SO_SNDBUF, 2097152)
                        .withChildOption(ChannelOption.SO_RCVBUF, 2097152)
                        .build()
                        .start();

                healthManager.setStatus("", ServingStatus.SERVING);
                healthManager.setStatus("bridge.v1.BridgeService", ServingStatus.SERVING);

                grpcServer.awaitTermination();
            } catch (Exception e) {
                e.printStackTrace();
            }
        });

        serverThread.setDaemon(true);
        serverThread.setContextClassLoader(pluginClassLoader);
        serverThread.start();
    }

    @Override
    protected void shutDown() {
        // Shutdown all handlers
        if (uiStateHandler != null) uiStateHandler.shutdown();
        if (playerStateHandler != null) playerStateHandler.shutdown();
        if (cameraHandler != null) cameraHandler.shutdown();
        if (worldHandler != null) worldHandler.shutdown();
        if (itemHandler != null) itemHandler.shutdown();
        if (chatHandler != null) chatHandler.shutdown();
        if (variableStateHandler != null) variableStateHandler.shutdown();
        if (menuInputHandler != null) menuInputHandler.shutdown();
        if (clickboxHandler != null) clickboxHandler.shutdown();
        if (drawingHandler != null) drawingHandler.shutdown();
        if (loginHandler != null) loginHandler.shutdown();
        if (scriptHandler != null) scriptHandler.shutdown();

        if (grpcServer != null) {
            if (healthManager != null) {
                healthManager.enterTerminalState();
            }
            grpcServer.shutdown();
            grpcServer = null;
        }
        if (bossGroup != null) {
            bossGroup.shutdownGracefully();
        }
        if (workerGroup != null) workerGroup.shutdownGracefully();
        try {
            Files.deleteIfExists(Path.of(SOCKET_PATH));
        } catch (Exception ignored) {
        }
    }

    // ========================================================================
    // EVENT HANDLERS (all delegate to domain-based handlers)
    // ========================================================================

    /**
     * GameStateChanged event handler - delegates to PlayerStateHandler
     */
    @Subscribe
    public void onGameStateChanged(net.runelite.api.events.GameStateChanged event) {
        ((PlayerStateHandler) playerStateHandler).onGameStateChanged(event);
    }

    /**
     * MenuOptionClicked event handler - delegates to MenuInputHandler
     */
    @Subscribe
    public void onMenuOptionClicked(MenuOptionClicked event) {
        ((MenuInputHandler) menuInputHandler).onMenuOptionClicked(event);
    }

    /**
     * VarClientIntChanged event handler - delegates to VariableStateHandler
     */
    @Subscribe
    public void onVarClientIntChanged(VarClientIntChanged event) {
        ((VariableStateHandler) variableStateHandler).onVarClientIntChanged(event);
    }

    /**
     * VarClientStrChanged event handler - delegates to VariableStateHandler
     */
    @Subscribe
    public void onVarClientStrChanged(VarClientStrChanged event) {
        ((VariableStateHandler) variableStateHandler).onVarClientStrChanged(event);
    }

    /**
     * VarbitChanged event handler - delegates to VariableStateHandler
     */
    @Subscribe
    public void onVarbitChanged(net.runelite.api.events.VarbitChanged event) {
        ((VariableStateHandler) variableStateHandler).onVarbitChanged(event);
    }

    /**
     * ChatMessage event handler - delegates to ChatHandler
     */
    @Subscribe
    public void onChatMessage(net.runelite.api.events.ChatMessage event) {
        ((ChatHandler) chatHandler).onChatMessage(event);
    }

    /**
     * ItemContainerChanged event handler - delegates to ItemHandler
     */
    @Subscribe
    public void onItemContainerChanged(net.runelite.api.events.ItemContainerChanged event) {
        ((ItemHandler) itemHandler).onItemContainerChanged(event);
    }

    /**
     * StatChanged event handler - delegates to PlayerStateHandler
     */
    @Subscribe
    public void onStatChanged(net.runelite.api.events.StatChanged event) {
        ((PlayerStateHandler) playerStateHandler).onStatChanged(event);
    }

    /**
     * AnimationChanged event handler - delegates to PlayerStateHandler
     */
    @Subscribe
    public void onAnimationChanged(net.runelite.api.events.AnimationChanged event) {
        ((PlayerStateHandler) playerStateHandler).onAnimationChanged(event);
    }

    /**
     * ClientTick event handler - delegates to MenuInputHandler and CameraHandler
     */
    @Subscribe
    public void onClientTick(ClientTick event) {
        // Delegate menu open/close tracking
        ((MenuInputHandler) menuInputHandler).onClientTickMenu();

        // Delegate selected widget tracking
        ((MenuInputHandler) menuInputHandler).onClientTickSelectedWidget();

        // Delegate camera tracking
        ((CameraHandler) cameraHandler).onClientTickCamera();

        // Delegate WorldEntity tracking
        ((CameraHandler) cameraHandler).onClientTickWorldEntity();
    }

    /**
     * PostMenuSort event handler - delegates to MenuInputHandler
     */
    @Subscribe
    public void onPostMenuSort(PostMenuSort event) {
        ((MenuInputHandler) menuInputHandler).onPostMenuSort(event);
    }

    /**
     * GameTick event handler - delegates to PlayerStateHandler and WorldHandler
     */
    @Subscribe
    public void onGameTick(GameTick event) {
        // Delegate player state tracking (position, energy, target)
        ((PlayerStateHandler) playerStateHandler).onGameTick(event);

        // Delegate collision flag diff
        ((WorldHandler) worldHandler).onGameTickCollisionSync();

        // Delegate batched scene object sync
        ((WorldHandler) worldHandler).onGameTickObjectSync();

        // Delegate batched ground item sync
        ((WorldHandler) worldHandler).onGameTickGroundItemSync();

        // Delegate NPC streaming sync
        ((WorldHandler) worldHandler).onGameTickNpcSync();
    }

    /**
     * WidgetLoaded event handler - delegates to UIStateHandler
     */
    @Subscribe
    public void onWidgetLoaded(WidgetLoaded event) {
        ((UIStateHandler) uiStateHandler).onWidgetLoaded(event);
    }

    /**
     * WidgetClosed event handler - delegates to UIStateHandler
     */
    @Subscribe
    public void onWidgetClosed(WidgetClosed event) {
        ((UIStateHandler) uiStateHandler).onWidgetClosed(event);
    }

    /**
     * WorldViewLoaded event handler - delegates to WorldHandler
     */
    @Subscribe
    public void onWorldViewLoaded(WorldViewLoaded event) {
        ((WorldHandler) worldHandler).onWorldViewLoaded(event);
    }

    public int getCurrentWorldViewIndex() {
        return currentWorldViewIndex;
    }

    /**
     * ItemSpawned event handler - delegates to WorldHandler
     */
    @Subscribe
    public void onItemSpawned(ItemSpawned event) {
        ((WorldHandler) worldHandler).onItemSpawned(event);
    }

    /**
     * ItemDespawned event handler - delegates to WorldHandler
     */
    @Subscribe
    public void onItemDespawned(ItemDespawned event) {
        ((WorldHandler) worldHandler).onItemDespawned(event);
    }

    /**
     * ItemQuantityChanged event handler - delegates to WorldHandler
     */
    @Subscribe
    public void onItemQuantityChanged(net.runelite.api.events.ItemQuantityChanged event) {
        ((WorldHandler) worldHandler).onItemQuantityChanged(event);
    }

    // ========================================================================
    // OBJECT STREAMER EVENTS - delegate to WorldHandler
    // ========================================================================

    @Subscribe
    public void onGameObjectSpawned(GameObjectSpawned event) {
        ((WorldHandler) worldHandler).onGameObjectSpawned(event.getGameObject());
    }

    @Subscribe
    public void onGameObjectDespawned(GameObjectDespawned event) {
        ((WorldHandler) worldHandler).onGameObjectDespawned(event.getGameObject());
    }

    @Subscribe
    public void onWallObjectSpawned(WallObjectSpawned event) {
        ((WorldHandler) worldHandler).onWallObjectSpawned(event.getWallObject());
    }

    @Subscribe
    public void onWallObjectDespawned(WallObjectDespawned event) {
        ((WorldHandler) worldHandler).onWallObjectDespawned(event.getWallObject());
    }

    @Subscribe
    public void onDecorativeObjectSpawned(DecorativeObjectSpawned event) {
        ((WorldHandler) worldHandler).onDecorativeObjectSpawned(event.getDecorativeObject());
    }

    @Subscribe
    public void onDecorativeObjectDespawned(DecorativeObjectDespawned event) {
        ((WorldHandler) worldHandler).onDecorativeObjectDespawned(event.getDecorativeObject());
    }

    @Subscribe
    public void onGroundObjectSpawned(GroundObjectSpawned event) {
        ((WorldHandler) worldHandler).onGroundObjectSpawned(event.getGroundObject());
    }

    @Subscribe
    public void onGroundObjectDespawned(GroundObjectDespawned event) {
        ((WorldHandler) worldHandler).onGroundObjectDespawned(event.getGroundObject());
    }

    // ========================================================================
    // CACHE ACCESSOR METHODS (for SubscribeHandler snapshots)
    // ========================================================================

    public Map<Integer, Integer> getVarcIntCache() {
        return ((VariableStateHandler) variableStateHandler).getVarcIntCache();
    }

    public Map<Integer, String> getVarcStrCache() {
        return ((VariableStateHandler) variableStateHandler).getVarcStrCache();
    }

    public Deque<net.runelite.api.events.ChatMessage> getChatHistory() {
        return ((ChatHandler) chatHandler).getChatHistory();
    }

    public Set<Integer> getActiveWidgetGroups() {
        return ((UIStateHandler) uiStateHandler).getActiveWidgetGroups();
    }

    public GroundItemStreamer getGroundItemStreamer() {
        return ((WorldHandler) worldHandler).getGroundItemStreamer();
    }

    public ObjectStreamer getObjectStreamer() {
        return ((WorldHandler) worldHandler).getObjectStreamer();
    }

    public PlayerStateHandler getPlayerStateHandler() {
        return (PlayerStateHandler) playerStateHandler;
    }

    public WorldHandler getWorldHandler() {
        return (WorldHandler) worldHandler;
    }

    public CameraHandler getCameraHandler() {
        return (CameraHandler) cameraHandler;
    }

    public MenuInputHandler getMenuInputHandler() {
        return (MenuInputHandler) menuInputHandler;
    }

    public ItemHandler getItemHandler() {
        return (ItemHandler) itemHandler;
    }

    public NpcStreamer getNpcStreamer() {
        return ((WorldHandler) worldHandler).getNpcStreamer();
    }
}
