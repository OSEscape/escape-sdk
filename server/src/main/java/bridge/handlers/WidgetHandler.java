package bridge.handlers;

import bridge.proto.v1.*;
import net.runelite.api.Client;
import net.runelite.api.Point;
import net.runelite.api.widgets.*;

import java.awt.Rectangle;

/**
 * Handler for querying and interacting with RuneLite widgets.
 * Supports bitmask-based property extraction and atomic server-side interaction data calculation.
 */
public class WidgetHandler {
    private static long bit(WidgetProperty prop) {
        return 1L << (prop.getNumber() - 1);
    }

    // Property bitmask constants derived from the stable Protobuf IDL
    public static final long PROP_ACTIONS                 = bit(WidgetProperty.WIDGET_PROP_ACTIONS);
    public static final long PROP_ANIMATION_ID            = bit(WidgetProperty.WIDGET_PROP_ANIMATION_ID);
    public static final long PROP_BORDER_TYPE             = bit(WidgetProperty.WIDGET_PROP_BORDER_TYPE);
    public static final long PROP_BOUNDS                  = bit(WidgetProperty.WIDGET_PROP_BOUNDS);
    public static final long PROP_CANVAS_LOCATION         = bit(WidgetProperty.WIDGET_PROP_CANVAS_LOCATION);
    public static final long PROP_CLICK_MASK              = bit(WidgetProperty.WIDGET_PROP_CLICK_MASK);
    public static final long PROP_CONTENT_TYPE            = bit(WidgetProperty.WIDGET_PROP_CONTENT_TYPE);
    public static final long PROP_DRAG_DEAD_TIME          = bit(WidgetProperty.WIDGET_PROP_DRAG_DEAD_TIME);
    public static final long PROP_DRAG_DEAD_ZONE          = bit(WidgetProperty.WIDGET_PROP_DRAG_DEAD_ZONE);
    public static final long PROP_DRAG_PARENT             = bit(WidgetProperty.WIDGET_PROP_DRAG_PARENT);
    public static final long PROP_FONT                    = bit(WidgetProperty.WIDGET_PROP_FONT);
    public static final long PROP_FONT_ID                 = bit(WidgetProperty.WIDGET_PROP_FONT_ID);
    public static final long PROP_HEIGHT                  = bit(WidgetProperty.WIDGET_PROP_HEIGHT);
    public static final long PROP_HEIGHT_MODE             = bit(WidgetProperty.WIDGET_PROP_HEIGHT_MODE);
    public static final long PROP_ID                      = bit(WidgetProperty.WIDGET_PROP_ID);
    public static final long PROP_INDEX                   = bit(WidgetProperty.WIDGET_PROP_INDEX);
    public static final long PROP_ITEM_ID                 = bit(WidgetProperty.WIDGET_PROP_ITEM_ID);
    public static final long PROP_ITEM_QUANTITY           = bit(WidgetProperty.WIDGET_PROP_ITEM_QUANTITY);
    public static final long PROP_ITEM_QUANTITY_MODE      = bit(WidgetProperty.WIDGET_PROP_ITEM_QUANTITY_MODE);
    public static final long PROP_LINE_HEIGHT             = bit(WidgetProperty.WIDGET_PROP_LINE_HEIGHT);
    public static final long PROP_MODEL_ID                = bit(WidgetProperty.WIDGET_PROP_MODEL_ID);
    public static final long PROP_MODEL_TYPE              = bit(WidgetProperty.WIDGET_PROP_MODEL_TYPE);
    public static final long PROP_MODEL_ZOOM              = bit(WidgetProperty.WIDGET_PROP_MODEL_ZOOM);
    public static final long PROP_NAME                    = bit(WidgetProperty.WIDGET_PROP_NAME);
    public static final long PROP_NO_CLICK_THROUGH        = bit(WidgetProperty.WIDGET_PROP_NO_CLICK_THROUGH);
    public static final long PROP_NO_SCROLL_THROUGH       = bit(WidgetProperty.WIDGET_PROP_NO_SCROLL_THROUGH);
    public static final long PROP_ON_INV_TRANSMIT         = bit(WidgetProperty.WIDGET_PROP_ON_INV_TRANSMIT);
    public static final long PROP_ON_KEY                  = bit(WidgetProperty.WIDGET_PROP_ON_KEY);
    public static final long PROP_ON_LOAD                 = bit(WidgetProperty.WIDGET_PROP_ON_LOAD);
    public static final long PROP_ON_OP                   = bit(WidgetProperty.WIDGET_PROP_ON_OP);
    public static final long PROP_ON_VAR_TRANSMIT         = bit(WidgetProperty.WIDGET_PROP_ON_VAR_TRANSMIT);
    public static final long PROP_OPACITY                 = bit(WidgetProperty.WIDGET_PROP_OPACITY);
    public static final long PROP_ORIGINAL_HEIGHT         = bit(WidgetProperty.WIDGET_PROP_ORIGINAL_HEIGHT);
    public static final long PROP_ORIGINAL_WIDTH          = bit(WidgetProperty.WIDGET_PROP_ORIGINAL_WIDTH);
    public static final long PROP_ORIGINAL_X              = bit(WidgetProperty.WIDGET_PROP_ORIGINAL_X);
    public static final long PROP_ORIGINAL_Y              = bit(WidgetProperty.WIDGET_PROP_ORIGINAL_Y);
    public static final long PROP_PARENT                  = bit(WidgetProperty.WIDGET_PROP_PARENT);
    public static final long PROP_PARENT_ID               = bit(WidgetProperty.WIDGET_PROP_PARENT_ID);
    public static final long PROP_RELATIVE_X              = bit(WidgetProperty.WIDGET_PROP_RELATIVE_X);
    public static final long PROP_RELATIVE_Y              = bit(WidgetProperty.WIDGET_PROP_RELATIVE_Y);
    public static final long PROP_ROTATION_X              = bit(WidgetProperty.WIDGET_PROP_ROTATION_X);
    public static final long PROP_ROTATION_Y              = bit(WidgetProperty.WIDGET_PROP_ROTATION_Y);
    public static final long PROP_ROTATION_Z              = bit(WidgetProperty.WIDGET_PROP_ROTATION_Z);
    public static final long PROP_SCROLL_HEIGHT           = bit(WidgetProperty.WIDGET_PROP_SCROLL_HEIGHT);
    public static final long PROP_SCROLL_WIDTH            = bit(WidgetProperty.WIDGET_PROP_SCROLL_WIDTH);
    public static final long PROP_SCROLL_X                = bit(WidgetProperty.WIDGET_PROP_SCROLL_X);
    public static final long PROP_SCROLL_Y                = bit(WidgetProperty.WIDGET_PROP_SCROLL_Y);
    public static final long PROP_SPRITE_ID               = bit(WidgetProperty.WIDGET_PROP_SPRITE_ID);
    public static final long PROP_SPRITE_TILING           = bit(WidgetProperty.WIDGET_PROP_SPRITE_TILING);
    public static final long PROP_STATIC_CHILDREN         = bit(WidgetProperty.WIDGET_PROP_STATIC_CHILDREN);
    public static final long PROP_TARGET_PRIORITY         = bit(WidgetProperty.WIDGET_PROP_TARGET_PRIORITY);
    public static final long PROP_TARGET_VERB             = bit(WidgetProperty.WIDGET_PROP_TARGET_VERB);
    public static final long PROP_TEXT                    = bit(WidgetProperty.WIDGET_PROP_TEXT);
    public static final long PROP_TEXT_COLOR              = bit(WidgetProperty.WIDGET_PROP_TEXT_COLOR);
    public static final long PROP_TEXT_SHADOWED           = bit(WidgetProperty.WIDGET_PROP_TEXT_SHADOWED);
    public static final long PROP_TYPE                    = bit(WidgetProperty.WIDGET_PROP_TYPE);
    public static final long PROP_VAR_TRANSMIT_TRIGGER    = bit(WidgetProperty.WIDGET_PROP_VAR_TRANSMIT_TRIGGER);
    public static final long PROP_WIDTH                   = bit(WidgetProperty.WIDGET_PROP_WIDTH);
    public static final long PROP_WIDTH_MODE              = bit(WidgetProperty.WIDGET_PROP_WIDTH_MODE);
    public static final long PROP_X_POSITION_MODE         = bit(WidgetProperty.WIDGET_PROP_X_POSITION_MODE);
    public static final long PROP_X_TEXT_ALIGNMENT        = bit(WidgetProperty.WIDGET_PROP_X_TEXT_ALIGNMENT);
    public static final long PROP_Y_POSITION_MODE         = bit(WidgetProperty.WIDGET_PROP_Y_POSITION_MODE);
    public static final long PROP_Y_TEXT_ALIGNMENT        = bit(WidgetProperty.WIDGET_PROP_Y_TEXT_ALIGNMENT);
    public static final long PROP_IS_HIDDEN               = bit(WidgetProperty.WIDGET_PROP_IS_HIDDEN);

