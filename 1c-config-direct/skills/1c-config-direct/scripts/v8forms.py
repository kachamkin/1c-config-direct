# Layout of managed forms. The form keeps everything in <form uuid>.0 (an ordinary form is a container with "form"
# and "module" there instead):
#   {3,<form>,"<module text>",<attributes>,<parameters>,<commands>,…}
#   form       {49,<properties>…,<events>,…,<auto command bar>,N,<type uuid>,<element>…,…}
#   element    {<version>,{<id>,02023637-…},…,<kind code>,"<name>",<title>…}: its kind is the type uuid before it
#              (group, field, button, table, decoration, addition) and the code just before the name; elements
#              the platform adds by itself (context menu, command bar, extended tooltip, search additions) come
#              without a type uuid. Children sit inside the element the same way.
#   events     {N,<event uuid>,"<handler>",…[,…]}
#   data path  {K,<step>×K}: {<id>} a form attribute or its column, {0,<uuid>} a field of the configuration,
#              {<-id>} a standard attribute, {k,5bdad865-…} a column the form adds to a tabular section
#   command    {0,<uuid>} a standard command of the form or a command of the configuration,
#              {N,409b9a53-…} the form command N, {N,<uuid>} a standard command of the element with id N
#   attributes {4,N,{9,{<id>},0,"<name>",<title>,{"Pattern",…},…}…,K,<added columns>×K}, columns {5,<id>,0,"<name>",…};
#              added columns {0,<data path of the tabular section>,M,{5,<id>,0,"<name>",…}×M}
#   parameters {0,N,{0,"<name>",{"Pattern",…},<key>}…}
#   commands   {0,N,{9,{<id>,409b9a53-…},"<name>",<title>,<tooltip>,…,"<action>",…}…}
# Names of events and standard commands: form_names.json.
import collections, json, os, re
from v8cfg import text, parse_brace, unq, is_container

ID = '02023637-7868-4a5f-8576-835a76e0c9ba'
FORM_COMMAND = '409b9a53-7f7e-4178-86c1-33176c7c7a7a'
EXTRA_COLUMN = '5bdad865-f2c5-434b-8041-ba4aad3b6687'
GUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
TYPE = {'cd5394d0-7dda-4b56-8927-93ccbe967a01': 'group', '77ffcc29-7f2d-4223-b22f-19666e7250ba': 'field',
        'a9f3b1ac-f51b-431e-b102-55a69acdecad': 'button', '143c00f7-a42d-4cd7-9189-88e4467dc768': 'table',
        '3d3cb80c-508b-41fa-8a18-680cdf5f1712': 'decoration', 'c5259a1d-518a-4afd-b98d-0176027e4feb': 'addition'}
KINDS = {
    'field': {'1': 'LabelField', '2': 'InputField', '3': 'CheckBoxField', '4': 'PictureField', '5': 'RadioButtonField',
              '6': 'SpreadSheetDocumentField', '7': 'TextDocumentField', '8': 'CalendarField', '9': 'ProgressBarField',
              '10': 'TrackBarField', '11': 'ChartField', '12': 'GanttChartField', '14': 'GraphicalSchemaField',
              '15': 'HTMLDocumentField', '17': 'FormattedDocumentField'},
    'group': {'0': 'CommandBar', '1': 'Popup', '2': 'ColumnGroup', '3': 'Pages', '4': 'Page', '5': 'UsualGroup', '6': 'ButtonGroup'},
    'decoration': {'0': 'LabelDecoration', '1': 'PictureDecoration'},
    'addition': {'0': 'SearchStringAddition', '1': 'ViewStatusAddition', '2': 'SearchControlAddition'},
}
TITLE_AT = {'field': 3, 'table': 4}                  # offset of the title from the name; 1 for the others
PATH_AT = {'field': 5, 'table': 6, 'button': 4}     # offset of the data path
COMMAND_AT = 3                                       # offset of the command of a button

Element = collections.namedtuple('Element', 'kind id name title path command events children embedded')
Attribute = collections.namedtuple('Attribute', 'id name title pattern columns main fields')   # fields: dynamic list {id: name}
Command = collections.namedtuple('Command', 'id name title action')
Form = collections.namedtuple('Form', 'events attributes parameters commands elements extra_columns')
# extra_columns: {<uuid of the tabular section>: {<column id>: (name, pattern)}} — columns the form adds
_NAMES = None


