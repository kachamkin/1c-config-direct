# Predefined items of catalogs, charts of characteristic types, charts of accounts and charts of calculation types.
# The designer keeps them in a file of the object: <uuid>.1c (catalog), .7 (chart of characteristic types), .9 (chart
# of accounts), .2 (chart of calculation types; .1 there is the help). The file holds a value tree, for calculation
# types a value table:
#   tree    {0|1|2,{1,<columns>,<data>}}            table  {8|9,<columns>,<data>[,{0,0}]}
#   columns {N,{<id>,"<field uuid>"|"",{"Pattern",…},"",0}…}
#   data    {2,N,<position>,<column id>…,{1,K,<row>…},…}
#   row     {2,<row id>,N,<value at position 0>…,0|1[,{1,K,<child row>…}]}
# The single first row of a tree is a hidden root ("Элементы", "Характеристики", "Счета"); its reference is mostly
# the zero one, not always.
# Values: {"S",…} {"N",…} {"B",0|1}, an item {"#",ae135932-…,{1,<uuid>}}, a type {"#",f5c65050-…,{"Pattern",…}},
# a nested value table {"#",acf6192e-…,{8|9,<columns>,<data>…}} (subconto of an account, lists of calculation types).
# Column ids are the same in every configuration seen; a chart of accounts adds a column per accounting flag
# (field uuid in the column) and keeps the order in column 10000.
import collections
from v8cfg import text, parse_brace, unq

FILE = {'Catalogs': '.1c', 'ChartsOfCharacteristicTypes': '.7', 'ChartsOfAccounts': '.9', 'ChartsOfCalculationTypes': '.2'}
REF = 'ae135932-4f94-44df-92c1-c91f15a92848'
TYPES = 'f5c65050-3bbb-11d5-b988-0050bae0a95d'
TABLE = 'acf6192e-81ca-46ef-93a6-5a6968b78663'
COLUMNS = {
    'Catalogs': {'0': 'Ref', '1': 'IsFolder', '3': 'Name', '4': 'Code', '5': 'Description'},
    'ChartsOfCharacteristicTypes': {'1': 'Ref', '2': 'IsFolder', '3': 'Name', '4': 'Code', '5': 'Description', '6': 'Type'},
    'ChartsOfAccounts': {'0': 'Ref', '1': 'Name', '2': 'Code', '3': 'Description', '4': 'AccountType', '5': 'OffBalance',
                         '6': 'ExtDimensionTypes', '10000': 'Order'},
    'ChartsOfCalculationTypes': {'1': 'Ref', '2': 'Name', '3': 'Code', '4': 'Description', '5': 'ActionPeriodIsBase'},
}
# not read: column 2 of a catalog (a reference the platform fills with junk), the zero number in column 6 of a catalog
# and 7 of a chart of characteristic types, the three tables in columns 6-8 of calculation types (empty in all
# 145 items seen; the XML dump does not write them)
ACCOUNT_TYPE = {0: 'Active', 1: 'Passive', 2: 'ActivePassive'}

Item = collections.namedtuple('Item', 'uuid name code description folder props children')
Ref = collections.namedtuple('Ref', 'uuid')
Types = collections.namedtuple('Types', 'pattern')
Table = collections.namedtuple('Table', 'columns rows')       # columns {id: (field uuid, pattern)}; rows [(values, children)]


def _num(s):
    try:
        return int(s)
    except ValueError:
        return float(s)


def value(v):
    if not isinstance(v, list) or not v:
        return v
    k = unq(v[0])
    if k == 'S':
        return unq(v[1]) if len(v) > 1 else ''
    if k == 'N':
        return _num(v[1])
    if k == 'B':
        return v[1] == '1'
    if k == 'U':
        return None
    if k == '#' and len(v) > 2 and isinstance(v[2], list):
        if v[1] == REF and len(v[2]) > 1:
            return Ref(v[2][1])
        if v[1] == TYPES:
            return Types(v[2])
        if v[1] == TABLE:
            return table(v[2])
    return v


def table(node):
    """{ver,<columns>,<data>…} -> Table"""
    cols = {c[0]: (unq(c[1]), c[2]) for c in node[1][1:] if isinstance(c, list) and len(c) >= 3}
    data = node[2]
    n = int(data[1])
    pos = {int(data[2 + 2 * k]): data[3 + 2 * k] for k in range(n)}
    fixed = {}                              # a string of fixed length comes padded with spaces, as the platform gives it
    for c, (u, pat) in cols.items():
        t = pat[1] if len(pat) == 2 and isinstance(pat[1], list) else None
        if t and t[0] == '"S"' and len(t) > 2 and t[2] == '0' and t[1].isdigit():
            fixed[c] = int(t[1])
    return Table(cols, _rows(data[2 + 2 * n], pos, fixed))