    private final Client client;

    public WidgetHandler(Client client) {
        this.client = client;
    }

    private DataValue toDataValue(int value) {
        return DataValue.newBuilder().setI32(value).build();
    }

    private DataValue toDataValue(long value) {
        return DataValue.newBuilder().setI64(value).build();
    }

    private DataValue toDataValue(String value) {
        return DataValue.newBuilder().setStr(value == null ? "" : value).build();
    }

    private DataValue toDataValue(boolean value) {
        return DataValue.newBuilder().setB(value).build();
    }

    private DataValue toDataValue(Rectangle rect) {
        if (rect == null) {
            return DataValue.newBuilder()
                .setRectangle(bridge.proto.v1.Rectangle.newBuilder()
                    .setX(0).setY(0).setWidth(0).setHeight(0).build())
                .build();
        }
        return DataValue.newBuilder()
            .setRectangle(bridge.proto.v1.Rectangle.newBuilder()
                .setX(rect.x).setY(rect.y).setWidth(rect.width).setHeight(rect.height).build())
            .build();
    }

    private DataValue toDataValue(Point point) {
        if (point == null) {
            return DataValue.newBuilder()
                .setPoint(bridge.proto.v1.Point.newBuilder().setX(0).setY(0).build())
                .build();
        }
        return DataValue.newBuilder()
            .setPoint(bridge.proto.v1.Point.newBuilder()
                .setX(point.getX()).setY(point.getY()).build())
            .build();
    }

