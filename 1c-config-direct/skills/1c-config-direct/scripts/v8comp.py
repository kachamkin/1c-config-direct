# Composite object properties: input by string, data lock fields (lists of fields) and characteristics.
#   field reference  {"#",60ea359f-3a6e-48bb-8e71-d2a457572918,{<std id>}} | {…,{0,<field uuid>}}
#                    inside a characteristic the same body comes as {1,{<std id>}|{0,<uuid>},0}; {-1} = not set
#   list of fields   {1,{0,N,<field reference>…}}
#   characteristic   {"#",fe839d42-d094-40ba-b903-75bccc21ba30,{4,{1,<types from>},{1,<values from>},<object field>,
#                     <type field>,<value field>,<types filter field>,<types filter value>,<key field>,<4 optional fields>}}
#   the characteristics property  {1,{N,<characteristic>…}}
# A standard attribute is named by its id in the class of the object the field belongs to (v8std.STD_IDS); the types
# filter value is a predefined item {"#",5c14e26f-…,{0,<TypeId>,<item uuid>}} (names: v8pred), a string or empty.
import re
from v8meta import unq
from v8std import STD_IDS, TS_LINE_ID

FIELD_REF = '60ea359f-3a6e-48bb-8e71-d2a457572918'
CHARACTERISTIC = 'fe839d42-d094-40ba-b903-75bccc21ba30'
DESIGN_TIME_REF = '5c14e26f-099b-4d37-84a6-b433d87400da'
ZERO = '00000000-0000-0000-0000-000000000000'


class Context:
    """what decoding needs from the configuration: names of fields, tabular sections and predefined items"""

    def __init__(self, cfg):
        from v8std import tabular_sections
        from v8meta import find_name_block
        self.cfg = cfg
        self.names = dict(cfg.ref_names())
        self.cls_of = {}
        for it, tree in cfg.trees():
            self.cls_of[it.path] = it.cls
            for name, node in tabular_sections(it.cls, tree):
                nb = find_name_block(node[0])
                if nb:
                    self.names[nb[1][2]] = '%s.TabularSections.%s' % (it.path, name)
                    self.cls_of[self.names[nb[1][2]]] = it.cls
        self.types = cfg.types()
        self._predefined = {}

    def predefined(self, obj_path):
        """{item uuid: name} of the predefined items of an object"""
        if obj_path not in self._predefined:
            from v8pred import FILE, items, walk
            self._predefined[obj_path] = out = {}         # set first: no second entry while the names are read
            it = next((i for i in self.cfg.items.values() if i.path == obj_path), None)
            if it is not None and it.cls in FILE:
                try:
                    out = {x.uuid: x.name for d, x in walk(items(self.cfg, it) or [])}
                except Exception:          # an unknown layout of the file: names stay unknown, as for a deleted item
                    out = {}
            self._predefined[obj_path] = out
        return self._predefined[obj_path]


def _std_name(ctx, source, sid):
    """name of a standard attribute by its id, for a field of `source` (an object or one of its tabular sections)"""
    cls = ctx.cls_of.get(source) or source.split('.')[0]
    if '.TabularSections.' in source and sid == TS_LINE_ID.get(cls, '-10'):
        return 'LineNumber'
    return STD_IDS.get(cls, {}).get(sid, '?' + sid)


def field_name(ctx, source, body):
    """{-3} -> '<source>.StandardAttributes.Description'; {0,<uuid>} -> path of the field; {-1} -> None"""
    if not isinstance(body, list) or not body:
        return None
    if len(body) == 1 and isinstance(body[0], str):
        if body[0] == '-1':
            return None
        return '%s.StandardAttributes.%s' % (source, _std_name(ctx, source, body[0]))
    if len(body) >= 2 and body[0] == '0' and isinstance(body[1], str):
        return ctx.names.get(body[1], body[1])
    return '?' + repr(body)[:40]


