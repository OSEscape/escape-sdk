package bridge.handlers;

import bridge.proto.v1.*;
import net.runelite.client.util.Text;
import java.util.Deque;
import java.util.concurrent.ConcurrentLinkedDeque;

/**
 * ChatHandler - Manages chat message history and streaming.
 *
 * Responsibilities:
 * - Maintain bounded buffer of recent chat messages (100 messages max)
 * - Stream chat messages as they arrive
 * - Provide chat history for snapshots
 *
 * Thread Safety:
 * - Uses ConcurrentLinkedDeque for thread-safe access
 * - Chat events come from client thread via BridgePlugin
 */
public class ChatHandler implements EventHandler {
    private static final int MAX_CHAT_HISTORY = 100;

    private final SubscribeHandler subscribeHandler;
    private final Deque<net.runelite.api.events.ChatMessage> chatHistory;

    public ChatHandler(SubscribeHandler subscribeHandler) {
        this.subscribeHandler = subscribeHandler;
        this.chatHistory = new ConcurrentLinkedDeque<>();
    }

    @Override
    public void initialize() {
        chatHistory.clear();
    }

    @Override
    public void shutdown() {
        chatHistory.clear();
    }

    @Override
    public String getName() {
        return "ChatHandler";
    }

    /**
     * Handle chat message event (called from BridgePlugin.onChatMessage)
     * @param event ChatMessage event from RuneLite
     */
    public void onChatMessage(net.runelite.api.events.ChatMessage event) {
        // Add to chat history (bounded buffer)
        chatHistory.addLast(event);
        if (chatHistory.size() > MAX_CHAT_HISTORY) {
            chatHistory.removeFirst();
        }

        // Stream to subscribers
        bridge.proto.v1.ChatChanged msg = bridge.proto.v1.ChatChanged.newBuilder()
            .setMessage(bridge.proto.v1.ChatMessage.newBuilder()
                .setType(event.getType().name())
                .setSender(Text.removeTags(event.getName()))
                .setMessage(Text.removeTags(event.getMessage()))
                .build())
            .build();
        subscribeHandler.send(msg);
    }

    /**
     * Get chat history for snapshots
     * @return Deque of recent chat messages
     */
    public Deque<net.runelite.api.events.ChatMessage> getChatHistory() {
        return chatHistory;
    }
}
