package bridge.interceptors;

import io.grpc.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class ExceptionInterceptor implements ServerInterceptor {
    private static final Logger log = LoggerFactory.getLogger(ExceptionInterceptor.class);

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerCallHandler<ReqT, RespT> next) {

        ServerCall.Listener<ReqT> listener = next.startCall(call, headers);
        return new ExceptionHandlingListener<>(listener, call);
    }

    private class ExceptionHandlingListener<ReqT, RespT>
            extends ForwardingServerCallListener.SimpleForwardingServerCallListener<ReqT> {

        private final ServerCall<ReqT, RespT> call;

        ExceptionHandlingListener(ServerCall.Listener<ReqT> delegate, ServerCall<ReqT, RespT> call) {
            super(delegate);
            this.call = call;
        }

        @Override
        public void onHalfClose() {
            try {
                super.onHalfClose();
            } catch (Exception e) {
                handleException(e);
            }
        }

        @Override
        public void onMessage(ReqT message) {
            try {
                super.onMessage(message);
            } catch (Exception e) {
                handleException(e);
            }
        }

        private void handleException(Exception e) {
            String methodName = call.getMethodDescriptor().getFullMethodName();
            log.error("{} failed: {}", methodName, e.getMessage(), e);

            Status status;
            if (e instanceof IllegalArgumentException) {
                status = Status.INVALID_ARGUMENT;
            } else if (e instanceof IllegalStateException) {
                status = Status.FAILED_PRECONDITION;
            } else if (e instanceof ClassNotFoundException) {
                status = Status.NOT_FOUND;
            } else {
                status = Status.INTERNAL;
            }

            call.close(status.withDescription(e.getMessage()).withCause(e), new Metadata());
        }
    }
}