def decode_fields(ctx, owner, node):
    """{1,{0,N,<field reference>…}} -> [field path]; None when the node is not such a list"""
    lst = node[1] if isinstance(node, list) and len(node) == 2 and isinstance(node[1], list) else node
    if not (isinstance(lst, list) and len(lst) >= 2 and lst[0] == '0' and isinstance(lst[1], str) and lst[1].isdigit()
            and len(lst) == 2 + int(lst[1])):
        return None
    out = []
    for r in lst[2:]:
        if not (isinstance(r, list) and len(r) >= 3 and r[0] == '"#"' and r[1] == FIELD_REF):
            return None
        out.append(field_name(ctx, owner, r[2]))
    return out


def _value(ctx, v):
    if isinstance(v, list) and len(v) >= 3 and v[0] == '"#"' and v[1] == DESIGN_TIME_REF and isinstance(v[2], list) and len(v[2]) >= 3:
        k, item = ctx.types.get(v[2][1], ('?', v[2][1])), v[2][2]
        if k[0] == 'Type' and 'Ref.' in k[1]:
            ref_cls, obj = k[1].split('.', 1)
            plural = {'CatalogRef': 'Catalogs', 'ChartOfCharacteristicTypesRef': 'ChartsOfCharacteristicTypes',
                      'ChartOfAccountsRef': 'ChartsOfAccounts', 'ChartOfCalculationTypesRef': 'ChartsOfCalculationTypes',
                      'EnumRef': 'Enums'}.get(ref_cls, ref_cls)
            path = '%s.%s' % (plural, obj)
            name = 'EmptyRef' if item == ZERO else ctx.predefined(path).get(item)
            if name is not None:
                return '%s.%s' % (path, name)
        return '%s.%s' % (v[2][1], item)     # the item is gone: written as in the XML dump, <TypeId>.<uuid>
    if isinstance(v, list) and v and v[0] == '"S"':
        return '"%s"' % unq(v[1]) if len(v) > 1 else '""'
    if isinstance(v, list) and v and v[0] == '"U"':
        return ''
    return repr(v)[:60]


def short(source, path):
    """a field of the source -> its name relative to the source: 'Свойство', 'Ref' (fields of other objects stay full)"""
    if path and source and path.startswith(source + '.'):
        return re.sub(r'^(StandardAttributes|Attributes|Dimensions|Resources|AddressingAttributes)\.', '', path[len(source) + 1:])
    return path


def decode_characteristics(ctx, owner, node):
    """{1,{N,<characteristic>…}} -> [description]; None when the node is not such a list"""
    lst = node[1] if isinstance(node, list) and len(node) == 2 and isinstance(node[1], list) else node
    if not (isinstance(lst, list) and lst and isinstance(lst[0], str) and lst[0].isdigit() and len(lst) == 1 + int(lst[0])):
        return None
    out = []
    for c in lst[1:]:
        if not (isinstance(c, list) and len(c) >= 3 and c[0] == '"#"' and c[1] == CHARACTERISTIC and isinstance(c[2], list)):
            return None
        b = c[2]
        # a source the configuration no longer has is left empty, as the XML dump does
        src = lambda x: ctx.names.get(x[1], '') if isinstance(x, list) and len(x) > 1 else ''
        types_from, values_from = src(b[1]), src(b[2])
        fld = lambda x, s: short(s, field_name(ctx, s, x[1] if isinstance(x, list) and len(x) > 1 else None)) or ''
        desc = 'types %s: key %s, filter %s = %s | values %s: object %s, type %s, value %s' % (
            types_from, fld(b[8], types_from), fld(b[6], types_from), _value(ctx, b[7]),
            values_from, fld(b[3], values_from), fld(b[4], values_from), fld(b[5], values_from))
        extra = [fld(x, types_from if i < 2 else values_from) for i, x in enumerate(b[9:13])]
        if any(extra):
            desc += ' | optional ' + ', '.join(x or '-' for x in extra)
        out.append(desc)
    return out
