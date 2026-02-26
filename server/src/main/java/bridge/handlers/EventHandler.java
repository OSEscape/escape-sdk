package bridge.handlers;

/**
 * EventHandler interface for domain-based event processing.
 *
 * Each handler is responsible for a specific domain of game events
 * and delegates to SubscribeHandler for event broadcasting.
 *
 * Handlers are initialized in BridgePlugin.startUp() and shut down
 * in BridgePlugin.shutDown(). They receive forwarded events from
 * BridgePlugin's @Subscribe methods (only Plugin classes can subscribe
 * to RuneLite's EventBus).
 */
public interface EventHandler {
    /**
     * Initialize handler state and resources.
     * Called from BridgePlugin.startUp() after dependencies are ready.
     */
    void initialize();

    /**
     * Shutdown handler and clean up resources.
     * Called from BridgePlugin.shutDown() before plugin unload.
     */
    void shutdown();

    /**
     * Get the handler name for logging and debugging.
     * @return Handler name (e.g., "MenuInputHandler", "ChatHandler")
     */
    String getName();
}
