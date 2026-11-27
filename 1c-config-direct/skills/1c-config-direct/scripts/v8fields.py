# Field properties: indexing, fill checking, use, master dimension … at places learned against XML (field_props.json,
# learn_fields.py), and the choice parameters and choice parameter links of the common block of a field.
# A tabular section attribute whose group was not learned takes the place every other class gives it (the tail of
# such attributes is laid out alike in all classes); other kinds of fields are read only where learned.
#   field          {<field version>,{<common version 27>,{2,<name block>,{"Pattern",…}},<common properties>…},<tail>…}
#   parameters     common[16] = {0,N,"<name>",<value>,…}
#   links          common[14] = {5006,N,"<name>",K,<part>×K,<0 Clear | 1 DontChange>,…}; a part is {<std id>} | {0,<uuid>} | {0}
#   value          {"B",1} | {"S","…"} | {"N",5} | {"U"} | {"#",5c14e26f-…,{0,<TypeId>,<uuid>}} (enum value, predefined item)
#                  | {"#",4500381b-…,{N,<value>…}} (fixed array)
import collections
import json
import os
from v8meta import unq, is_collection, find_name_block, KIND, NAMED
from v8std import STD_IDS

FIXED_ARRAY = '4500381b-db30-4a10-9db4-990038032acf'
DESIGN_TIME_REF = '5c14e26f-099b-4d37-84a6-b433d87400da'
ZERO = '00000000-0000-0000-0000-000000000000'
VALUE_CHANGE = {'0': 'Clear', '1': 'DontChange'}
COMMON_PARAMETERS, COMMON_LINKS = 16, 14
PLURAL_REF = {'CatalogRef': 'Catalogs', 'ChartOfCharacteristicTypesRef': 'ChartsOfCharacteristicTypes',
              'ChartOfAccountsRef': 'ChartsOfAccounts', 'ChartOfCalculationTypesRef': 'ChartsOfCalculationTypes',
              'EnumRef': 'Enums', 'ExchangePlanRef': 'ExchangePlans', 'DocumentRef': 'Documents',
              'BusinessProcessRef': 'BusinessProcesses', 'TaskRef': 'Tasks'}
_TABLES = None


def tables():
    """field_props.json, with two additions made on load:
    - one code table per property, merged over all groups, when the groups never disagree on a token;
    - for a group that lacks a property, the place every other class gives it for the same kind of field and field
      version (all values default in learning: the place could not be seen)"""
    global _TABLES
    if _TABLES is None:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'field_props.json')
        t = json.load(open(p, encoding='utf-8')) if os.path.isfile(p) else {'common': {}, 'tail': {}}
        codecs, bad = {}, set()
        for vers in t['tail'].values():
            for props in vers.values():
                for prop, d in props.items():
                    if isinstance(d['codec'], dict):
                        merged = codecs.setdefault(prop, {})
                        for tok, val in d['codec'].items():
                            if merged.setdefault(tok, val) != val:
                                bad.add(prop)
        shapes, classes = {}, collections.defaultdict(set)
        for g, vers in t['tail'].items():
            cls, kind_ts = g.split('/', 1)
            if kind_ts != 'Attribute/TS':     # elsewhere the tail differs by class (a catalog attribute has Use …)
                continue
            for v, props in vers.items():
                for prop, d in props.items():
                    shapes.setdefault((kind_ts, v), {}).setdefault(prop, set()).add(d['place'])
                    classes[(kind_ts, v, prop)].add(cls)
        shapes = {key: {prop: places for prop, places in props.items() if len(classes[key + (prop,)]) >= 2}
                  for key, props in shapes.items()}
        for g, vers in t['tail'].items():
            for v, props in vers.items():
                for prop, d in props.items():
                    if isinstance(d['codec'], dict) and prop in codecs and prop not in bad:
                        d['codec'] = codecs[prop]
        t['_shape'] = {key: {prop: {'place': next(iter(places)), 'codec': codecs.get(prop)}
                             for prop, places in props.items() if len(places) == 1 and prop in codecs and prop not in bad}
                       for key, props in shapes.items()}
        _TABLES = t
    return _TABLES


