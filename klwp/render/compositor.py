"""Compose individual KLWP modules and their child layers."""

from ..shared import *  # noqa: F401,F403
from .context import ItemPlacement, PaintRequest, StackCursor


class CompositorLeafMixin:
    def _paint_item(self, image, item, parent_box, globals_=None,
                    preplaced=False, _root_animation=None,
                    _opacity_pass=False):
        request = PaintRequest(
            image=image, item=item, parent_box=parent_box,
            global_values=globals_, preplaced=preplaced,
            root_animation=_root_animation, opacity_pass=_opacity_pass,
        )
        self._paint_request(request)

    def _paint_request(self, request):
        self._prepare_request(request)
        if self._request_is_hidden(request):
            return
        if self._paint_root_opacity(request):
            return
        placement = self._item_placement(request)
        self._remember_item_bounds(request, placement)
        self._register_events(request, placement)
        self._paint_shadow(request, placement)
        self._paint_leaf(request, placement)
        self._paint_children(request, placement)

    def _prepare_request(self, request):
        request["is_root"] = request["parent_box"] is None
        request["root_animation"] = self._root_animation(request)
        global_values = request["global_values"] or self._root_globals()
        request["global_values"] = self._with_local_globals(
            request["item"], global_values)

    def _root_animation(self, request):
        animation = request["root_animation"]
        if not request["is_root"] or animation is not None:
            return animation
        return self._animation_transform(request["item"])

    def _request_is_hidden(self, request):
        animation = request["root_animation"]
        if request["is_root"] and animation["alpha"] <= 0.001:
            return True
        visible = self._value(
            request["item"], "config_visible", True,
            request["global_values"])
        if visible is False:
            return True
        return isinstance(visible, str) and visible.lower() == "false"

    def _paint_root_opacity(self, request):
        animation = request["root_animation"]
        if not self._needs_root_opacity(request, animation):
            return False
        image = request["image"]
        transparent = Image.new("RGBA", image.size, (0, 0, 0, 0))
        self._paint_item(
            transparent, request["item"], request["parent_box"],
            request["global_values"], request["preplaced"],
            _root_animation=animation, _opacity_pass=True)
        self._apply_opacity(transparent, animation["alpha"])
        image.alpha_composite(transparent)
        return True

    @staticmethod
    def _needs_root_opacity(request, animation):
        return (
            request["is_root"] and animation["alpha"] < 0.999
            and not request["opacity_pass"]
        )

    @staticmethod
    def _apply_opacity(image, opacity):
        alpha_channel = image.getchannel("A")
        table = [int(value * opacity) for value in range(256)]
        image.putalpha(alpha_channel.point(table))

    def _item_placement(self, request):
        scale = self.memory['_scale']
        box = self._request_box(request)
        item = request["item"]
        global_values = request["global_values"]
        width, height = self._item_size(item, global_values)
        horizontal, vertical = self._coordinates(request, box, width, height)
        horizontal, vertical = self._animated_coordinates(
            request, horizontal, vertical)
        return ItemPlacement(
            box=box, horizontal=horizontal, vertical=vertical,
            width=width, height=height,
            pixel_horizontal=int(horizontal * scale),
            pixel_vertical=int(vertical * scale),
            pixel_width=max(1, int(width * scale)),
            pixel_height=max(1, int(height * scale)),
            scale=scale,
        )

    def _request_box(self, request):
        if request["parent_box"] is not None:
            return request["parent_box"]
        document_width, document_height = self.memory['_doc']
        return (0, 0, document_width, document_height)

    def _coordinates(self, request, box, width, height):
        if request["preplaced"]:
            return box[0], box[1]
        return self._place(
            request["item"], box, width, height,
            is_root=request["is_root"],
            globals_=request["global_values"])

    @staticmethod
    def _animated_coordinates(request, horizontal, vertical):
        if not request["is_root"]:
            return horizontal, vertical
        animation = request["root_animation"]
        return horizontal + animation["dx"], vertical + animation["dy"]

    def _register_events(self, request, placement):
        events = request["item"].get("internal_events", []) or []
        if not events:
            return
        bounds = (
            placement["horizontal"], placement["vertical"],
            placement["width"], placement["height"],
        )
        self.memory['_event_regions'].append((request["item"], bounds, events))

    def _remember_item_bounds(self, request, placement):
        memory = self.memory
        bounds = (
            placement["horizontal"], placement["vertical"],
            placement["width"], placement["height"],
        )
        entries = memory.optional("_item_bounds", [])
        entries.append((request["item"], bounds))

    def _paint_shadow(self, request, placement):
        shadow = self._value(
            request["item"], "fx_shadow", "", request["global_values"])
        if shadow != "OUTER":
            return
        self._paint_outer_shadow(
            request["image"], request["item"],
            placement["pixel_horizontal"], placement["pixel_vertical"],
            placement["pixel_width"], placement["pixel_height"],
            placement["scale"], request["global_values"])

    def _paint_leaf(self, request, placement):
        item = request["item"]
        module_type = item.get("internal_type", "")
        angle = self._item_rotation(item, request["global_values"])
        if angle and module_type in ("ShapeModule", "TextModule"):
            self._paint_rotated_leaf(request, placement)
            return
        handlers = {
            "ShapeModule": self._paint_shape_leaf,
            "TextModule": self._paint_text_leaf,
            "FontIconModule": self._paint_icon_leaf,
            "BitmapModule": self._paint_bitmap_leaf,
            "ProgressModule": self._paint_progress_leaf,
        }
        handler = handlers.get(module_type)
        if handler is not None:
            handler(request, placement)

    def _paint_rotated_leaf(self, request, placement):
        self._paint_rotated_item(
            request["image"], request["item"],
            placement["pixel_horizontal"], placement["pixel_vertical"],
            placement["pixel_width"], placement["pixel_height"],
            placement["scale"], request["global_values"])

    def _paint_shape_leaf(self, request, placement):
        drawing = ImageDraw.Draw(request["image"])
        self._paint_shape(
            request["image"], drawing, request["item"],
            placement["pixel_horizontal"], placement["pixel_vertical"],
            placement["pixel_width"], placement["pixel_height"],
            placement["scale"], request["global_values"])

    def _paint_text_leaf(self, request, placement):
        drawing = ImageDraw.Draw(request["image"])
        self._paint_text(
            request["image"], drawing, request["item"],
            placement["horizontal"], placement["vertical"], placement["box"],
            placement["scale"], request["global_values"])

    def _paint_icon_leaf(self, request, placement):
        drawing = ImageDraw.Draw(request["image"])
        self._paint_icon(
            request["image"], drawing, request["item"],
            placement["pixel_horizontal"], placement["pixel_vertical"],
            placement["pixel_width"], placement["pixel_height"],
            request["global_values"])

    def _paint_bitmap_leaf(self, request, placement):
        self._paint_bitmap(
            request["image"], request["item"],
            placement["pixel_horizontal"], placement["pixel_vertical"],
            placement["pixel_width"], placement["pixel_height"],
            request["global_values"])

    def _paint_progress_leaf(self, request, placement):
        drawing = ImageDraw.Draw(request["image"])
        self._paint_progress(
            request["image"], drawing, request["item"],
            placement["pixel_horizontal"], placement["pixel_vertical"],
            placement["scale"], request["global_values"])

