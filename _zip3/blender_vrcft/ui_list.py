import bpy
from bpy.types import UIList


def compute_filter_and_order(items, sort_alphabetical, show_unmatched, filter_name, bitflag):
    """Pure function: derive UIList filter flags and order map. Testable."""
    n = len(items)
    flt_flags = [bitflag] * n

    if not show_unmatched:
        for i, it in enumerate(items):
            if not it.matched:
                flt_flags[i] &= ~bitflag

    if filter_name:
        needle = filter_name.lower()
        for i, it in enumerate(items):
            if needle not in it.name.lower():
                flt_flags[i] &= ~bitflag

    if sort_alphabetical:
        ranked = sorted(range(n), key=lambda i: items[i].name.lower())
        order_map = [0] * n
        for new_pos, old_idx in enumerate(ranked):
            order_map[old_idx] = new_pos
        return flt_flags, order_map

    # Default: insertion order. Returning [] tells Blender's UIList to keep
    # the underlying CollectionProperty order, which is stable (items only
    # ever appended, never reordered, so rows stay put once seen).
    return flt_flags, []


class VRCFT_UL_params(UIList):
    bl_idname = "VRCFT_UL_params"

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        if self.layout_type in ('DEFAULT', 'COMPACT'):
            split = layout.split(factor=0.45, align=True)
            name_row = split.row(align=True)
            if not item.matched:
                name_row.label(text=item.name, icon='ERROR')
            else:
                name_row.label(text=item.name, icon='SHAPEKEY_DATA')
            split.progress(factor=item.value, text=f"{item.value:.2f}", type='BAR')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.name)

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        s = context.scene.vrcft
        return compute_filter_and_order(
            items,
            sort_alphabetical=s.sort_alphabetical,
            show_unmatched=s.show_unmatched,
            filter_name=self.filter_name,
            bitflag=self.bitflag_filter_item,
        )


_classes = (VRCFT_UL_params,)


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
