package bridge.handlers;

import bridge.proto.v1.GetLoginIndexResponse;
import bridge.proto.v1.SetCredentialsRequest;
import com.google.protobuf.Empty;
import net.runelite.api.Client;

/**
 * LoginHandler - Sets credentials and reads login index from the client.
 */
public class LoginHandler implements EventHandler {
    private final Client client;

    public LoginHandler(Client client) {
        this.client = client;
    }

    @Override
    public void initialize() {}

    @Override
    public void shutdown() {}

    @Override
    public String getName() {
        return "LoginHandler";
    }

    /**
     * RPC: Set username and password on the client.
     */
    public Empty setCredentials(SetCredentialsRequest request) {
        client.setUsername(request.getUsername());
        client.setPassword(request.getPassword());
        return Empty.getDefaultInstance();
    }

    /**
     * RPC: Get the current login index.
     */
    public GetLoginIndexResponse getLoginIndex(Empty request) {
        return GetLoginIndexResponse.newBuilder()
                .setLoginIndex(client.getLoginIndex())
                .build();
    }
}
