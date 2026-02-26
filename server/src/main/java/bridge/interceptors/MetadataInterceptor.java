package bridge.interceptors;

import io.grpc.*;

/**
 * Captures RPC metadata and stores it in Context for access in handlers.
 */
public class MetadataInterceptor implements ServerInterceptor {

    public static final Context.Key<String> DIRECT_EXECUTION_KEY = Context.key("direct-execution");

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerCallHandler<ReqT, RespT> next) {

        // Extract direct-execution metadata and store in Context
        Metadata.Key<String> key = Metadata.Key.of("direct-execution", Metadata.ASCII_STRING_MARSHALLER);
        String directExecution = headers.get(key);

        Context context = Context.current();
        if (directExecution != null) {
            context = context.withValue(DIRECT_EXECUTION_KEY, directExecution);
        }

        // Execute with metadata-enriched context
        return Contexts.interceptCall(context, call, headers, next);
    }
}