def _rows(container, pos, fixed):
    out = []
    for r in container[2:] if isinstance(container, list) else ():
        if not isinstance(r, list) or len(r) < 3:
            continue
        n = int(r[2])
        vals = {}
        for k in range(n):
            c = pos.get(k, str(k))
            vals[c] = value(r[3 + k])
            if c in fixed and isinstance(vals[c], str):
                vals[c] = vals[c].ljust(fixed[c])
        kids = _rows(r[4 + n], pos, fixed) if len(r) > 4 + n and r[3 + n] == '1' else []
        out.append((vals, kids))
    return out


def raw_table(cfg, it):
    """Table of the predefined data of an object, or None"""
    suffix = FILE.get(it.cls)
    if not suffix or not cfg.src.has(it.uuid + suffix):
        return None
    t = parse_brace(text(cfg.src.raw(it.uuid + suffix)))
    if not isinstance(t, list) or len(t) < 2:
        return None
    return table(t if it.cls == 'ChartsOfCalculationTypes' else t[1])


def _flag(cfg, u):
    """name of an accounting flag (or a subconto accounting flag) by its field uuid"""
    if getattr(cfg, '_pred_flags', None) is None:
        cfg._pred_flags = {f.uuid: f.name for f in cfg.fields() if f.kind in ('AccountingFlag', 'ExtDimensionAccountingFlag')}
    return cfg._pred_flags.get(u, u)


def _cct_item(cfg, u):
    """'ChartOfCharacteristicTypes.<chart>.<item>' of a predefined characteristic type by its uuid"""
    if getattr(cfg, '_pred_cct', None) is None:
        cfg._pred_cct = {}
        for it in cfg.items.values():
            if it.cls == 'ChartsOfCharacteristicTypes':
                for depth, x in walk(items(cfg, it) or []):
                    cfg._pred_cct[x.uuid] = 'ChartOfCharacteristicTypes.%s.%s' % (it.name, x.name)
    return cfg._pred_cct.get(u, u)


def _flags(cfg, tb, vals):
    return [(_flag(cfg, tb.columns[c][0]), vals.get(c, False)) for c in sorted(tb.columns, key=int) if tb.columns[c][0]]


def _ext_dims(cfg, tb):
    """subconto of an account: [(characteristic type, turnover only, [(subconto accounting flag, on)])]"""
    if not isinstance(tb, Table):
        return []
    out = []
    for vals, _ in tb.rows:
        ref = vals.get('0')
        out.append((_cct_item(cfg, ref.uuid) if isinstance(ref, Ref) else '', vals.get('1', False), _flags(cfg, tb, vals)))
    return out


def items(cfg, it):
    """[Item] of an object, children inside; None when the object keeps no predefined data.
    props: Type (chart of characteristic types); AccountType, OffBalance, Order, AccountingFlags [(flag, on)],
    ExtDimensionTypes (chart of accounts); ActionPeriodIsBase (calculation types)"""
    tb = raw_table(cfg, it)
    if tb is None:
        return None
    cols = COLUMNS[it.cls]
    # The column of the code may keep the code type and length of an older version of the object. The XML dump gives
    # the code of a catalog in the current type and padded to the current length (a code "00001" of a column S(5) in a
    # catalog of codes S(9) comes as "00001    ", a number 1 left in a catalog of string codes as "1        "), the
    # code of a chart of characteristic types as the column holds it (seen once: "00001" in S(5), the chart has S(9))
    code_len = string_code = None
    if it.cls == 'Catalogs':
        if getattr(cfg, '_pred_trees', None) is None:
            cfg._pred_trees = {i.uuid: t for i, t in cfg.trees()}
        tree = cfg._pred_trees.get(it.uuid)
        wanted = ('CodeType', 'CodeLength', 'CodeAllowedLength')
        op = {k: v for k, v, how in cfg.properties(it, tree, only=wanted)} if tree is not None else {}
        string_code = op.get('CodeType') == 'String'
        if string_code and op.get('CodeAllowedLength') == 'Fixed' and str(op.get('CodeLength', '')).isdigit():
            code_len = int(op['CodeLength'])

    def build(rows):
        out = []
        for vals, kids in rows:
            v = {cols.get(c, c): x for c, x in vals.items()}
            ref = v.get('Ref')
            children = build(kids)
            if not isinstance(ref, Ref):
                continue
            props = collections.OrderedDict()
            if it.cls == 'ChartsOfCharacteristicTypes':
                props['Type'] = cfg.decode(v['Type'].pattern) if isinstance(v.get('Type'), Types) else []
            elif it.cls == 'ChartsOfAccounts':
                props['AccountType'] = ACCOUNT_TYPE.get(v.get('AccountType'), v.get('AccountType'))
                props['OffBalance'] = v.get('OffBalance', False)
                props['Order'] = v.get('Order', '')
                props['AccountingFlags'] = _flags(cfg, tb, vals)
                props['ExtDimensionTypes'] = _ext_dims(cfg, v.get('ExtDimensionTypes'))
            elif it.cls == 'ChartsOfCalculationTypes':
                props['ActionPeriodIsBase'] = v.get('ActionPeriodIsBase', False)
            folder = v.get('IsFolder', False) if it.cls in ('Catalogs', 'ChartsOfCharacteristicTypes') else None
            code = v.get('Code', '')
            if string_code and not isinstance(code, str):
                code = str(code)
            if code_len and isinstance(code, str):
                code = code.rstrip().ljust(code_len)
            out.append(Item(ref.uuid, v.get('Name', ''), code, v.get('Description', ''), folder, props, children))
        return out
    if it.cls == 'ChartsOfCalculationTypes':
        return build(tb.rows)
    return [x for vals, kids in tb.rows for x in build(kids)]      # a tree starts with a hidden root row


