# learn_fields.py — learn where field properties (indexing, fill checking, use, master dimension ...) sit in field
# descriptions, by comparing with XML dumps. Maintenance tool: regenerates scripts/field_props.json.
#
#   py -X utf8 learn_fields.py <source> <XML dump dir> [...] [--out field_props.json]
#
# A field is stored as {<field version>,{<common version>,{2,<name block>,{"Pattern",…}},<common properties>…},<tail>…}:
# the common block (version 27) is the same for every kind of field, the tail depends on the class and the kind of the
# field (catalog attribute, tabular section attribute, register dimension …). A scalar property is learned at the place
# where the stored token maps to the XML value one to one, with at least two distinct values and >= 99.5% agreement.
import collections, json, os, sys, types
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from v8meta import unq  # noqa: E402
from v8fields import field_nodes  # noqa: E402
import cfgread  # noqa: E402

MD = '{http://v8.1c.ru/8.3/MDClasses}'
FIELD_TAGS = ('Attribute', 'Dimension', 'Resource', 'AddressingAttribute', 'AccountingFlag', 'ExtDimensionAccountingFlag')
SKIP = {'Name', 'Synonym', 'Comment', 'Type', 'ToolTip', 'Format', 'EditFormat', 'MinValue', 'MaxValue', 'FillValue',
        'ChoiceForm', 'LinkByType', 'ChoiceParameters', 'ChoiceParameterLinks', 'DocumentMap', 'RegisterRecordsMap',
        'ScheduleLink', 'BaseDimension'}
# properties whose value is a field of the configuration: learned for the place, read as a reference (codec ref)
REF_PROPS = ('AccountingFlag', 'ExtDimensionAccountingFlag', 'AddressingDimension')


def xml_fields(path, choice=False):
    """{field uuid: {property: text}} for the leaf properties of the fields of an object XML; with choice=True also
    ChoiceParameters and ChoiceParameterLinks in the form v8fields gives them"""
    out = {}
    obj = next(iter(ET.parse(path).getroot()), None)
    if obj is None:
        return out
    for e in obj.iter():
        tag = e.tag.replace(MD, '')
        if tag in FIELD_TAGS and e.get('uuid'):
            pr = e.find(MD + 'Properties')
            if pr is not None:
                props = {c.tag.replace(MD, ''): (c.text or '').strip() for c in pr if not list(c)}
                if choice:
                    from learn_props import xml_field
                    for p in REF_PROPS:                  # 'ChartOfAccounts.X.AccountingFlag.Y' -> 'ChartsOfAccounts.X.AccountingFlags.Y'
                        if props.get(p):
                            props[p] = xml_field(props[p]) or props[p]
                    cp, cl = pr.find(MD + 'ChoiceParameters'), pr.find(MD + 'ChoiceParameterLinks')
                    props['ChoiceParameters'] = [xml_parameter(i) for i in (cp if cp is not None else [])]
                    props['ChoiceParameterLinks'] = [xml_link(i) for i in (cl if cl is not None else [])]
                out[e.get('uuid')] = props
    return out


APP = '{http://v8.1c.ru/8.2/managed-application/core}'
XR = '{http://v8.1c.ru/8.3/xcf/readable}'
XSI_TYPE = '{http://www.w3.org/2001/XMLSchema-instance}type'


def xml_value(v):
    if v is None:
        return ''
    t, text = v.get(XSI_TYPE), (v.text or '').strip()
    if t == 'xs:string':
        return '"%s"' % text
    if t == 'xr:DesignTimeRef' and '.' in text:
        from learn_props import PLURAL
        head, rest = text.split('.', 1)
        return '%s.%s' % (PLURAL.get(head, head), rest)
    if t == 'v8:FixedArray':
        return '[%s]' % ', '.join(xml_value(x) for x in v)
    return text


def xml_parameter(item):
    return '%s = %s' % (item.get('name'), xml_value(item.find(APP + 'value')))


def xml_link(link):
    from learn_props import xml_field, xml_ref
    d = (link.findtext(XR + 'DataPath') or '').strip()
    path = xml_field(d) or (xml_ref(d) if '.' in d else None) or d
    return '%s = %s (%s)' % (link.findtext(XR + 'Name'), path, link.findtext(XR + 'ValueChange'))


def samples(pairs):
    for spec, conf in pairs:
        cfg, desc, _ = cfgread.open_source(spec, types.SimpleNamespace(no_sync=True, cache=None))
        for it, tree in cfg.trees():
            x = os.path.join(conf, it.cls, it.name + '.xml')
            if not os.path.isfile(x):
                continue
            xf = xml_fields(x)
            for uuid, (kind, ts, common, field) in field_nodes(tree).items():
                if uuid not in xf:
                    continue
                catoms = {k: v for k, v in enumerate(common) if isinstance(v, str) and k > 0}
                tatoms = {k: v for k, v in enumerate(field) if isinstance(v, str) and k > 0}
                yield it.cls, kind, ts, common[0], field[0], catoms, tatoms, xf[uuid]
        print('#', desc, file=sys.stderr)