def names_table():
    global _NAMES
    if _NAMES is None:
        _NAMES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'form_names.json'), encoding='utf-8'))
    return _NAMES


def multilang(v):
    """{1,N,{"ru","…"}…} -> {lang: text} (empty texts left out), or None"""
    if isinstance(v, list) and len(v) >= 2 and v[0] == '1' and isinstance(v[1], str) and v[1].isdigit():
        out = {}
        for p in v[2:2 + int(v[1])]:
            if not (isinstance(p, list) and len(p) == 2):
                return None
            if unq(p[1]):
                out[unq(p[0])] = unq(p[1]).replace('\r', '')
        return out
    return None


def _is_element(x):
    return isinstance(x, list) and len(x) > 2 and isinstance(x[1], list) and len(x[1]) == 2 and x[1][1] == ID


def _name_index(n):
    return next((i for i in range(2, 9) if i < len(n) and isinstance(n[i], str) and n[i][:1] == '"'), None)


def _events(node, out=None):
    """[(event, handler)] of an element or of the form: every list {n,<uuid>,"<handler>",…} of known events in it"""
    known = names_table()['events']
    out = [] if out is None else out
    for x in node:
        if isinstance(x, list) and not _is_element(x):
            n = int(x[0]) if x and isinstance(x[0], str) and x[0].isdigit() else 0
            if n and len(x) >= 1 + 2 * n and \
                    all(isinstance(x[1 + 2 * k], str) and GUID.match(x[1 + 2 * k]) and isinstance(x[2 + 2 * k], str) and x[2 + 2 * k][:1] == '"'
                        for k in range(n)) and any(x[1 + 2 * k] in known for k in range(n)):
                out += [(known.get(x[1 + 2 * k], x[1 + 2 * k]), unq(x[2 + 2 * k])) for k in range(n) if unq(x[2 + 2 * k])]
            else:
                _events(x, out)
    return out


def _element(node, prev):
    ni = _name_index(node)
    if ni is None:
        return None
    t = TYPE.get(prev)
    code = node[ni - 1] if isinstance(node[ni - 1], str) else ''
    if t in KINDS:
        kind = KINDS[t].get(code, '%s:%s' % (t, code))
    elif t == 'button':
        kind = 'Button'
    elif t == 'table':
        kind = 'Table'
    elif node[0] in ('3', '4', '5'):
        kind = KINDS['addition'].get(code, 'addition:' + code)
    else:
        kind = {'9': 'AutoCommandBar', '8': 'ContextMenu', '0': 'ExtendedTooltip'}.get(code, 'embedded:' + code)
    title = multilang(node[ni + TITLE_AT.get(t, 1)]) if ni + TITLE_AT.get(t, 1) < len(node) else None
    path = None
    at = PATH_AT.get(t)
    if at and ni + at < len(node):
        p = node[ni + at]
        if isinstance(p, list) and p and isinstance(p[0], str) and p[0].isdigit() and len(p) == int(p[0]) + 1 \
                and all(isinstance(s, list) for s in p[1:]):
            path = p[1:]
    command = node[ni + COMMAND_AT] if t == 'button' and ni + COMMAND_AT < len(node) else None
    return Element(kind, node[1][0], unq(node[ni]), title or {}, path, command, _events(node), [], t is None)


def _walk(node, parent_children):
    prev = None
    for x in node:
        if isinstance(x, list):
            if _is_element(x):
                el = _element(x, prev)
                if el is not None:
                    parent_children.append(el)
                    _walk(x, el.children)
                else:
                    _walk(x, parent_children)
            else:
                _walk(x, parent_children)
        prev = x if isinstance(x, str) else None


