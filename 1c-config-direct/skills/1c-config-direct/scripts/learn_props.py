# learn_props.py — learn where object properties sit in object descriptions, by comparing with XML dumps.
# Maintenance tool: regenerates scripts/props_tables.json, which v8meta.py uses at run time.
#
#   py -X utf8 learn_props.py <source> <XML dump dir> [...] [--out props_tables.json] [--samples cache.pkl]
#   (with --samples and no sources, the cached samples are reused)
#
# A property is learned per (class, format version of the object description): its index path in the description
# and, for scalar values, the code table (raw token -> XML value). Properties whose position cannot be confirmed
# with >= 97% agreement on real objects are left out.
import collections, json, os, re, sys, types
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from v8meta import is_collection, unq, GUID  # noqa: E402
import cfgread  # noqa: E402

MD = '{http://v8.1c.ru/8.3/MDClasses}'
XR = '{http://v8.1c.ru/8.3/xcf/readable}'
MDREF = '157fa490-4ce9-11d4-9415-008048da11f9'
SUB = {'Form': 'Forms', 'Command': 'Commands', 'Template': 'Templates', 'Attribute': 'Attributes',
       'TabularSection': 'TabularSections', 'Dimension': 'Dimensions', 'Resource': 'Resources',
       'AddressingAttribute': 'AddressingAttributes'}
FIELD_KIND = {'Attribute': 'Attributes', 'Dimension': 'Dimensions', 'Resource': 'Resources', 'AddressingAttribute': 'AddressingAttributes'}


def plural_map():
    from v8meta import CLASS, SINGULAR
    m = {v: k for k, v in SINGULAR.items()}
    for cls in CLASS.values():                          # CommonModules -> CommonModule, Subsystems -> Subsystem ...
        if cls not in m.values():
            s = cls[:-1] if cls.endswith('s') else cls
            for a, b in (('Criteria', 'Criterion'), ('ies', 'y'), ('ses', 's')):
                if cls.endswith(a):
                    s = cls[:-len(a)] + b
            m[s] = cls
    m.update({'FilterCriterion': 'FilterCriteria', 'BusinessProcess': 'BusinessProcesses', 'Subsystem': 'Subsystems'})
    return m


PLURAL = plural_map()


def xml_ref(s):
    """'Catalog.X.Form.Y' -> 'Catalogs.X.Forms.Y' (None when it does not look like a metadata reference)"""
    p = s.split('.')
    if len(p) < 2 or len(p) % 2 or p[0] not in PLURAL:
        return None
    out = [PLURAL[p[0]], p[1]]
    for i in range(2, len(p), 2):
        if p[i] not in SUB:
            return None
        out += [SUB[p[i]], p[i + 1]]
    return '.'.join(out)


FIELD_SUB = dict(SUB, StandardAttribute='StandardAttributes', AccountingFlag='AccountingFlags',
                 ExtDimensionAccountingFlag='ExtDimensionAccountingFlags')
XSI_TYPE = '{http://www.w3.org/2001/XMLSchema-instance}type'


def xml_field(s):
    """'Catalog.X.StandardAttribute.Code' -> 'Catalogs.X.StandardAttributes.Code' (None for '-1' and the like)"""
    p = (s or '').strip().split('.')
    if len(p) < 4 or len(p) % 2 or p[0] not in PLURAL:
        return None
    out = [PLURAL[p[0]], p[1]]
    for i in range(2, len(p), 2):
        if p[i] not in FIELD_SUB:
            return None
        out += [FIELD_SUB[p[i]], p[i + 1]]
    return '.'.join(out)