def field_nodes(tree):
    """{field uuid: (kind, in a tabular section, common block, field node)} for the typed fields of an object"""
    out, parents = {}, {}

    def walk(node, chain, coll, ts):
        if not isinstance(node, list):
            return
        if is_collection(node):
            coll = node[0]
        for i, x in enumerate(node):
            if isinstance(x, list) and x and x[0] == '"Pattern"' and i > 0 and len(chain) >= 2:
                nb = find_name_block(node[i - 1])
                common, field = chain[-1], chain[-2]
                if nb and isinstance(common, list) and len(common) > 1 and isinstance(common[0], str) and common[1] is node \
                        and isinstance(field, list) and field and isinstance(field[0], str) and field[1] is common:
                    out[nb[1][2]] = (KIND.get(coll, 'Type' if coll is None else 'Field'), ts, common, field)
        for x in node:
            if isinstance(x, list):
                sub = ts or bool(x and isinstance(x[0], list) and any(is_collection(y) for y in x[1:]) and find_name_block(x[0]))
                walk(x, chain + [node], coll, sub)
    walk(tree, [], None, False)
    return out


class Names:
    """names of enum values and predefined items, for values of choice parameters"""

    def __init__(self, cfg, comp):
        self.cfg, self.comp = cfg, comp
        self._enum = {}

    def enum_values(self, path):
        if path not in self._enum:
            it = next((i for i in self.cfg.items.values() if i.path == path), None)
            t = self.cfg._texts.get(it.uuid, '') if it is not None else ''
            self._enum[path] = {u: n.replace('""', '"') for u, n in NAMED.findall(t) if it is None or u != it.uuid}
        return self._enum[path]

    def ref(self, type_id, uuid):
        if type_id == ZERO:                        # an empty value of no type: the XML dump leaves it empty
            return ''
        k = self.comp.types.get(type_id, ('?', type_id))
        if k[0] == 'Type' and '.' in k[1]:
            ref_cls, obj = k[1].split('.', 1)
            path = '%s.%s' % (PLURAL_REF.get(ref_cls, ref_cls), obj)
            if uuid == ZERO:
                return path + '.EmptyRef'
            if ref_cls == 'EnumRef':
                name = self.enum_values(path).get(uuid)
                if name:
                    return '%s.EnumValue.%s' % (path, name)
            else:
                name = self.comp.predefined(path).get(uuid)
                if name:
                    return '%s.%s' % (path, name)
        return '%s.%s' % (type_id, uuid)          # as the XML dump writes a reference it cannot name


def value(names, v):
    if not isinstance(v, list) or not v:
        return '?'
    k = v[0]
    if k == '"B"':
        return 'true' if len(v) > 1 and v[1] == '1' else 'false'
    if k == '"S"':
        return '"%s"' % (unq(v[1]) if len(v) > 1 else '')
    if k == '"N"':
        return v[1] if len(v) > 1 else '0'
    if k == '"U"':
        return ''
    if k == '"#"' and len(v) >= 3 and v[1] == DESIGN_TIME_REF and isinstance(v[2], list) and len(v[2]) >= 3:
        return names.ref(v[2][1], v[2][2])
    if k == '"#"' and len(v) >= 3 and v[1] == FIXED_ARRAY and isinstance(v[2], list):
        return '[%s]' % ', '.join(value(names, x) for x in v[2][1:])
    return '?' + json.dumps(v, ensure_ascii=False)[:40]


def choice_parameters(names, node):
    """{0,N,"<name>",<value>,…} -> ['<name> = <value>']"""
    if not (isinstance(node, list) and len(node) >= 2 and node[0] == '0' and node[1].isdigit()):
        return None
    items = node[2:]
    return ['%s = %s' % (unq(items[i]), value(names, items[i + 1])) for i in range(0, len(items) - 1, 2)]