def walk(its, depth=0):
    for x in its:
        yield depth, x
        yield from walk(x.children, depth + 1)


def shown_code(x):
    return x.code.rstrip() if isinstance(x.code, str) else str(x.code)


def details(x):
    """what the class adds to name, code and description, for the screen: folder, value type, account properties"""
    from v8meta import show_type
    extra = []
    if x.folder:
        extra.append('folder')
    p = x.props
    if 'Type' in p:
        extra.append(show_type(p['Type']))
    if 'AccountType' in p:
        acc = [p['AccountType']] + (['off-balance'] if p['OffBalance'] else [])
        if p['Order'].strip() and p['Order'].strip() != shown_code(x):
            acc.append('order ' + p['Order'].strip())
        on = [f for f, v in p['AccountingFlags'] if v]
        if on:
            acc.append('flags: ' + ', '.join(on))
        extra.append(', '.join(acc))
        if p['ExtDimensionTypes']:
            subs = []
            for name, turnover, fl in p['ExtDimensionTypes']:
                on = [f for f, v in fl if v]
                notes = (['turnover only'] if turnover else []) + ([] if len(on) == len(fl) else
                                                                   ['flags: ' + ', '.join(on)] if on else ['no flags'])
                subs.append(name.split('.', 2)[-1] + (' (%s)' % '; '.join(notes) if notes else ''))
            extra.append('subconto: ' + ', '.join(subs))
    if p.get('ActionPeriodIsBase'):
        extra.append('action period is base')
    return ' | '.join(extra)


def show_item(x):
    """one line: name, code, description, then what the class adds"""
    d = details(x)
    return '%-40s %-12s %s%s' % (x.name, shown_code(x), x.description, ('  | ' + d) if d else '')


def xml_items(path):
    """[Item] from Ext/Predefined.xml of an XML dump, in the shape of items() (for check)"""
    import xml.etree.ElementTree as ET
    from v8meta import xml_type
    P = '{http://v8.1c.ru/8.3/xcf/predef}'
    XSI = '{http://www.w3.org/2001/XMLSchema-instance}type'

    def flags(e):
        return [(f.get('ref', '').split('.')[-1], f.text == 'true') for f in e.findall(P + 'Flag')] if e is not None else []

    def build(parent):
        out = []
        for x in parent.findall(P + 'Item'):
            ce = x.find(P + 'Code')
            code = (ce.text or '') if ce is not None else ''
            if ce is not None and ce.get(XSI) == 'xs:decimal':
                code = _num(code)
            props = collections.OrderedDict()
            if x.find(P + 'Type') is not None:
                props['Type'] = xml_type(x.find(P + 'Type'))
            if x.find(P + 'AccountType') is not None:
                props['AccountType'] = x.findtext(P + 'AccountType')
                props['OffBalance'] = x.findtext(P + 'OffBalance') == 'true'
                props['Order'] = x.findtext(P + 'Order') or ''
                props['AccountingFlags'] = flags(x.find(P + 'AccountingFlags'))
                ed = x.find(P + 'ExtDimensionTypes')
                props['ExtDimensionTypes'] = [(e.get('name', ''), e.findtext(P + 'Turnover') == 'true', flags(e.find(P + 'AccountingFlags')))
                                              for e in (ed.findall(P + 'ExtDimensionType') if ed is not None else [])]
            if x.find(P + 'ActionPeriodIsBase') is not None:
                props['ActionPeriodIsBase'] = x.findtext(P + 'ActionPeriodIsBase') == 'true'
            folder = x.findtext(P + 'IsFolder')
            ch = x.find(P + 'ChildItems')
            out.append(Item(x.get('id'), x.findtext(P + 'Name') or '', code, x.findtext(P + 'Description') or '',
                            None if folder is None else folder == 'true', props, build(ch) if ch is not None else []))
        return out
    return build(ET.parse(path).getroot())


def flat(its):
    """{uuid: (parent uuid, position among siblings, item)}"""
    out = {}

    def go(xs, parent):
        for i, x in enumerate(xs):
            out[x.uuid] = (parent, i, x)
            go(x.children, x.uuid)
    go(its, '')
    return out