def xml_characteristic(c):
    """<xr:Characteristic> -> the description v8comp.decode_characteristics gives"""
    from v8comp import short
    t, v = c.find(XR + 'CharacteristicTypes'), c.find(XR + 'CharacteristicValues')
    tf, vf = xml_ref(t.get('from') or '') or '', xml_ref(v.get('from') or '') or ''
    f = lambda e, name, src: short(src, xml_field(e.findtext(XR + name))) or ''
    tv = t.find(XR + 'TypesFilterValue')
    kind, text = (tv.get(XSI_TYPE), (tv.text or '').strip()) if tv is not None else (None, '')
    if kind == 'xr:DesignTimeRef' and '.' in text:
        head, rest = text.split('.', 1)
        value = '%s.%s' % (PLURAL.get(head, head), rest)
    elif kind == 'xs:string':
        value = '"%s"' % text
    else:
        value = text
    desc = 'types %s: key %s, filter %s = %s | values %s: object %s, type %s, value %s' % (
        tf, f(t, 'KeyField', tf), f(t, 'TypesFilterField', tf), value, vf, f(v, 'ObjectField', vf), f(v, 'TypeField', vf),
        f(v, 'ValueField', vf))
    extra = [f(t, 'DataPathField', tf), f(t, 'MultipleValuesUseField', tf), f(v, 'MultipleValuesKeyField', vf),
             f(v, 'MultipleValuesOrderField', vf)]
    if any(extra):
        desc += ' | optional ' + ', '.join(x or '-' for x in extra)
    return desc


def xml_props(path):
    """object XML -> {prop: ('scalar', text) | ('ref', name) | ('list', tuple(names)) | ('fields', tuple(fields))
    | ('characteristics', tuple(descriptions))}"""
    obj = next(iter(ET.parse(path).getroot()))
    pr = obj.find(MD + 'Properties')
    out = {}
    for e in pr if pr is not None else []:
        tag = e.tag.replace(MD, '')
        kids = list(e)
        if tag in ('InputByString', 'DataLockFields') and all(k.tag == XR + 'Field' for k in kids):
            out[tag] = ('fields', tuple(xml_field(k.text) or (k.text or '').strip() for k in kids)) if kids else ('empty', '')
            continue
        if tag == 'Characteristics':
            out[tag] = ('characteristics', tuple(xml_characteristic(k) for k in kids)) if kids else ('empty', '')
            continue
        if not kids:
            t = (e.text or '').strip()
            r = xml_ref(t) if t else None
            m = re.match(r'^CommonModule\.([^.]+)\.([^.]+)$', t)
            if m:
                out[tag] = ('method', ('CommonModules.' + m.group(1), m.group(2)))
            else:
                out[tag] = ('ref', r) if r else ('scalar', t) if t else ('empty', '')   # empty: list, ref or text
        elif all(k.tag == XR + 'Item' for k in kids):
            names = [xml_ref((k.text or '').strip()) for k in kids]
            if all(names):
                out[tag] = ('list', tuple(sorted(names)))
    return out


def walk(node, names, path=(), atoms=None, refs=None, depth=0):
    """atoms: path -> raw token; refs: path -> ('list', names) | ('ref', name)"""
    atoms = {} if atoms is None else atoms
    refs = {} if refs is None else refs
    if isinstance(node, list):
        if len(node) >= 3 and node[0] == '"#"' and node[1] == MDREF and isinstance(node[2], list) and len(node[2]) > 1:
            refs[path] = ('ref', names.get(node[2][1], node[2][1]))
        elif len(node) >= 2 and isinstance(node[0], str) and node[0].isdigit() and isinstance(node[1], str) and node[1].isdigit():
            items = node[2:]
            if len(items) == int(node[1]) and all(isinstance(x, list) and len(x) >= 3 and x[1] == MDREF for x in items):
                refs[path] = ('list', tuple(sorted(names.get(x[2][1], x[2][1]) for x in items)))
        for i, x in enumerate(node):
            p = path + (i,)
            if isinstance(x, list):
                if not is_collection(x) and depth < 8:
                    walk(x, names, p, atoms, refs, depth + 1)
            else:
                atoms[p] = x
                if x == '00000000-0000-0000-0000-000000000000':
                    refs.setdefault(p, ('ref', None))          # empty reference
                elif GUID.match(x) and x in names:
                    refs.setdefault(p, ('ref', names[x]))
                    nxt = node[i + 1] if i + 1 < len(node) else None
                    if isinstance(nxt, str) and nxt[:1] == '"':
                        refs[p + (-1,)] = ('method', (names[x], unq(nxt)))
    return atoms, refs