    private WidgetValue toWidgetValue(int value) {
        return WidgetValue.newBuilder().setSingleValue(toDataValue(value)).build();
    }

    private WidgetValue toWidgetValue(long value) {
        return WidgetValue.newBuilder().setSingleValue(toDataValue(value)).build();
    }

    private WidgetValue toWidgetValue(String value) {
        return WidgetValue.newBuilder().setSingleValue(toDataValue(value)).build();
    }

    private WidgetValue toWidgetValue(boolean value) {
        return WidgetValue.newBuilder().setSingleValue(toDataValue(value)).build();
    }

    private WidgetValue toWidgetValue(Rectangle rect) {
        return WidgetValue.newBuilder().setSingleValue(toDataValue(rect)).build();
    }

    private WidgetValue toWidgetValue(Point point) {
        return WidgetValue.newBuilder().setSingleValue(toDataValue(point)).build();
    }

    private WidgetValue toWidgetValue(String[] values) {
        DataValueList.Builder listBuilder = DataValueList.newBuilder();
        if (values != null) {
            for (String val : values) {
                listBuilder.addValues(toDataValue(val));
            }
        }
        return WidgetValue.newBuilder().setMultipleValues(listBuilder.build()).build();
    }

    private WidgetValue toWidgetValue(int[] values) {
        DataValueList.Builder listBuilder = DataValueList.newBuilder();
        if (values != null) {
            for (int val : values) {
                listBuilder.addValues(toDataValue(val));
            }
        }
        return WidgetValue.newBuilder().setMultipleValues(listBuilder.build()).build();
    }