def best_places(data):
    """data: [(atoms, value)] -> [(place, codec, agreement)] of the places that map tokens to values one to one equally
    well (more than one: the data cannot tell them apart), or []"""
    values = {v for _, v in data}
    if len(values) < 2:
        return []
    common = set.intersection(*(set(a) for a, _ in data))
    found = []
    for k in common:
        pairs = collections.Counter((a[k], v) for a, v in data)
        by_tok = collections.defaultdict(collections.Counter)
        for (t, v), n in pairs.items():
            by_tok[t][v] += n
        codec = {t: c.most_common(1)[0][0] for t, c in by_tok.items()}
        agree = sum(c.most_common(1)[0][1] for c in by_tok.values()) / len(data)
        if len(set(codec.values())) != len(codec) or agree < 0.995:
            continue
        identity = all(unq(t) == v or t == v for t, v in codec.items())
        codec = None if identity and all(t[:1] != '"' for t in codec) else 'str' if identity else codec
        found.append(((agree, len(by_tok)), k, codec))
    if not found:
        return []
    top = max(s for s, _, _ in found)
    return sorted((k, c, top[0]) for s, k, c in found if s == top)


def _assign(cands, order):
    """{prop: [(place, codec, agreement)]} -> {prop: (place, codec, agreement, tie)}. Properties tied over the same
    places share them out in the order of the XML (the description keeps the properties in that order); a lone tie
    takes its first place and is marked."""
    out, by_set = {}, collections.defaultdict(list)
    for p, c in cands.items():
        if len(c) == 1:
            out[p] = c[0] + (False,)
        else:
            by_set[tuple(k for k, _, _ in c)].append(p)
    for places, props in by_set.items():
        props.sort(key=lambda p: order.get(p, 1 << 30))
        for i, p in enumerate(props):
            c = {k: (k, codec, agree) for k, codec, agree in cands[p]}
            out[p] = c[places[min(i, len(places) - 1)]] + (len(props) != len(places),)
    return out


def _drop_shared(versions):
    """{version: {prop: entry}}: a place claimed by two properties of one version keeps the property that has that
    place in another version as well"""
    for v, props in versions.items():
        by_place = collections.defaultdict(list)
        for p, d in props.items():
            by_place[d['place']].append(p)
        for place, ps in by_place.items():
            if len(ps) > 1:
                elsewhere = [p for p in ps if any(o.get(p, {}).get('place') == place for w, o in versions.items() if w != v)]
                for p in ps:
                    if elsewhere and p not in elsewhere:
                        del props[p]


def learn(rows):
    common = collections.defaultdict(list)                     # common version -> rows
    tail = collections.defaultdict(list)                       # (class, kind, ts, field version) -> rows
    order = {}
    for cls, kind, ts, cver, fver, catoms, tatoms, xp in rows:
        common[cver].append((catoms, xp))
        tail[(cls, kind, 'TS' if ts else '', fver)].append((tatoms, xp))
        for i, p in enumerate(xp):
            order.setdefault(p, i)
    out = {'common': {}, 'tail': {}}

    def entry(r, n, ref=False):
        place, codec, agree, tie = r
        e = {'place': place, 'codec': 'ref' if ref else codec, 'agreement': round(agree, 5), 'n': n}
        if tie:
            e['tie'] = True
        return e
    for cver, data in sorted(common.items()):
        props = sorted({p for _, xp in data for p in xp} - SKIP)
        cands = {p: best_places([(a, xp[p]) for a, xp in data if p in xp]) for p in props}
        for p, r in _assign({p: c for p, c in cands.items() if c}, order).items():
            out['common'].setdefault(cver, {})[p] = entry(r, sum(1 for _, xp in data if p in xp))
    _drop_shared(out['common'])
    learned_common = {p for v in out['common'].values() for p in v}
    for key, data in sorted(tail.items()):
        props = sorted({p for _, xp in data for p in xp} - SKIP - learned_common)
        cands = {p: best_places([(a, xp[p]) for a, xp in data if p in xp]) for p in props}
        for p, r in _assign({p: c for p, c in cands.items() if c}, order).items():
            out['tail'].setdefault('/'.join(key[:3]), {}).setdefault(key[3], {})[p] = entry(
                r, sum(1 for _, xp in data if p in xp), p in REF_PROPS)
    for vers in out['tail'].values():
        _drop_shared(vers)
    return out


def main():
    import pickle
    args = sys.argv[1:]
    opts = {}
    for flag in ('--out', '--samples'):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    out_path = opts.get('--out', os.path.join(HERE, 'field_props.json'))
    pairs = list(zip(args[::2], args[1::2]))
    cache = opts.get('--samples')
    if cache and not pairs and os.path.isfile(cache):
        rows = pickle.load(open(cache, 'rb'))
    else:
        rows = list(samples(pairs))
        if cache:
            pickle.dump(rows, open(cache, 'wb'))
    tables = learn(rows)
    json.dump(tables, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('fields:', len(rows), '| common properties:', sum(len(v) for v in tables['common'].values()),
          '| tail groups:', len(tables['tail']))


if __name__ == '__main__':
    main()