def _attributes(node):
    out = []
    for a in node[2:] if isinstance(node, list) else ():
        if not (isinstance(a, list) and len(a) > 5 and a[0] == '9'):
            continue
        cols = []
        for c in a:
            if isinstance(c, list) and len(c) > 4 and c[0] == '5' and isinstance(c[3], str) and c[3][:1] == '"':
                cols.append((c[1], unq(c[3]), c[5] if len(c) > 5 else None))
        fields = {}
        for x in a:                                  # a dynamic list: "FieldsMapItemId<k>",{"N",<id>},"FieldsMapItemName<k>",{"S","<name>"}
            if isinstance(x, list) and len(x) > 3 and x[0] == '0' and '"QueryText"' in x[:4]:
                ids = {}
                for i in range(len(x) - 1):
                    key = x[i]
                    if isinstance(key, str) and (key.startswith('"FieldsMapItem') or key.startswith('"FiledsMapItem')):
                        v = x[i + 1]
                        if isinstance(v, list) and len(v) == 2:
                            k = re.match(r'"Fi(?:el|le)dsMapItem(Id|Name)(\d+)"', key)
                            if k:
                                ids.setdefault(k.group(2), {})[k.group(1)] = unq(v[1])
                fields = {d['Id']: d['Name'] for d in ids.values() if 'Id' in d and 'Name' in d}
        out.append(Attribute(a[1][0] if isinstance(a[1], list) else a[1], unq(a[3]), multilang(a[4]) or {}, a[5],
                             cols, len(a) > 10 and a[10] == '1', fields))
    return out


def _extra_columns(node):
    """{<tabular section uuid>: {<id>: (name, pattern)}} from the tail of the attributes section"""
    out = {}
    if not isinstance(node, list) or len(node) < 2 or not node[1].isdigit():
        return out
    rest = node[2 + int(node[1]):]
    for tb in rest[1:] if rest and isinstance(rest[0], str) and rest[0].isdigit() else ():
        if not (isinstance(tb, list) and len(tb) > 2 and isinstance(tb[1], list) and tb[1] and isinstance(tb[1][-1], list)):
            continue
        last = tb[1][-1]
        ts = last[1] if len(last) == 2 and last[0] == '0' else None
        cols = {c[1]: (unq(c[3]), c[5] if len(c) > 5 else None) for c in tb[3:]
                if isinstance(c, list) and len(c) > 3 and c[0] == '5' and isinstance(c[3], str) and c[3][:1] == '"'}
        if ts:
            out.setdefault(ts, {}).update(cols)
    return out


def _parameters(node):
    return [(unq(p[1]), p[2], len(p) > 3 and p[3] == '1') for p in (node[2:] if isinstance(node, list) else ())
            if isinstance(p, list) and len(p) > 2 and isinstance(p[1], str) and p[1][:1] == '"']


def _commands(node):
    out = []
    for c in node[2:] if isinstance(node, list) else ():
        if isinstance(c, list) and len(c) > 8 and isinstance(c[1], list) and len(c[1]) == 2 and c[1][1] == FORM_COMMAND:
            action = unq(c[8]) if isinstance(c[8], str) and c[8][:1] == '"' else ''
            out.append(Command(c[1][0], unq(c[2]), multilang(c[3]) or {}, action))
    return out


def read(cfg, it):
    """Form of a managed form, or None (an ordinary form or no layout)"""
    if not cfg.src.has(it.uuid + '.0'):
        return None
    b = cfg.src.raw(it.uuid + '.0')
    if is_container(b):
        return None
    t = parse_brace(text(b))
    if not isinstance(t, list) or len(t) < 2 or not isinstance(t[1], list):
        return None
    block = t[1]
    elements = []
    _walk(block, elements)
    head = [x for x in block if not _is_element(x)]
    return Form(_events(head), _attributes(t[3]) if len(t) > 3 else [], _parameters(t[4]) if len(t) > 4 else [],
                _commands(t[5]) if len(t) > 5 else [], elements, _extra_columns(t[3]) if len(t) > 3 else {})


def walk(elements, depth=0, parent=None):
    for i, e in enumerate(elements):
        yield depth, parent, i, e
        yield from walk(e.children, depth + 1, e)


def _class_of(cfg, decoded):
    """class of the first configuration type of a decoded type list: Catalogs, Documents …, or None"""
    from v8meta import SINGULAR
    plural = {v: k for k, v in SINGULAR.items()}
    for k, v in decoded or ():
        if k == 'Type':
            m = re.match(r'([A-Za-z]+?)(Object|Ref|RecordManager|RecordSet|List|Manager|Selection|RecordKey)\.', v)
            if m and m.group(1) in plural:
                return plural[m.group(1)]
    return None


