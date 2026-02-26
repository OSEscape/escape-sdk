package bridge.interceptors;

import io.grpc.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;

import java.util.UUID;

public class LoggingInterceptor implements ServerInterceptor {
    private static final Logger log = LoggerFactory.getLogger(LoggingInterceptor.class);

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerCallHandler<ReqT, RespT> next) {

        String requestId = UUID.randomUUID().toString().substring(0, 8);
        String methodName = call.getMethodDescriptor().getBareMethodName();
        long startTime = System.nanoTime();

        MDC.put("request_id", requestId);
        MDC.put("method", methodName);

        return new ForwardingServerCallListener.SimpleForwardingServerCallListener<ReqT>(
                next.startCall(new ForwardingServerCall.SimpleForwardingServerCall<ReqT, RespT>(call) {
                    @Override
                    public void close(Status status, Metadata trailers) {
                        long duration = (System.nanoTime() - startTime) / 1_000_000;
                        log.info("method={} status={} duration={}ms", methodName, status.getCode(), duration);
                        MDC.clear();
                        super.close(status, trailers);
                    }
                }, headers)) {};
    }
}
