package bridge;

import java.lang.invoke.MethodHandles;
import java.net.URL;
import java.net.URLClassLoader;
import net.runelite.client.util.ReflectUtil;

public class BridgeClassLoader extends URLClassLoader implements ReflectUtil.PrivateLookupableClassLoader {
    private MethodHandles.Lookup lookup;

    public BridgeClassLoader(URL[] urls, ClassLoader parent) {
        super(urls, parent);
    }

    @Override
    public Class<?> defineClass0(String name, byte[] b, int off, int len) {
        return defineClass(name, b, off, len);
    }

    @Override
    public MethodHandles.Lookup getLookup() {
        return lookup;
    }

    @Override
    public void setLookup(MethodHandles.Lookup lookup) {
        this.lookup = lookup;
    }
}