# steps of data paths that are properties of platform objects rather than standard attributes
OBJECT_STEPS = {'Documents': {'-8': 'RegisterRecords'}}
VALUE_LIST = {'0': 'Value', '1': 'Presentation', '2': 'Check', '3': 'Picture'}
VALUE_LIST_TYPE = 'ValueListType'


def data_path(cfg, form, steps, elements_by_id=None):
    """text of a data path as the XML dump writes it (Объект.Товары.Номенклатура, Список.Ref,
    Items.Список.CurrentData.Ref), or None when a step is not known"""
    from v8std import STD_IDS
    if not steps:
        return None
    if not hasattr(cfg, '_form_ftypes'):
        cfg._form_ftypes = {f.uuid: f.types for f in cfg.fields()}
    names = cfg.comp_context().names
    attrs = {a.id: a for a in form.attributes}
    s0 = steps[0]
    prefix = []
    if len(s0) == 2 and s0[1] == ID and elements_by_id:               # Items.<element>.CurrentData.<field>
        el = elements_by_id.get(s0[0])
        if el is None or not el.path or len(el.path[0]) != 1 or el.path[0][0] not in attrs:
            return None
        prefix = ['Items', el.name, 'CurrentData']
        s0 = el.path[0]
    if len(s0) != 1 or s0[0] not in attrs:
        return None
    a = attrs[s0[0]]
    out = [a.name]
    value_list = any(k == 'Type' and v == VALUE_LIST_TYPE for k, v in (cfg.decode(a.pattern) if isinstance(a.pattern, list) else []))
    cls = _class_of(cfg, cfg.decode(a.pattern) if isinstance(a.pattern, list) else [])
    cols = {c[0]: c for c in a.columns}
    in_ts = False
    ts = None
    for s in steps[1:]:
        if len(s) == 2 and s[0] == '0' and GUID.match(s[1]):            # a field of the configuration
            p = names.get(s[1])
            if p is None:
                return None
            out.append(p.split('.')[-1])
            in_ts = p.split('.')[-2:-1] == ['TabularSections']
            ts = s[1] if in_ts else None
            if p.count('.') == 1:                                       # an object (a register in RegisterRecords)
                cls = p.split('.')[0]
            elif not in_ts:
                cls = _class_of(cfg, cfg._form_ftypes.get(s[1]))
            cols = {}
        elif len(s) == 2 and s[1] == EXTRA_COLUMN:                     # a column the form adds to a tabular section
            col = form.extra_columns.get(ts, {}).get(s[0])
            if col is None:
                return None
            out.append(col[0])
        elif len(s) == 1 and s[0].isdigit() and a.fields and len(out) >= 1 and out[0] == a.name and s[0] in a.fields:
            out = [a.name] + a.fields[s[0]].split('.')                  # a field of a dynamic list: its full name
        elif len(s) == 1 and value_list and len(out) == 1 and s[0] in VALUE_LIST:
            out.append(VALUE_LIST[s[0]])
        elif len(s) == 1 and s[0].isdigit() and s[0] in cols:           # a column of a table attribute
            out.append(cols[s[0]][1])
            cols = {}
        elif len(s) == 1 and s[0].startswith('-'):                      # a standard attribute
            if in_ts and s[0] == '-2':
                out.append('LineNumber')
            else:
                nm = STD_IDS.get(cls, {}).get(s[0]) or OBJECT_STEPS.get(cls, {}).get(s[0])
                if nm is None:
                    return None
                out.append(nm)
        else:
            return None
    if prefix:                                                         # the first step names the element's attribute
        return '.'.join(prefix + out[1:])
    return '.'.join(out)


def command_text(cfg, form, ref, elements_by_id):
    """text of the command of a button as the XML dump writes it, or None"""
    if not isinstance(ref, list) or not ref:
        return None
    if ref == ['0']:
        return '0'
    if len(ref) != 2:
        return None
    n, u = ref
    std = names_table()['commands']
    it = cfg.items.get(u)
    if it is not None:                                   # a command of the configuration, or a standard one of an object
        from v8roles import xml_name
        if it.path.count('.') == 1 and it.cls != 'CommonCommands':
            name = names_table().get('object commands', {}).get('%s|%s' % (it.cls, n))
            return '%s.StandardCommand.%s' % (xml_name(it.path), name) if name else '%s:%s' % (n, u)
        return xml_name(it.path) if n == '0' else '%s:%s' % (n, u)
    if u == FORM_COMMAND:
        c = next((c for c in form.commands if c.id == n), None)
        return 'Form.Command.' + c.name if c else '%s:%s' % (n, u)
    if u in std:
        if n == '0':
            return 'Form.StandardCommand.' + std[u]
        el = elements_by_id.get(n)
        return 'Form.Item.%s.StandardCommand.%s' % (el.name, std[u]) if el else None
    return '%s:%s' % (n, u)                                            # as the XML dump writes what it does not know