def collect(spec, conf):
    a = types.SimpleNamespace(no_sync=True, cache=None)
    cfg, desc, _ = cfgread.open_source(spec, a)
    names = {u: it.path for u, it in cfg.items.items()}
    for f in cfg.fields():
        kind = FIELD_KIND.get(f.kind)
        if kind:
            names[f.uuid] = ('%s.TabularSections.%s.Attributes.%s' % (f.obj, f.path, f.name)) if f.path else '%s.%s.%s' % (f.obj, kind, f.name)
    samples = []
    for it, tree in cfg.trees():
        x = os.path.join(conf, it.cls, it.name + '.xml')
        if not os.path.isfile(x):
            continue
        ver = tree[1][0] if isinstance(tree[1], list) and tree[1] and isinstance(tree[1][0], str) else 'x'
        atoms, refs = walk(tree, names)
        samples.append((it.cls, ver, atoms, refs, xml_props(x)))
    print('#', desc, len(samples), 'objects', file=sys.stderr)
    return samples


MIN_OWN = 8          # a format version gets its own path only with at least this many objects


def scalar_candidates(data):
    """data: [(atoms, value)] with >= 2 distinct values -> {path: (mapping, agreement)}"""
    common = set.intersection(*(set(a) for a, _ in data))
    res = {}
    for p in common:
        cnt = collections.defaultdict(collections.Counter)
        for a, v in data:
            cnt[a[p]][v] += 1
        mapping = {t: c.most_common(1)[0][0] for t, c in cnt.items()}
        if len(set(mapping.values())) < 2:
            continue
        # a usable code table is simple: values stored as is, strings stored as is, or a few codes 1:1 with values.
        # (otherwise a per-object GUID would "explain" any property)
        simple = all(t == v for t, v in mapping.items()) or all(t[:1] == '"' and unq(t) == v for t, v in mapping.items())             or all(t[:1] == '"' and unq(t).split('_')[0] == v for t, v in mapping.items())             or (len(mapping) <= 12 and len(mapping) == len(set(mapping.values())))
        if not simple:
            continue
        agree = sum(1 for a, v in data if mapping[a[p]] == v) / len(data)
        if agree >= 0.97:
            res[p] = (mapping, agree)
    return res


def ref_candidates(data, kind):
    """data: [(refs, value)] with at least one non-empty value -> {path: agreement}"""
    common = set.intersection(*(set(r) for r, _ in data))
    res = {}
    for p in common:
        if any(r[p][0] != kind for r, _ in data):
            continue
        agree = sum(1 for r, v in data if r[p][1] == v) / len(data)
        if agree >= 0.97:
            res[p] = agree
    return res


def prop_kind(values):
    kinds = {k for k, _ in values} - {'empty'}
    if len(kinds) > 1:
        return None
    return kinds.pop() if kinds else None


def normalize(kind, item):
    k, v = item
    if k == 'empty':
        return () if kind == 'list' else None if kind in ('ref', 'method') else ''
    return v


