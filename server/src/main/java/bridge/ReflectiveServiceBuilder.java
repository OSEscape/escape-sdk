package bridge;

import bridge.handlers.SubscribeHandler;
import bridge.interceptors.MetadataInterceptor;
import bridge.proto.v1.BridgeServiceGrpc;
import bridge.proto.v1.ClientMessage;
import bridge.proto.v1.ServerMessage;
import bridge.proto.v1.SubscriptionOptions;
import io.grpc.MethodDescriptor;
import io.grpc.ServerCallHandler;
import io.grpc.ServerServiceDefinition;
import io.grpc.stub.ServerCalls;
import io.grpc.stub.StreamObserver;
import net.runelite.client.callback.ClientThread;

import java.lang.reflect.Method;
import java.util.HashMap;
import java.util.Map;

/**
 * Builds a gRPC service definition by reflection, auto-discovering handler methods.
 * Provides seamless synchronization between multithreaded gRPC workers and the
 * single-threaded RuneLite engine loop.
 */
public class ReflectiveServiceBuilder {

    private final ClientThread clientThread;
    private final Map<String, HandlerMethod> handlerMethods = new HashMap<>();
    private SubscribeHandler subscribeHandler;

    public ReflectiveServiceBuilder(ClientThread clientThread) {
        this.clientThread = clientThread;
    }

    public ReflectiveServiceBuilder setSubscribeHandler(SubscribeHandler subscribeHandler) {
        this.subscribeHandler = subscribeHandler;
        return this;
    }

    /**
     * Registers a domain handler class. Methods matching the RPC name (e.g. getPlayer)
     * are auto-mapped to the corresponding gRPC service method.
     */
    public ReflectiveServiceBuilder addHandler(Object handler) {
        for (Method method : handler.getClass().getMethods()) {
            Class<?>[] params = method.getParameterTypes();
            Class<?> returnType = method.getReturnType();

            // Convention: ResponseType methodName(RequestType request)
            boolean validParam = params.length == 1 &&
                (params[0].getSimpleName().endsWith("Request") ||
                 params[0].getSimpleName().equals("Empty"));

            boolean validReturn = com.google.protobuf.Message.class.isAssignableFrom(returnType);

            if (validParam && validReturn) {
                String methodName = method.getName();
                handlerMethods.put(methodName, new HandlerMethod(handler, method));
            }
        }
        return this;
    }

    /**
     * Compiles the final gRPC ServerServiceDefinition using the registered handlers.
     */
    @SuppressWarnings("unchecked")
    public ServerServiceDefinition build() {
        ServerServiceDefinition.Builder builder = ServerServiceDefinition.builder(
            BridgeServiceGrpc.getServiceDescriptor()
        );

        for (Method grpcMethod : BridgeServiceGrpc.class.getMethods()) {
            if (!grpcMethod.getName().startsWith("get") || !grpcMethod.getName().endsWith("Method")) {
                continue;
            }
            if (grpcMethod.getReturnType() != MethodDescriptor.class) {
                continue;
            }

            try {
                MethodDescriptor<Object, Object> descriptor =
                    (MethodDescriptor<Object, Object>) grpcMethod.invoke(null);

                String fullMethodName = descriptor.getFullMethodName();
                String rpcName = fullMethodName.substring(fullMethodName.lastIndexOf('/') + 1);
                String handlerMethodName = Character.toLowerCase(rpcName.charAt(0)) + rpcName.substring(1);

                MethodDescriptor.MethodType type = descriptor.getType();

                if (type == MethodDescriptor.MethodType.BIDI_STREAMING) {
                    if (subscribeHandler != null) {
                        builder.addMethod(BridgeServiceGrpc.getSubscribeMethod(), createSubscribeHandler());
                    }
                    continue;
                }

                HandlerMethod handler = handlerMethods.get(handlerMethodName);
                if (handler == null) {
                    System.err.println("[Bridge] No handler found for RPC: " + rpcName);
                    continue;
                }

                if (type == MethodDescriptor.MethodType.UNARY) {
                    builder.addMethod(descriptor, createUnaryHandler(handler));
                }

            } catch (Exception e) {
                e.printStackTrace();
            }
        }

        return builder.build();
    }

    private ServerCallHandler<ClientMessage, ServerMessage> createSubscribeHandler() {
        return ServerCalls.asyncBidiStreamingCall(responseObserver -> {
            return new StreamObserver<ClientMessage>() {
                @Override
                public void onNext(ClientMessage message) {
                    if (message.hasSubscribe()) {
                        SubscriptionOptions options = message.getSubscribe().getOptions();
                        if (options == null) {
                            options = SubscriptionOptions.getDefaultInstance();
                        }
                        subscribeHandler.subscribe(responseObserver, options);
                    }
                }

                @Override
                public void onError(Throwable t) {
                    subscribeHandler.unsubscribe(responseObserver);
                }

                @Override
                public void onCompleted() {
                    subscribeHandler.unsubscribe(responseObserver);
                    responseObserver.onCompleted();
                }
            };
        });
    }

    private <ReqT, RespT> ServerCallHandler<ReqT, RespT> createUnaryHandler(HandlerMethod handler) {
        return ServerCalls.asyncUnaryCall((request, observer) -> {
            invokeOnClientThread(handler, request, observer);
        });
    }

    /**
     * Executes the handler method on the RuneLite ClientThread asynchronously.
     * Prevents blocking gRPC worker threads, ensuring the bridge remains responsive
     * even during game engine lag spikes.
     */
    @SuppressWarnings("unchecked")
    private <ReqT, RespT> void invokeOnClientThread(
            HandlerMethod handler, ReqT request, StreamObserver<RespT> observer) {

        String directExecutionValue = MetadataInterceptor.DIRECT_EXECUTION_KEY.get();
        boolean directExecution = "true".equals(directExecutionValue);

        if (directExecution) {
            try {
                RespT result = (RespT) handler.method.invoke(handler.instance, request);
                observer.onNext(result);
                observer.onCompleted();
            } catch (Exception e) {
                observer.onError(new RuntimeException(e));
            }
        } else {
            // Offload to game thread and return immediately to free the gRPC worker
            clientThread.invokeLater(() -> {
                try {
                    RespT result = (RespT) handler.method.invoke(handler.instance, request);
                    observer.onNext(result);
                    observer.onCompleted();
                } catch (Exception e) {
                    observer.onError(new RuntimeException(e));
                }
            });
        }
    }

    private static class HandlerMethod {
        final Object instance;
        final Method method;

        HandlerMethod(Object instance, Method method) {
            this.instance = instance;
            this.method = method;
        }
    }
}