EMBEDDED_TAGS = {'ContextMenu', 'AutoCommandBar', 'ExtendedTooltip'}


def xml_form(path):
    """what check compares from a Form.xml: ({id: element}, events, attributes, commands, parameters); element:
    dict(kind, name, parent, order (None for elements outside ChildItems), title, events, path, command)"""
    import xml.etree.ElementTree as ET
    LF, V8 = '{http://v8.1c.ru/8.3/xcf/logform}', '{http://v8.1c.ru/8.1/data/core}'
    tags = re.compile(r'</>|<(?:b|i|u|s|link|color|bgcolor|font|img)(?:\s[^>]*)?>')
    known = names_table()['events']

    def ml(e):
        if e is None:
            return {}
        plain = (lambda t: tags.sub('', t)) if e.get('formatted') == 'true' else (lambda t: t)
        return {i.findtext(V8 + 'lang'): plain(i.findtext(V8 + 'content')) for i in e if i.findtext(V8 + 'content')}

    def events(e):
        ev = e.find(LF + 'Events')
        return [(known.get(x.get('name'), x.get('name')), x.text or '') for x in ev] if ev is not None else []
    r = ET.parse(path).getroot()
    els = {}

    def add(c, parent, order):
        els[c.get('id')] = dict(kind=c.tag.replace(LF, ''), name=c.get('name'), parent=parent, order=order, title=ml(c.find(LF + 'Title')),
                                events=events(c), path=c.findtext(LF + 'DataPath'), command=c.findtext(LF + 'CommandName'))
        walk(c, c.get('id'))

    def walk(e, parent):
        for c in e:
            if c.get('id') is not None and c.get('name') is not None:
                add(c, parent, None)
            elif c.tag == LF + 'ChildItems':
                for k, x in enumerate(y for y in c if y.get('id') is not None):
                    add(x, parent, k)
    walk(r, None)
    sec = lambda n, tag: [x for x in (r.find(LF + n) if r.find(LF + n) is not None else []) if x.tag == LF + tag]
    return (els, events(r), [(a.get('id'), a.get('name')) for a in sec('Attributes', 'Attribute')],
            [(c.get('id'), c.get('name'), c.findtext(LF + 'Action') or '') for c in sec('Commands', 'Command')],
            [x.get('name') for x in sec('Parameters', 'Parameter')])


def path_display(cfg, form, steps, elements_by_id=None):
    """data path for the screen: as the XML dump writes it, or the form attribute and the raw steps after it"""
    t = data_path(cfg, form, steps, elements_by_id)
    if t is not None:
        return t
    attrs = {a.id: a.name for a in form.attributes}
    raw = []
    for k, s in enumerate(steps):
        if k == 0 and len(s) == 1 and s[0] in attrs:
            raw.append(attrs[s[0]])
        else:
            raw.append(':'.join(x for x in s if isinstance(x, str)))
    return '/'.join(raw)


def rows(cfg, it, f=None):
    """[(element path, kind, data path, command, events)] of a managed form, for export"""
    f = f or read(cfg, it)
    if f is None:
        return []
    by_id = {e.id: e for d, p, i, e in walk(f.elements)}
    out = []

    def go(els, prefix):
        for e in els:
            path = prefix + [e.name]
            if e.kind != 'ExtendedTooltip':
                out.append(('/'.join(path), e.kind, path_display(cfg, f, e.path, by_id) if e.path else '',
                            (command_text(cfg, f, e.command, by_id) or '') if e.kind == 'Button' else '',
                            '; '.join('%s=%s' % ev for ev in e.events)))
            go(e.children, path)
    go(f.elements, [])
    return out