    private WidgetValue toWidgetValue(Object[] values) {
        DataValueList.Builder listBuilder = DataValueList.newBuilder();
        if (values != null) {
            for (Object val : values) {
                if (val instanceof Integer) {
                    listBuilder.addValues(toDataValue((Integer) val));
                } else if (val instanceof String) {
                    listBuilder.addValues(toDataValue((String) val));
                }
            }
        }
        return WidgetValue.newBuilder().setMultipleValues(listBuilder.build()).build();
    }

    private WidgetResponse.Builder extractWidgetProperties(Widget w, long propertyMask) {
        WidgetResponse.Builder builder = WidgetResponse.newBuilder();

        if (w == null) {
            throw new IllegalArgumentException("Widget is null");
        }

        if ((propertyMask & PROP_ACTIONS) != 0) builder.putValues("actions", toWidgetValue(w.getActions()));
        if ((propertyMask & PROP_ANIMATION_ID) != 0) builder.putValues("animationId", toWidgetValue(w.getAnimationId()));
        if ((propertyMask & PROP_BORDER_TYPE) != 0) builder.putValues("borderType", toWidgetValue(w.getBorderType()));
        if ((propertyMask & PROP_BOUNDS) != 0) builder.putValues("bounds", toWidgetValue(w.getBounds()));
        if ((propertyMask & PROP_CANVAS_LOCATION) != 0) builder.putValues("canvasLocation", toWidgetValue(w.getCanvasLocation()));
        if ((propertyMask & PROP_CLICK_MASK) != 0) builder.putValues("clickMask", toWidgetValue(w.getClickMask()));
        if ((propertyMask & PROP_CONTENT_TYPE) != 0) builder.putValues("contentType", toWidgetValue(w.getContentType()));
        if ((propertyMask & PROP_DRAG_DEAD_TIME) != 0) builder.putValues("dragDeadTime", toWidgetValue(w.getDragDeadTime()));
        if ((propertyMask & PROP_DRAG_DEAD_ZONE) != 0) builder.putValues("dragDeadZone", toWidgetValue(w.getDragDeadZone()));
        if ((propertyMask & PROP_DRAG_PARENT) != 0) {
            Widget parent = w.getDragParent();
            builder.putValues("dragParent", toWidgetValue(parent != null ? parent.getId() : -1));
        }
        if ((propertyMask & PROP_FONT) != 0) builder.putValues("font", toWidgetValue(w.getFont() != null ? w.getFont().toString() : ""));
        if ((propertyMask & PROP_FONT_ID) != 0) builder.putValues("fontId", toWidgetValue(w.getFontId()));
        if ((propertyMask & PROP_HEIGHT) != 0) builder.putValues("height", toWidgetValue(w.getHeight()));
        if ((propertyMask & PROP_HEIGHT_MODE) != 0) builder.putValues("heightMode", toWidgetValue(w.getHeightMode()));
        if ((propertyMask & PROP_ID) != 0) builder.putValues("id", toWidgetValue(w.getId()));
        if ((propertyMask & PROP_INDEX) != 0) builder.putValues("index", toWidgetValue(w.getIndex()));
        if ((propertyMask & PROP_ITEM_ID) != 0) builder.putValues("itemId", toWidgetValue(w.getItemId()));
        if ((propertyMask & PROP_ITEM_QUANTITY) != 0) builder.putValues("itemQuantity", toWidgetValue(w.getItemQuantity()));
        if ((propertyMask & PROP_ITEM_QUANTITY_MODE) != 0) builder.putValues("itemQuantityMode", toWidgetValue(w.getItemQuantityMode()));
        if ((propertyMask & PROP_LINE_HEIGHT) != 0) builder.putValues("lineHeight", toWidgetValue(w.getLineHeight()));
        if ((propertyMask & PROP_MODEL_ID) != 0) builder.putValues("modelId", toWidgetValue(w.getModelId()));
        if ((propertyMask & PROP_MODEL_TYPE) != 0) builder.putValues("modelType", toWidgetValue(w.getModelType()));
        if ((propertyMask & PROP_MODEL_ZOOM) != 0) builder.putValues("modelZoom", toWidgetValue(w.getModelZoom()));
        if ((propertyMask & PROP_NAME) != 0) builder.putValues("name", toWidgetValue(w.getName()));
        if ((propertyMask & PROP_NO_CLICK_THROUGH) != 0) builder.putValues("noClickThrough", toWidgetValue(w.getNoClickThrough()));
        if ((propertyMask & PROP_NO_SCROLL_THROUGH) != 0) builder.putValues("noScrollThrough", toWidgetValue(w.getNoScrollThrough()));
        if ((propertyMask & PROP_ON_INV_TRANSMIT) != 0) builder.putValues("onInvTransmitListener", toWidgetValue(w.getOnInvTransmitListener()));
        if ((propertyMask & PROP_ON_KEY) != 0) builder.putValues("onKeyListener", toWidgetValue(w.getOnKeyListener()));
        if ((propertyMask & PROP_ON_LOAD) != 0) builder.putValues("onLoadListener", toWidgetValue(w.getOnLoadListener()));
        if ((propertyMask & PROP_ON_OP) != 0) builder.putValues("onOpListener", toWidgetValue(w.getOnOpListener()));
        if ((propertyMask & PROP_ON_VAR_TRANSMIT) != 0) builder.putValues("onVarTransmitListener", toWidgetValue(w.getOnVarTransmitListener()));
        if ((propertyMask & PROP_OPACITY) != 0) builder.putValues("opacity", toWidgetValue(w.getOpacity()));
        if ((propertyMask & PROP_ORIGINAL_HEIGHT) != 0) builder.putValues("originalHeight", toWidgetValue(w.getOriginalHeight()));
        if ((propertyMask & PROP_ORIGINAL_WIDTH) != 0) builder.putValues("originalWidth", toWidgetValue(w.getOriginalWidth()));
        if ((propertyMask & PROP_ORIGINAL_X) != 0) builder.putValues("originalX", toWidgetValue(w.getOriginalX()));
        if ((propertyMask & PROP_ORIGINAL_Y) != 0) builder.putValues("originalY", toWidgetValue(w.getOriginalY()));
        if ((propertyMask & PROP_PARENT) != 0) {
            Widget parent = w.getParent();
            builder.putValues("parent", toWidgetValue(parent != null ? parent.getId() : -1));
        }
        if ((propertyMask & PROP_PARENT_ID) != 0) builder.putValues("parentId", toWidgetValue(w.getParentId()));
        if ((propertyMask & PROP_RELATIVE_X) != 0) builder.putValues("relativeX", toWidgetValue(w.getRelativeX()));
        if ((propertyMask & PROP_RELATIVE_Y) != 0) builder.putValues("relativeY", toWidgetValue(w.getRelativeY()));
        if ((propertyMask & PROP_ROTATION_X) != 0) builder.putValues("rotationX", toWidgetValue(w.getRotationX()));
        if ((propertyMask & PROP_ROTATION_Y) != 0) builder.putValues("rotationY", toWidgetValue(w.getRotationY()));
        if ((propertyMask & PROP_ROTATION_Z) != 0) builder.putValues("rotationZ", toWidgetValue(w.getRotationZ()));
        if ((propertyMask & PROP_SCROLL_HEIGHT) != 0) builder.putValues("scrollHeight", toWidgetValue(w.getScrollHeight()));
        if ((propertyMask & PROP_SCROLL_WIDTH) != 0) builder.putValues("scrollWidth", toWidgetValue(w.getScrollWidth()));
        if ((propertyMask & PROP_SCROLL_X) != 0) builder.putValues("scrollX", toWidgetValue(w.getScrollX()));
        if ((propertyMask & PROP_SCROLL_Y) != 0) builder.putValues("scrollY", toWidgetValue(w.getScrollY()));
        if ((propertyMask & PROP_SPRITE_ID) != 0) builder.putValues("spriteId", toWidgetValue(w.getSpriteId()));
        if ((propertyMask & PROP_SPRITE_TILING) != 0) builder.putValues("spriteTiling", toWidgetValue(w.getSpriteTiling()));
        if ((propertyMask & PROP_STATIC_CHILDREN) != 0) {
            Widget[] children = w.getStaticChildren();
            if (children != null) {
                int[] childIds = new int[children.length];
                for (int i = 0; i < children.length; i++) {
                    childIds[i] = children[i] != null ? children[i].getId() : -1;
                }
                builder.putValues("staticChildren", toWidgetValue(childIds));
            }
        }
        if ((propertyMask & PROP_TARGET_VERB) != 0) builder.putValues("targetVerb", toWidgetValue(w.getTargetVerb()));
        if ((propertyMask & PROP_TEXT) != 0) builder.putValues("text", toWidgetValue(w.getText()));
        if ((propertyMask & PROP_TEXT_COLOR) != 0) builder.putValues("textColor", toWidgetValue(w.getTextColor()));
        if ((propertyMask & PROP_TEXT_SHADOWED) != 0) builder.putValues("textShadowed", toWidgetValue(w.getTextShadowed()));
        if ((propertyMask & PROP_TYPE) != 0) builder.putValues("type", toWidgetValue(w.getType()));
        if ((propertyMask & PROP_VAR_TRANSMIT_TRIGGER) != 0) builder.putValues("varTransmitTrigger", toWidgetValue(w.getVarTransmitTrigger()));
        if ((propertyMask & PROP_WIDTH) != 0) builder.putValues("width", toWidgetValue(w.getWidth()));
        if ((propertyMask & PROP_WIDTH_MODE) != 0) builder.putValues("widthMode", toWidgetValue(w.getWidthMode()));
        if ((propertyMask & PROP_X_POSITION_MODE) != 0) builder.putValues("xPositionMode", toWidgetValue(w.getXPositionMode()));
        if ((propertyMask & PROP_X_TEXT_ALIGNMENT) != 0) builder.putValues("xTextAlignment", toWidgetValue(w.getXTextAlignment()));
        if ((propertyMask & PROP_Y_POSITION_MODE) != 0) builder.putValues("yPositionMode", toWidgetValue(w.getYPositionMode()));
        if ((propertyMask & PROP_Y_TEXT_ALIGNMENT) != 0) builder.putValues("yTextAlignment", toWidgetValue(w.getYTextAlignment()));
        if ((propertyMask & PROP_IS_HIDDEN) != 0) builder.putValues("isHidden", toWidgetValue(w.isSelfHidden()));

        return builder;
    }