def _part(comp, owner, cls, p):
    if not isinstance(p, list) or not p:
        return '?'
    if len(p) == 1:
        sid = p[0]
        name = STD_IDS.get(cls, {}).get(sid) if sid.startswith('-') else None
        return '%s.StandardAttributes.%s' % (owner, name) if name else sid
    if p[0] == '0' and len(p) >= 2:
        # a field of the object itself or a constant; a field of another object is a stale link, written raw as in XML
        name = comp.names.get(p[1])
        return name if name and (name.startswith(owner + '.') or name.startswith('Constants.')) else '0:' + p[1]
    return '?'


def choice_links(comp, owner, cls, node):
    """{5006,N,"<name>",K,<part>…,<change>,…} -> ['<name> = <data path> (<Clear|DontChange>)']"""
    if not (isinstance(node, list) and len(node) >= 2 and node[1].isdigit()):
        return None
    out, i = [], 2
    for _ in range(int(node[1])):
        if i + 1 >= len(node):
            return None
        name, k = unq(node[i]), int(node[i + 1]) if node[i + 1].isdigit() else 0
        parts = node[i + 2:i + 2 + k]
        change = node[i + 2 + k] if i + 2 + k < len(node) else '?'
        if k == 1:
            path = _part(comp, owner, cls, parts[0])
        else:
            # a tabular section and its attribute: named by the attribute, as the XML dump does; otherwise written raw
            steps = [comp.names.get(p[1]) if isinstance(p, list) and len(p) >= 2 and p[0] == '0' else None for p in parts]
            if all(steps) and steps[0].startswith(owner + '.') and \
                    all(steps[j + 1].startswith(steps[j] + '.') for j in range(len(steps) - 1)):
                path = steps[-1]
            else:
                path = '/'.join(('0:' + p[1]) if len(p) >= 2 and p[0] == '0' else p[0] for p in parts if isinstance(p, list) and p)
        out.append('%s = %s (%s)' % (name, path, VALUE_CHANGE.get(change, '?' + str(change))))
        i += 3 + k
    return out


def _scalar(token, codec, comp=None):
    if not isinstance(token, str):
        return None
    if codec is None:
        return token
    if codec == 'str':
        return unq(token)
    if codec == 'ref':                              # a field (accounting flag, addressing dimension): its path
        return '' if token == ZERO else (comp.names.get(token, token) if comp else token)
    return codec.get(token, '?' + token)


def object_field_props(cfg, it, tree):
    """{field uuid: {property: value}} for the fields of one object: learned scalars, ChoiceParameters,
    ChoiceParameterLinks"""
    t = tables()
    comp = cfg.comp_context()
    names = getattr(cfg, '_field_names', None)
    if names is None:
        names = cfg._field_names = Names(cfg, comp)
    out = {}
    for uuid, (kind, ts, common, field) in field_nodes(tree).items():
        props = {}
        for p, d in t['common'].get(common[0], {}).items():
            v = _scalar(common[d['place']] if d['place'] < len(common) else None, d['codec'])
            if v is not None:
                props[p] = v
        kind_ts = '%s/%s' % (kind, 'TS' if ts else '')
        own = t['tail'].get('%s/%s' % (it.cls, kind_ts), {}).get(field[0], {})
        shape = t['_shape'].get((kind_ts, field[0]), {})
        for p, d in list(own.items()) + [(p, d) for p, d in shape.items() if p not in own]:
            v = _scalar(field[d['place']] if d['place'] < len(field) else None, d['codec'], comp)
            if v is not None:
                props[p] = v
        if common[0] == '27':
            cp = choice_parameters(names, common[COMMON_PARAMETERS]) if len(common) > COMMON_PARAMETERS else None
            cl = choice_links(comp, it.path, it.cls, common[COMMON_LINKS]) if len(common) > COMMON_LINKS else None
            if cp is not None:
                props['ChoiceParameters'] = cp
            if cl is not None:
                props['ChoiceParameterLinks'] = cl
        out[uuid] = props
    return out
