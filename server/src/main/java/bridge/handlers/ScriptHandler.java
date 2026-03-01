package bridge.handlers;

import bridge.proto.v1.RunScriptRequest;
import bridge.proto.v1.RunScriptResponse;
import bridge.proto.v1.ScriptArg;
import net.runelite.api.Client;

/**
 * ScriptHandler - Executes CS2 client scripts via runScript.
 *
 * CS2 scripts only accept int and String arguments (the VM has exactly two stacks).
 * Game types like component, coord, obj are all encoded as int at the VM level.
 */
public class ScriptHandler implements EventHandler {
    private final Client client;

    public ScriptHandler(Client client) {
        this.client = client;
    }

    @Override
    public void initialize() {}

    @Override
    public void shutdown() {}

    @Override
    public String getName() {
        return "ScriptHandler";
    }

    /**
     * RPC: Execute a CS2 client script.
     *
     * args[0] is always the script ID, followed by int/string parameters.
     * Return values are read from the int/string stacks after execution.
     */
    public RunScriptResponse runScript(RunScriptRequest request) {
        Object[] args = new Object[request.getArgsCount() + 1];
        args[0] = request.getScriptId();
        for (int i = 0; i < request.getArgsCount(); i++) {
            ScriptArg arg = request.getArgs(i);
            if (arg.hasIntValue()) {
                args[i + 1] = arg.getIntValue();
            } else {
                args[i + 1] = arg.getStringValue();
            }
        }

        client.runScript(args);

        RunScriptResponse.Builder response = RunScriptResponse.newBuilder();

        int intCount = request.getIntResultCount();
        if (intCount > 0) {
            int[] intStack = client.getIntStack();
            for (int i = 0; i < intCount && i < intStack.length; i++) {
                response.addIntResults(intStack[i]);
            }
        }

        int strCount = request.getStringResultCount();
        if (strCount > 0) {
            String[] stringStack = client.getStringStack();
            for (int i = 0; i < strCount && i < stringStack.length; i++) {
                response.addStringResults(stringStack[i] != null ? stringStack[i] : "");
            }
        }

        return response.build();
    }
}