def learn(samples):
    groups = collections.defaultdict(list)
    for cls, ver, atoms, refs, xp in samples:
        groups[(cls, ver)].append((atoms, refs, xp))
    by_class = collections.defaultdict(list)
    for (cls, ver), objs in groups.items():
        by_class[cls].append((ver, objs))
    tables = {}
    for cls, vers in sorted(by_class.items()):
        props = sorted({p for _, objs in vers for _, _, xp in objs for p in xp})
        for prop in props:
            kind = prop_kind([xp[prop] for _, objs in vers for _, _, xp in objs if prop in xp])
            if kind is None or kind in ('fields', 'characteristics'):     # composite: places in props_manual.json
                continue
            gdata = {}
            for ver, objs in vers:
                if kind == 'scalar':
                    d = [(a, normalize(kind, xp[prop])) for a, _, xp in objs if prop in xp]
                else:
                    d = [(r, normalize(kind, xp[prop])) for _, r, xp in objs if prop in xp]
                if d:
                    gdata[ver] = d
            # 1. candidates of the versions whose objects disagree enough to tell positions apart
            cands, votes = {}, collections.Counter()
            for ver, d in gdata.items():
                informative = len({v for _, v in d}) >= 2 if kind == 'scalar' else any(v for _, v in d)
                if not informative:
                    continue
                c = scalar_candidates(d) if kind == 'scalar' else ref_candidates(d, kind)
                cands[ver] = c
                weight = len(d) if kind == 'scalar' else sum(1 for _, v in d if v)
                for p in c:
                    votes[p] += weight
            if not votes:
                continue
            top = max(votes.items(), key=lambda pv: (pv[1], -len(pv[0]), [-i for i in pv[0]]))[0]
            # 2. assign: the voted path where it fits, an own path only for big enough versions
            paths, codec = {}, {}
            for ver, c in cands.items():
                if top in c:
                    p = top
                elif len(gdata[ver]) >= MIN_OWN and c:
                    p = max(c, key=lambda q: (votes[q], c[q] if kind != 'scalar' else c[q][1], -len(q)))
                else:
                    continue
                if kind == 'scalar':
                    mapping = c[p][0]
                    if any(codec.get(t, v) != v for t, v in mapping.items()):
                        continue                        # would contradict the codes learned so far
                    codec.update(mapping)
                paths[ver] = p
            if not paths:
                continue
            ctype = codec
            if kind == 'scalar':
                if all(t == v for t, v in codec.items()):
                    ctype = None                       # numbers stored as is
                elif all(t[:1] == '"' and unq(t) == v for t, v in codec.items()):
                    ctype = 'str'
                elif all(t[:1] == '"' and unq(t).split('_')[0] == v for t, v in codec.items()):
                    ctype = 'prefix'                   # "BeforeWrite_ПередЗаписью" -> BeforeWrite
            decode = lambda t: t if ctype is None else unq(t) if ctype == 'str' else unq(t).split('_')[0] if ctype == 'prefix' else ctype.get(t)
            # 3. versions without variation only confirm the voted path; where it fails, the version is refused
            refused = []
            for ver, d in gdata.items():
                if ver in paths:
                    continue
                if kind == 'scalar':
                    ok = all(top in a and decode(a[top]) == v for a, v in d)
                else:
                    ok = all(top in r and r[top] == (kind, v) for r, v in d)
                if ok:
                    paths[ver] = top
                else:
                    refused.append(ver)
            # 4. final test on every object of the learned versions: more than 0.5% of wrong values drops the property
            total = wrong = 0
            for ver, d in gdata.items():
                p = paths.get(ver)
                if p is None:
                    continue
                for x, v in d:
                    total += 1
                    if kind == 'scalar':
                        wrong += not (p in x and decode(x[p]) == v)
                    else:
                        wrong += not (p in x and x[p] == (kind, v))
            # a code table needs evidence (about three objects per code), at most 12 codes after merging versions,
            # and enum-like values only: free text (comments, URLs) is never a code table, and must not end up in the file
            if isinstance(ctype, dict) and (len(ctype) > 12 or total < 3 * len(ctype)
                                            or not all(re.match(r'^(?:[A-Za-z][A-Za-z0-9]*|-?[0-9]+)$', v) for v in ctype.values())):
                continue
            if not total or wrong / total > 0.005:
                continue
            tables.setdefault(cls, {})[prop] = {'kind': kind, 'codec': ctype if kind == 'scalar' else None,
                                               'paths': {v: list(p) for v, p in sorted(paths.items())},
                                               'default_path': list(top), 'refused_versions': sorted(refused),
                                               'checked': total, 'wrong': wrong}
    return tables


def main():
    args = sys.argv[1:]
    out = os.path.join(HERE, 'props_tables.json')
    if '--out' in args:
        i = args.index('--out'); out = args[i + 1]; del args[i:i + 2]
    cache = None
    if '--samples' in args:
        i = args.index('--samples'); cache = args[i + 1]; del args[i:i + 2]
    import pickle
    if cache and os.path.isfile(cache) and not args:
        samples = pickle.load(open(cache, 'rb'))
    else:
        samples = []
        for spec, conf in zip(args[::2], args[1::2]):
            samples += collect(spec, conf)
        if cache:
            pickle.dump(samples, open(cache, 'wb'))
    tables = learn(samples)
    json.dump(tables, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    n = sum(len(v) for v in tables.values())
    print('learned %d properties in %d classes -> %s' % (n, len(tables), out))


if __name__ == '__main__':
    main()