    public GetWidgetResponse getWidgetProperties(GetWidgetRequest request) {
        Widget w = client.getWidget(request.getWidgetId());
        if (w == null) {
            return GetWidgetResponse.newBuilder().setWidget(WidgetResponse.newBuilder().build()).build();
        }
        WidgetResponse widgetResponse = extractWidgetProperties(w, request.getMask()).build();
        return GetWidgetResponse.newBuilder().setWidget(widgetResponse).build();
    }

    public GetWidgetArrayResponse getWidgetPropertiesBatch(GetWidgetBatchedRequest request) {
        if (request.getWidgetIdsCount() != request.getMaskCount()) {
            throw new IllegalArgumentException("Widget IDs and masks arrays must have same length");
        }

        GetWidgetArrayResponse.Builder builder = GetWidgetArrayResponse.newBuilder();
        for (int i = 0; i < request.getWidgetIdsCount(); i++) {
            Widget w = client.getWidget(request.getWidgetIds(i));
            if (w != null) {
                builder.addWidgetArray(extractWidgetProperties(w, request.getMask(i)).build());
            }
        }
        return builder.build();
    }

    public GetWidgetArrayResponse getWidgetChildrenBatch(GetWidgetBatchedRequest request) {
        if (request.getWidgetIdsCount() != request.getMaskCount()) {
            throw new IllegalArgumentException("Widget IDs and masks arrays must have same length");
        }

        GetWidgetArrayResponse.Builder builder = GetWidgetArrayResponse.newBuilder();
        for (int i = 0; i < request.getWidgetIdsCount(); i++) {
            Widget w = client.getWidget(request.getWidgetIds(i));
            if (w == null) continue;

            Widget[] dynChildren = w.getDynamicChildren();
            if (dynChildren == null) continue;

            for (Widget child : dynChildren) {
                if (child != null) {
                    builder.addWidgetArray(extractWidgetProperties(child, request.getMask(i)).build());
                }
            }
        }
        return builder.build();
    }

