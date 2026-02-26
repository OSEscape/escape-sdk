package bridge.handlers;

import bridge.overlay.Drawing;
import bridge.proto.v1.*;
import com.google.protobuf.Empty;
import net.runelite.client.ui.overlay.OverlayManager;

/**
 * Handler for drawing overlay RPCs.
 * Manages lifecycle and forwards drawing commands to Drawing overlay.
 */
public class DrawingHandler implements EventHandler {
    private final OverlayManager overlayManager;
    private Drawing drawing;

    public DrawingHandler(OverlayManager overlayManager) {
        this.overlayManager = overlayManager;
    }

    @Override
    public void initialize() {
        drawing = new Drawing();
        overlayManager.add(drawing);
    }

    @Override
    public void shutdown() {
        if (drawing != null) {
            drawing.clear();
            overlayManager.remove(drawing);
            drawing = null;
        }
    }

    @Override
    public String getName() {
        return "DrawingHandler";
    }

    public Drawing getDrawing() {
        return drawing;
    }

    public Empty addBox(AddBoxRequest req) {
        String tag = req.getTag().isEmpty() ? null : req.getTag();
        drawing.addBox(
            req.getX(),
            req.getY(),
            req.getWidth(),
            req.getHeight(),
            req.getArgbColor(),
            req.getFilled(),
            tag
        );
        return Empty.getDefaultInstance();
    }

    public Empty addCircle(AddCircleRequest req) {
        String tag = req.getTag().isEmpty() ? null : req.getTag();
        drawing.addCircle(
            req.getX(),
            req.getY(),
            req.getRadius(),
            req.getArgbColor(),
            req.getFilled(),
            tag
        );
        return Empty.getDefaultInstance();
    }

    public Empty addLine(AddLineRequest req) {
        String tag = req.getTag().isEmpty() ? null : req.getTag();
        drawing.addLine(
            req.getX1(),
            req.getY1(),
            req.getX2(),
            req.getY2(),
            req.getArgbColor(),
            req.getThickness(),
            tag
        );
        return Empty.getDefaultInstance();
    }

    public Empty addPolygon(AddPolygonRequest req) {
        String tag = req.getTag().isEmpty() ? null : req.getTag();
        int[] xPoints = req.getXPointsList().stream().mapToInt(Integer::intValue).toArray();
        int[] yPoints = req.getYPointsList().stream().mapToInt(Integer::intValue).toArray();
        drawing.addPolygon(
            xPoints,
            yPoints,
            req.getArgbColor(),
            req.getFilled(),
            tag
        );
        return Empty.getDefaultInstance();
    }

    public Empty addText(AddTextRequest req) {
        String tag = req.getTag().isEmpty() ? null : req.getTag();
        drawing.addText(
            req.getText(),
            req.getX(),
            req.getY(),
            req.getArgbColor(),
            req.getFontSize(),
            tag
        );
        return Empty.getDefaultInstance();
    }

    public Empty addImage(AddImageRequest req) {
        String tag = req.getTag().isEmpty() ? null : req.getTag();
        int[] argbPixels = req.getArgbPixelsList().stream().mapToInt(Integer::intValue).toArray();
        drawing.addImage(
            argbPixels,
            req.getImgWidth(),
            req.getImgHeight(),
            req.getX(),
            req.getY(),
            tag
        );
        return Empty.getDefaultInstance();
    }

    public Empty batchDraw(BatchDrawRequest req) {
        if (!req.getClearTag().isEmpty()) {
            drawing.clearTag(req.getClearTag());
        }
        for (DrawCommand cmd : req.getCommandsList()) {
            switch (cmd.getCommandCase()) {
                case BOX: addBox(cmd.getBox()); break;
                case CIRCLE: addCircle(cmd.getCircle()); break;
                case LINE: addLine(cmd.getLine()); break;
                case POLYGON: addPolygon(cmd.getPolygon()); break;
                case TEXT: addText(cmd.getText()); break;
                case IMAGE: addImage(cmd.getImage()); break;
                default: break;
            }
        }
        return Empty.getDefaultInstance();
    }

    public Empty clearDrawing(Empty req) {
        drawing.clear();
        return Empty.getDefaultInstance();
    }

    public Empty clearDrawingTag(ClearDrawingTagRequest req) {
        drawing.clearTag(req.getTag());
        return Empty.getDefaultInstance();
    }
}