class CompositorMixin(CompositorLeafMixin):
    def _paint_children(self, request, placement):
        item = request["item"]
        if self._paint_rotated_group(request, placement):
            return
        if item.get("internal_type") == "StackLayerModule":
            self._paint_stack(request, placement)
            return
        if "viewgroup_items" in item:
            self._paint_overlap(request, placement)

    def _paint_rotated_group(self, request, placement):
        item = request["item"]
        global_values = request["global_values"]
        angle = self._group_rotation(item, global_values)
        if not angle or item.get("internal_type") == "StackLayerModule":
            return False
        if "viewgroup_items" not in item:
            return False
        image = request["image"]
        transparent = Image.new("RGBA", image.size, (0, 0, 0, 0))
        child_box = self._child_box(placement)
        for child in item.get("viewgroup_items", []):
            self._paint_item(transparent, child, child_box, global_values)
        center = self._rotation_center(placement)
        rotated = transparent.rotate(
            -angle, resample=Resampling.BICUBIC,
            center=center, expand=False)
        image.alpha_composite(rotated)
        return True

    @staticmethod
    def _child_box(placement):
        return (
            placement["horizontal"], placement["vertical"],
            placement["width"], placement["height"],
        )

    @staticmethod
    def _rotation_center(placement):
        horizontal = placement["pixel_horizontal"] + placement["pixel_width"] / 2
        vertical = placement["pixel_vertical"] + placement["pixel_height"] / 2
        return horizontal, vertical

    def _paint_stack(self, request, placement):
        cursor = StackCursor(placement["horizontal"], placement["vertical"])
        children = request["item"].get("viewgroup_items", [])
        for child in children:
            self._paint_stack_child(request, placement, cursor, child)

    def _paint_stack_child(self, request, placement, cursor, child):
        item = request["item"]
        global_values = request["global_values"]
        child_width, child_height = self._item_size(child, global_values)
        padding = self._child_padding(child, global_values)
        child_box = self._stack_child_box(
            item, placement, cursor, child_width, child_height, padding)
        self._paint_item(
            request["image"], child, child_box, global_values, preplaced=True)
        margin = self._number(item, "config_margin", 0.0, global_values)
        self._advance_stack_cursor(item, cursor, child_width, child_height, padding, margin)

    def _child_padding(self, child, global_values):
        return {
            "left": self._number(child, "position_padding_left", 0.0, global_values),
            "right": self._number(child, "position_padding_right", 0.0, global_values),
            "top": self._number(child, "position_padding_top", 0.0, global_values),
            "bottom": self._number(child, "position_padding_bottom", 0.0, global_values),
        }

    def _stack_child_box(self, item, placement, cursor, width, height, padding):
        if self._stack_is_horizontal(item):
            return self._horizontal_child_box(
                item, placement, cursor, width, height, padding)
        return self._vertical_child_box(
            item, placement, cursor, width, height, padding)

    def _horizontal_child_box(self, item, placement, cursor, width, height, padding):
        horizontal = cursor.horizontal() + padding["left"]
        vertical = self._horizontal_child_vertical(
            item, placement, height, padding)
        return horizontal, vertical, width, height

    @staticmethod
    def _horizontal_child_vertical(item, placement, height, padding):
        stacking = str(item.get("config_stacking", ""))
        if "TOP" in stacking:
            return placement["vertical"] + padding["top"]
        if "BOTTOM" in stacking:
            return placement["vertical"] + placement["height"] - padding["bottom"] - height
        difference = (padding["top"] - padding["bottom"]) / 2
        return placement["vertical"] + (placement["height"] - height) / 2 + difference

    def _vertical_child_box(self, item, placement, cursor, width, height, padding):
        horizontal = self._vertical_child_horizontal(
            item, placement, width, padding)
        vertical = cursor.vertical() + padding["top"]
        return horizontal, vertical, width, height

    @staticmethod
    def _vertical_child_horizontal(item, placement, width, padding):
        stacking = str(item.get("config_stacking", ""))
        if "LEFT" in stacking:
            return placement["horizontal"] + padding["left"]
        if "RIGHT" in stacking:
            return placement["horizontal"] + placement["width"] - padding["right"] - width
        difference = (padding["left"] - padding["right"]) / 2
        return placement["horizontal"] + (placement["width"] - width) / 2 + difference

    def _advance_stack_cursor(self, item, cursor, width, height, padding, margin):
        if self._stack_is_horizontal(item):
            cursor.move_horizontal(width + padding["left"] + padding["right"] + margin)
            return
        cursor.move_vertical(height + padding["top"] + padding["bottom"] + margin)

    def _paint_overlap(self, request, placement):
        clip_mask = None
        children = request["item"]["viewgroup_items"]
        for child in children:
            clip_mask = self._paint_overlap_child(
                request, placement, child, clip_mask)

    def _paint_overlap_child(self, request, placement, child, clip_mask):
        child_box = self._child_box(placement)
        if self._is_clip_shape(child):
            return self._clip_mask_for(
                request["image"].size, child, child_box,
                request["global_values"])
        if clip_mask is not None:
            self._paint_clipped_child(request, child_box, child, clip_mask)
            return None
        self._paint_unclipped_child(request, placement, child_box, child)
        return None

    @staticmethod
    def _is_clip_shape(child):
        is_shape = child.get("internal_type") == "ShapeModule"
        mask = str(child.get("fx_mask", ""))
        return is_shape and mask.startswith("CLIP")

    def _paint_clipped_child(self, request, child_box, child, clip_mask):
        image = request["image"]
        transparent = Image.new("RGBA", image.size, (0, 0, 0, 0))
        self._paint_item(
            transparent, child, child_box, request["global_values"])
        alpha_channel = transparent.getchannel("A")
        transparent.putalpha(ImageChops.multiply(alpha_channel, clip_mask))
        image.alpha_composite(transparent)

    def _paint_unclipped_child(self, request, placement, child_box, child):
        global_values = request["global_values"]
        child_width, child_height = self._item_size(child, global_values)
        if self._is_full_background(child, placement, child_width, child_height):
            fixed_box = (
                placement["horizontal"], placement["vertical"],
                child_width, child_height,
            )
            self._paint_item(
                request["image"], child, fixed_box, global_values,
                preplaced=True)
            return
        self._paint_item(request["image"], child, child_box, global_values)

    @staticmethod
    def _is_full_background(child, placement, width, height):
        if child.get("internal_type") != "ShapeModule":
            return False
        same_width = abs(width - placement["width"]) < 0.01
        same_height = abs(height - placement["height"]) < 0.01
        return same_width and same_height