    /**
     * Get the properties for a dynamic child of a widget.
     */
    public GetWidgetResponse getWidgetChild(GetWidgetChildRequest request) {
        Widget parent = client.getWidget(request.getWidgetId());
        if (parent == null) {
            throw new IllegalArgumentException("Parent widget not found: " + request.getWidgetId());
        }

        Widget[] dynChildren = parent.getDynamicChildren();
        if (dynChildren == null || dynChildren.length == 0) {
            throw new IllegalArgumentException("No dynamic children for widget: " + request.getWidgetId());
        }

        int idx = request.getChildIndex();
        if (idx < 0) idx = dynChildren.length + idx;

        if (idx < 0 || idx >= dynChildren.length) {
            throw new IllegalArgumentException("Child index out of range: " + request.getChildIndex());
        }

        Widget child = dynChildren[idx];
        WidgetResponse widgetResponse = extractWidgetProperties(child, request.getMask()).build();
        return GetWidgetResponse.newBuilder().setWidget(widgetResponse).build();
    }

    public GetWidgetArrayResponse getWidgetChildren(GetWidgetRequest request) {
        Widget parent = client.getWidget(request.getWidgetId());
        if (parent == null) {
            throw new IllegalArgumentException("Parent widget not found: " + request.getWidgetId());
        }

        Widget[] dynChildren = parent.getDynamicChildren();
        if (dynChildren == null || dynChildren.length == 0) {
            return GetWidgetArrayResponse.newBuilder().build();
        }

        GetWidgetArrayResponse.Builder builder = GetWidgetArrayResponse.newBuilder();
        for (Widget child : dynChildren) {
            if (child != null) {
                builder.addWidgetArray(extractWidgetProperties(child, request.getMask()).build());
            }
        }
        return builder.build();
    }

    public GetWidgetArrayResponse getWidgetChildrenMasked(GetWidgetChildrenMaskedRequest request) {
        Widget parent = client.getWidget(request.getWidgetId());
        if (parent == null) {
            throw new IllegalArgumentException("Parent widget not found: " + request.getWidgetId());
        }

        Widget[] dynChildren = parent.getDynamicChildren();
        if (dynChildren == null || dynChildren.length == 0) {
            return GetWidgetArrayResponse.newBuilder().build();
        }

        GetWidgetArrayResponse.Builder builder = GetWidgetArrayResponse.newBuilder();
        for (int rawIndex : request.getChildMaskList()) {
            int idx = rawIndex < 0 ? dynChildren.length + rawIndex : rawIndex;
            if (idx >= 0 && idx < dynChildren.length && dynChildren[idx] != null) {
                builder.addWidgetArray(extractWidgetProperties(dynChildren[idx], request.getMask()).build());
            }
        }
        return builder.build();
    }
}
