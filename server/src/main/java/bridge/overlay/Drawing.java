package bridge.overlay;

import net.runelite.client.ui.overlay.Overlay;
import net.runelite.client.ui.overlay.OverlayLayer;
import net.runelite.client.ui.overlay.OverlayPosition;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Drawing overlay - renders shapes and images at screen coordinates.
 *
 * Usage:
 *   - overlayManager.add(drawing) - register once
 *   - addBox(), addCircle(), addLine(), addText(), addImage() - add draw commands
 *   - clear() or clearTag(tag) - remove drawings
 *
 * All colors are ARGB format: 0xAARRGGBB (e.g., 0xFFFF0000 = opaque red)
 * All commands persist until clear() is called.
 * Thread-safe for external calls.
 */
public class Drawing extends Overlay {
    private final List<DrawCommand> commands = new CopyOnWriteArrayList<>();

    public Drawing() {
        setPosition(OverlayPosition.DYNAMIC);
        setLayer(OverlayLayer.ABOVE_WIDGETS);
    }

    public void addBox(int x, int y, int width, int height, int argbColor, boolean filled, String tag) {
        commands.add(new DrawCommand(tag, g -> {
            g.setColor(new Color(argbColor, true));
            if (filled) {
                g.fillRect(x, y, width, height);
            } else {
                g.drawRect(x, y, width, height);
            }
        }));
    }

    public void addBox(int x, int y, int width, int height, int argbColor, boolean filled) {
        addBox(x, y, width, height, argbColor, filled, null);
    }

    public void addCircle(int x, int y, int radius, int argbColor, boolean filled, String tag) {
        commands.add(new DrawCommand(tag, g -> {
            g.setColor(new Color(argbColor, true));
            if (filled) {
                g.fillOval(x - radius, y - radius, radius * 2, radius * 2);
            } else {
                g.drawOval(x - radius, y - radius, radius * 2, radius * 2);
            }
        }));
    }

    public void addCircle(int x, int y, int radius, int argbColor, boolean filled) {
        addCircle(x, y, radius, argbColor, filled, null);
    }

    public void addLine(int x1, int y1, int x2, int y2, int argbColor, int thickness, String tag) {
        commands.add(new DrawCommand(tag, g -> {
            g.setColor(new Color(argbColor, true));
            g.setStroke(new BasicStroke(thickness));
            g.drawLine(x1, y1, x2, y2);
        }));
    }

    public void addLine(int x1, int y1, int x2, int y2, int argbColor, int thickness) {
        addLine(x1, y1, x2, y2, argbColor, thickness, null);
    }

    public void addPolygon(int[] xPoints, int[] yPoints, int argbColor, boolean filled, String tag) {
        if (xPoints.length != yPoints.length || xPoints.length < 3) return;
        commands.add(new DrawCommand(tag, g -> {
            g.setColor(new Color(argbColor, true));
            if (filled) {
                g.fillPolygon(xPoints, yPoints, xPoints.length);
            } else {
                g.drawPolygon(xPoints, yPoints, xPoints.length);
            }
        }));
    }

    public void addPolygon(int[] xPoints, int[] yPoints, int argbColor, boolean filled) {
        addPolygon(xPoints, yPoints, argbColor, filled, null);
    }

    public void addText(String text, int x, int y, int argbColor, int fontSize, String tag) {
        commands.add(new DrawCommand(tag, g -> {
            g.setColor(new Color(argbColor, true));
            if (fontSize > 0) {
                g.setFont(g.getFont().deriveFont((float) fontSize));
            }
            g.drawString(text, x, y);
        }));
    }

    public void addText(String text, int x, int y, int argbColor) {
        addText(text, x, y, argbColor, 0, null);
    }

    public void addImage(int[] argbPixels, int imgWidth, int imgHeight, int x, int y, String tag) {
        if (argbPixels == null || argbPixels.length != imgWidth * imgHeight) return;
        BufferedImage img = new BufferedImage(imgWidth, imgHeight, BufferedImage.TYPE_INT_ARGB);
        img.setRGB(0, 0, imgWidth, imgHeight, argbPixels, 0, imgWidth);
        commands.add(new DrawCommand(tag, g -> g.drawImage(img, x, y, null)));
    }

    public void addImage(int[] argbPixels, int imgWidth, int imgHeight, int x, int y) {
        addImage(argbPixels, imgWidth, imgHeight, x, y, null);
    }

    public void addImage(BufferedImage img, int x, int y, String tag) {
        if (img == null) return;
        commands.add(new DrawCommand(tag, g -> g.drawImage(img, x, y, null)));
    }

    public void clear() {
        commands.clear();
    }

    public void clearTag(String tag) {
        if (tag == null) return;
        commands.removeIf(cmd -> tag.equals(cmd.tag));
    }

    @Override
    public Dimension render(Graphics2D g) {
        for (DrawCommand cmd : commands) {
            cmd.renderer.accept(g);
        }
        return null;
    }

    public int getCount() {
        return commands.size();
    }

    private static class DrawCommand {
        final String tag;
        final java.util.function.Consumer<Graphics2D> renderer;

        DrawCommand(String tag, java.util.function.Consumer<Graphics2D> renderer) {
            this.tag = tag;
            this.renderer = renderer;
        }
    }
}
