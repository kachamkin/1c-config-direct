# Layout of ordinary forms. The form is a container in <form uuid>.0 with the streams "form" and "module"; the XML
# dump keeps that container as it is (Form.bin), so there is no readable dump to check against: the names of control
# types come from the default names the designer gives (Надпись12, ПолеВвода3 …), the names of events from the default
# names of handlers (<control><event>), and every handler must be a procedure of the module.
#   form stream {27,<dialog>,<attributes and bindings>,<form events>,…}
#   dialog      {16|18,{<title>,…},<main panel>,<width>,<height>,…}: the size of the form is after the panel
#   panel       {09ccdc77-…,{1,{<properties, pages>…}},{N,<control>×N},…}
#   control     {<type uuid>,<id>,{<properties>…},{8,<left>,<top>,<right>,<bottom>,…},{14,"<name>",…},…}; a panel
#               inside keeps its controls the same way
#   events      {N,{<code>,e1692cc2-…,{3,"<handler>",…}}…} — of a control (in its properties) and of the form
#   attributes  {{<id of the main attribute>},<next id>,{K,{{<id>},0,0,1,"<name>",{"Pattern",…}}…},
#                {M,{<control id>,<data path>}…}}; older forms have one 0 less before the name
#   form events two blocks after it: of the object (8000x: ПередЗаписью, ПослеЗаписи … — by the kind of form) and of
#               the form (7000x: ПередОткрытием, ПриОткрытии, ОбработкаВыбора …)
#   data path   {K,<step>×K} as in managed forms: {<id>} an attribute of the form, {0,<uuid>} a field, {-k} standard
#   command bar {5,<bar uuid>,…,N,{7,<button uuid>,1,<kind>,<action>,<…>,<title>,<tooltip>,…}…} in its properties;
#               kind e1692cc2-… a handler {3,"<handler>",…}, fbe38877-… a standard action {6,<source>,<group>,<code>,…},
#               abde0c9a-… a separator (9d0a2e40-…) or a submenu with its items in a bar inside, c93a51ed-… a standard
#               submenu; the names of buttons in a list of their own: <button uuid>,{8,"<name>",…,<bar uuid>,…}
#   pages       of a panel in its properties: {1,K,{<ver>,<title>,{…},-1,1,1,"<name>",…}×K}; the main panel has one
#               at least; the page of a control is in its position block: {8,<l>,<t>,<r>,<b>,1,<anchors>…,<4 counted
#               lists>,<v0>,<v1>,<page>,…}
#   table field columns {N,{<kind>,…{8,{<ver>,<title>,…,"<name>",…,<Pattern>,…,<cell type>,{<cell>,…},…},
#               <data>,<check box data>,<picture data>}}}×N} ({-1}: none); the cell control is a #base64 value
#               storage — 2 bytes, a 16-byte uuid and raw deflate of its properties, events among them
#   current row a data path {-2},{<id of a table field>},{0},<steps>… is ЭлементыФормы.<table>.ТекущиеДанные.<field>
#   other steps {-8} the records of a document (Движения), then {0,<register>}; {k,<uuid>} the ext dimension k+1 of
#               an accounting register (Дт, Кт); {-60001} the filter of a list, {0,<field>} its item, {-2} Значение,
#               {-3} Использование; {<k>} after an attribute of a platform type — a property of it (ПостроительОтчета:
#               0 Отбор …); {0,b9754f01-…} КомпоновщикНастроек of a report object
import base64, collections, json, os, re, zlib
from v8cfg import text, parse_brace, unq, inflate, is_container, container_entries

GUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
EVENT = 'e1692cc2-605b-4535-84dd-28440238746c'
PANEL = '09ccdc77-ea1a-4a6d-ab1c-3435eada2433'
TYPES = {
    '0fc7e20d-f241-460c-bdf4-5ad88e5474a5': 'Надпись', '381ed624-9217-4e63-85db-c4c3cb87daae': 'ПолеВвода',
    'e69bf21d-97b2-4f37-86db-675aea9ec2cb': 'КоманднаяПанель', 'ea83fe3a-ac3c-4cce-8045-3dddf35b28b1': 'ТабличноеПоле',
    '35af3d93-d7c7-4a2e-a8eb-bac87a1a3f26': 'Флажок', '90db814a-c75f-4b54-bc96-df62e554d67d': 'РамкаГруппы',
    '6ff79819-710e-4145-97cd-1618da79e3e2': 'Кнопка', PANEL: 'Панель', '64483e7f-3833-48e2-8c75-2c31aac49f6e': 'ПолеВыбора',
    '782e569a-79a7-4a4f-a936-b48d013936ec': 'Переключатель', '151ef23e-6bb2-4681-83d0-35bc2217230c': 'ПолеКартинки',
    '236a17b3-7f44-46d9-a907-75f9cdc61ab5': 'ПолеТабличногоДокумента', '36e52348-5d60-4770-8e89-a16ed50a2006': 'Разделитель',
    'd92a805c-98ae-4750-9158-d9ce7cec2f20': 'ПолеHTMLДокумента', '19f8b798-314e-4b4e-8121-905b2a7a03f5': 'ПолеСписка',
    '14c4a229-bfc3-42fe-9ce1-2da049fd0109': 'ПолеТекстовогоДокумента', 'a8b97779-1a4b-4059-b09c-807f86d2a461': 'Диаграмма',
    'b1db1f86-abbb-4cf0-8852-fe6ae21650c2': 'Индикатор', 'e3c063d8-ef92-41be-9c89-b70290b5368b': 'ПолеКалендаря',
    '42248403-7748-49da-b782-e4438fd7bff3': 'ПолеГрафическойСхемы', '6c06cd5d-8481-4b6f-a90a-7a97a8bb8bef': 'ПолосаРегулирования',
    'a26da99e-184a-4823-b0d6-62816d38dc4e': 'СводнаяДиаграмма', 'e5fdc112-5c84-4a16-9728-72b85692b6e2': 'ДиаграммаГанта',
}

Control = collections.namedtuple('Control', 'kind id name rect title events children buttons page pages columns')
# kind: handler (action is a procedure of the module), standard (source: 0 the form, 4294967295 the source of the
# bar, else the id of a control), submenu, standard submenu, separator; depth: of submenus
Button = collections.namedtuple('Button', 'name title kind action depth source')
# steps, check, picture: data paths from the data of the table (Данные, ДанныеФлажка, ДанныеКартинки), [] if none
Column = collections.namedtuple('Column', 'name title kind steps check picture events')
OrdinaryForm = collections.namedtuple('OrdinaryForm', 'title size attributes bindings events controls module pages')
# columns of a table field: of a tabular section or a value table, of a list, and two more kinds
COLUMNS = {'c2cf1953-2796-4fe2-b78c-ff84140b124e', '48a6ebc3-fcc8-4f8f-b399-459fb32aa46b',
           '737535a4-21e6-4971-8513-3e3173a9fedd', 'fbacf851-e6ff-4107-9e08-4302dda1d14d'}
BUTTON_KINDS = {EVENT: 'handler', 'fbe38877-b914-4fd5-8540-07dde06ba2e1': 'standard',
                'c93a51ed-b2d1-47f1-948d-38373f8710af': 'standard submenu', 'abde0c9a-18a6-4e0c-bbaa-af26b911b3e6': 'submenu'}
SEPARATOR = '9d0a2e40-b978-11d4-84b6-008048da06df'
_NAMES = None


def names_table():
    global _NAMES
    if _NAMES is None:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ordform_names.json')
        _NAMES = json.load(open(p, encoding='utf-8')) if os.path.isfile(p) else {'events': {}, 'form events': {}}
    return _NAMES


def _is_control(x):
    return isinstance(x, list) and len(x) >= 4 and isinstance(x[0], str) and GUID.match(x[0]) is not None \
        and isinstance(x[1], str) and x[1].isdigit() and any(isinstance(y, list) and y and y[0] == '14' for y in x[2:8])


def multilang(v):
    if isinstance(v, list) and len(v) >= 2 and v[0] == '1' and isinstance(v[1], str) and v[1].isdigit():
        out = {}
        for p in v[2:2 + int(v[1])]:
            if isinstance(p, list) and len(p) == 2 and unq(p[1]):
                out[unq(p[0])] = unq(p[1]).replace('\r', '')
        return out
    return None


def event_entries(node, out=None, top=True):
    """[(code, handler)]: entries {<code>,e1692cc2-…,{3,"<handler>",…}} inside a node, not inside nested controls"""
    out = [] if out is None else out
    for x in node if isinstance(node, list) else ():
        if isinstance(x, list):
            if _is_control(x) and not top:
                continue
            if len(x) >= 3 and isinstance(x[0], str) and x[0].isdigit() and x[1] == EVENT and isinstance(x[2], list) \
                    and len(x[2]) > 1 and isinstance(x[2][1], str) and x[2][1][:1] == '"':
                out.append((x[0], unq(x[2][1])))
            else:
                event_entries(x, out, False)
    return out


def _title(props):
    """the first texts in languages among the properties: the caption of a label, a check box, a button, a frame"""
    def find(n, depth=0):
        for x in n if isinstance(n, list) else ():
            t = multilang(x)
            if t:
                return t
            if isinstance(x, list) and depth < 4 and not _is_control(x):
                r = find(x, depth + 1)
                if r:
                    return r
        return None
    return find(props) or {}


def _button_names(node, out=None):
    """{<button uuid>: name}: pairs <uuid>,{8,"<name>",…} anywhere in the form stream"""
    out = {} if out is None else out
    if isinstance(node, list):
        for i in range(len(node) - 1):
            a, b = node[i], node[i + 1]
            if isinstance(a, str) and GUID.match(a) and isinstance(b, list) and len(b) > 1 and b[0] == '8' \
                    and isinstance(b[1], str) and b[1][:1] == '"':
                out[a] = unq(b[1])
        for x in node:
            if isinstance(x, list):
                _button_names(x, out)
    return out


def _buttons(props, names):
    """buttons of a command bar in its properties; the items of a submenu follow it one level deeper"""
    out = []

    def bars(n, depth=0):
        for x in n if isinstance(n, list) else ():
            if isinstance(x, list):
                if len(x) > 4 and x[0] == '5' and isinstance(x[1], str) and GUID.match(x[1]):
                    yield x
                elif depth < 6 and not _is_control(x):
                    yield from bars(x, depth + 1)

    def items(bar, depth):
        for b in bar[5:]:
            if isinstance(b, list) and len(b) > 4 and b[0] == '7' and isinstance(b[1], str) and GUID.match(b[1]):
                a = b[4] if isinstance(b[4], list) else []
                kind = BUTTON_KINDS.get(b[3], '')
                if kind == 'submenu' and len(a) > 1 and a[1] == SEPARATOR:
                    kind = 'separator'
                action = unq(a[1]) if kind == 'handler' and len(a) > 1 and isinstance(a[1], str) and a[1][:1] == '"' else ''
                source = a[1] if kind == 'standard' and len(a) > 1 and isinstance(a[1], str) else ''
                title = multilang(b[6]) if len(b) > 6 else None
                out.append(Button(names.get(b[1], ''), title or {}, kind, action, depth, source))
                for sub in bars(b[5:]):
                    items(sub, depth + 1)
    for bar in bars(props):
        items(bar, 0)
        break
    return out


def _pages(props):
    """[(name, title)] of the pages of a panel, from its properties {1,{…,{1,K,<page>×K},…}}; None if not found"""
    body = props[1] if isinstance(props, list) and len(props) > 1 and isinstance(props[1], list) else []
    for x in body:
        if isinstance(x, list) and len(x) > 2 and x[0] == '1' and isinstance(x[1], str) and x[1].isdigit() \
                and int(x[1]) == len(x) - 2 and all(isinstance(q, list) and len(q) > 6 and isinstance(q[0], str) and q[0].isdigit()
                                                     and isinstance(q[6], str) and q[6][:1] == '"' for q in x[2:]):
            return [(unq(q[6]), multilang(q[1]) or {}) for q in x[2:]]
    return None


def _page(pos):
    """the index of the page of a control from its position block, or None"""
    i = 6
    while i < len(pos) and isinstance(pos[i], list):
        i += 1
    for _ in range(4):
        if i >= len(pos) or not (isinstance(pos[i], str) and pos[i].isdigit()):
            return None
        i += 1 + int(pos[i])
    return int(pos[i + 2]) if i + 2 < len(pos) and isinstance(pos[i + 2], str) and pos[i + 2].isdigit() else None


def value_storage(chunks):
    """the brace tree kept in a #base64 value storage: 2 bytes, a 16-byte uuid, then raw deflate of the text"""
    try:
        raw = base64.b64decode(''.join(c for c in chunks if isinstance(c, str))[len('#base64:'):])
        out = zlib.decompress(raw[18:], -15)
    except Exception:
        return None
    i = out.find(b'\xef\xbb\xbf{')
    i = i + 3 if i >= 0 else out.find(b'{')
    return parse_brace(text(out[i:])) if i >= 0 else None


def _columns(props):
    """[Column] of a table field from its properties"""
    def find(n, depth=0):
        for x in n if isinstance(n, list) else ():
            if isinstance(x, list):
                if len(x) > 1 and isinstance(x[0], str) and x[0].isdigit() and int(x[0]) == len(x) - 1 \
                        and all(isinstance(c, list) and c and c[0] in COLUMNS for c in x[1:]):
                    return x[1:]
                if depth < 5 and not _is_control(x):
                    r = find(x, depth + 1)
                    if r is not None:
                        return r
        return None
    out = []
    ev = names_table()['events']
    def parts(c):
        """the column block {8,<big>,<data>…}: <big> starts with a version and a title in languages"""
        node = c
        for _ in range(4):
            for i, x in enumerate(node[1:], 1):
                if isinstance(x, list) and len(x) > 1 and x[0] == '8' and isinstance(x[1], list) and len(x[1]) > 1 \
                        and isinstance(x[1][0], str) and x[1][0].isdigit() and isinstance(x[1][1], list) and x[1][1][:1] == ['1']:
                    return x, node[i + 1:i + 4]
            node = node[1] if len(node) > 1 and isinstance(node[1], list) else None
            if node is None:
                break
        return [], []
    for c in find(props) or ():
        inner, named = parts(c)
        big = inner[1] if len(inner) > 1 and isinstance(inner[1], list) else []
        name = next((unq(v) for v in big[2:] if isinstance(v, str) and v[:1] == '"' and len(v) > 2), '')
        kind = next((TYPES[v] for v in big if isinstance(v, str) and v in TYPES), '')
        events = []
        for v in big:
            chunks = v if isinstance(v, list) and v and isinstance(v[0], str) and v[0].startswith('#base64:') else \
                v[0] if isinstance(v, list) and v and isinstance(v[0], list) and v[0] and isinstance(v[0][0], str) \
                and v[0][0].startswith('#base64:') else None
            if chunks:
                tree = value_storage(chunks)
                events = [(ev.get('%s|%s' % (kind, code), code), h) for code, h in event_entries(tree or [])]
                break
        steps = [[x] if isinstance(x, list) and x and x != ['-1'] else [] for x in (inner[2:5] + [None] * 3)[:3]]
        for k, v in enumerate(named[:3]):          # the data named by a string: {…,{8,…},"<data>","<check>","<picture>"}
            if not steps[k] and isinstance(v, str) and v[:1] == '"' and unq(v):
                steps[k] = [[v]]
        out.append(Column(name, (multilang(big[1]) if len(big) > 1 else None) or {}, kind, steps[0], steps[1], steps[2], events))
    return out


def _controls(node, out, names=None):
    for x in node if isinstance(node, list) else ():
        if isinstance(x, list):
            if _is_control(x):
                kind = TYPES.get(x[0], x[0])
                name = next(unq(y[1]) for y in x[2:8] if isinstance(y, list) and y and y[0] == '14')
                pos = next((y for y in x[2:8] if isinstance(y, list) and y and y[0] == '8'), None)
                rect = tuple(int(v) for v in pos[1:5]) if pos and all(isinstance(v, str) and v.lstrip('-').isdigit() for v in pos[1:5]) else None
                ev = names_table()['events']
                events = [(ev.get('%s|%s' % (kind, c), c), h) for c, h in event_entries(x)]
                title = _title(x[2]) if kind in ('Надпись', 'Флажок', 'Кнопка', 'РамкаГруппы', 'Переключатель') else {}
                buttons = _buttons(x[2], names or {}) if kind == 'КоманднаяПанель' else []
                c = Control(kind, x[1], name, rect, title, events, [], buttons, _page(pos) if pos else None,
                            _pages(x[2]) if kind == 'Панель' else None, _columns(x[2]) if kind == 'ТабличноеПоле' else [])
                out.append(c)
                _controls(x[2:], c.children, names)
            else:
                _controls(x, out, names)


def read(cfg, it):
    """OrdinaryForm of an ordinary form, or None"""
    if not cfg.src.has(it.uuid + '.0'):
        return None
    b = cfg.src.raw(it.uuid + '.0')
    if not is_container(b):
        return None
    ents = {n: inflate(d) for n, d in container_entries(b)}
    if 'form' not in ents:
        return None
    t = parse_brace(text(ents['form']))
    dialog = t[1] if len(t) > 1 and isinstance(t[1], list) else []
    head = dialog[1] if len(dialog) > 1 and isinstance(dialog[1], list) else []
    title = multilang(head[0]) if head else None
    size = tuple(int(v) for v in dialog[3:5]) if len(dialog) > 4 and all(isinstance(v, str) and v.isdigit() for v in dialog[3:5]) else None
    controls = []
    _controls(dialog[2:] if len(dialog) > 2 else [], controls, _button_names(t))
    attributes, bindings = [], {}
    sec = t[2] if len(t) > 2 and isinstance(t[2], list) else []
    main = sec[0][0] if sec and isinstance(sec[0], list) and sec[0] else None
    if len(sec) > 2 and isinstance(sec[2], list):
        for a in sec[2][1:]:                    # {{<id>},0,0,<main>,"<name>",<Pattern>}; older forms one 0 less
            k = next((i for i in range(1, min(len(a), 6)) if isinstance(a[i], str) and a[i][:1] == '"'), None) \
                if isinstance(a, list) and a and isinstance(a[0], list) else None
            if k is not None:
                aid = a[0][0] if a[0] else ''
                attributes.append((aid, unq(a[k]), a[k + 1] if k + 1 < len(a) else None, aid == main))
    if len(sec) > 3 and isinstance(sec[3], list):
        for bnd in sec[3][1:]:
            if isinstance(bnd, list) and len(bnd) == 2 and isinstance(bnd[1], list) and bnd[1] and bnd[1][0].isdigit():
                bindings[bnd[0]] = bnd[1][1:]
    fev = names_table()['form events']
    owner = it.path.split('.')[0]
    events = [(fev.get('%s|%s' % (owner, c)) or fev.get(c, c), h) for c, h in event_entries(t[3:5])] if len(t) > 3 else []
    # the list events of a table field (10000+) are numbered by the class of its list
    from v8forms import _class_of
    ev, at = names_table()['events'], {a[0]: a for a in attributes}
    for d, p, c in walk(controls):
        if c.kind == 'ТабличноеПоле' and any(code.isdigit() for code, h in c.events):
            st = bindings.get(c.id) or []
            a = at.get(st[0][0]) if len(st) == 1 and st[0] else None
            kl = _class_of(cfg, cfg.decode(a[2])) if a and isinstance(a[2], list) else None
            c.events[:] = [(ev.get('ТабличноеПоле|%s|%s' % (kl, code), code) if code.isdigit() else code, h)
                           for code, h in c.events]
    main_panel = dialog[2] if len(dialog) > 2 and isinstance(dialog[2], list) and len(dialog[2]) > 1 else []
    return OrdinaryForm(title or {}, size, attributes, bindings, events, controls, text(ents.get('module', b'')),
                        _pages(main_panel[1]) if main_panel else None)


def walk(controls, depth=0, parent=None):
    for c in controls:
        yield depth, parent, c
        yield from walk(c.children, depth + 1, c)


EXT_DIM_STEPS = {'1ab44b24-3315-40a9-b495-f1f1227ac205': 'СубконтоДт', 'f77758c9-9fcd-490f-9bbd-1e446541f536': 'СубконтоКт',
                 '91162600-3161-4326-89a0-4a7cecd5092a': 'Субконто'}
LIST_FILTER, FILTER_ITEM = '-60001', {'-2': 'Значение', '-3': 'Использование'}
CORR_SIDES = {'2': 'Дт', '3': 'Кт'}                    # {2|3,<field>}: a side of a non-balance field of a register
CORR_ACCOUNTS = {'-6': 'СчетДт', '-7': 'СчетКт'}        # of a correspondent accounting register
SETTINGS_COMPOSER = 'b9754f01-29e9-11d6-a3c7-0050bae0a776'          # КомпоновщикНастроек of a report object
# properties of platform objects by their places: <type>:<place>[:<place>…] -> name, as data paths of controls and
# columns reach them (a column of a table on ПостроительОтчета.Отбор is a property of a filter item:
# ReportBuilder:0:<place>). These are from the names of the controls; ordform_names.json ("platform") adds those
# learned from the default names of columns and controls, which the designer gives after the properties.
PLATFORM_PROPS = {'ReportBuilder:0': 'Отбор', 'ReportBuilder:1': 'ДоступныеПоля', 'ReportBuilder:2': 'Порядок',
                  'ReportBuilder:3': 'ВыбранныеПоля', 'ReportBuilder:4': 'ИзмеренияСтроки', 'ReportBuilder:5': 'ИзмеренияКолонки',
                  'SettingsComposer:0': 'Настройки', 'SettingsComposer:0:1': 'Отбор', 'SettingsComposer:0:3': 'Порядок',
                  'SettingsComposer:0:4': 'УсловноеОформление',
                  # a value list as in managed forms (Form.xml: 0 Value, 1 Presentation, 2 Check, 3 Picture)
                  'ValueListType:0': 'Значение', 'ValueListType:1': 'Представление', 'ValueListType:2': 'Пометка',
                  'ValueListType:3': 'Картинка'}
PROP_TYPE = {}                                                      # a property that is a known type of its own
JOURNAL_COLUMNS = '5aee69df-0513-4c6c-9815-103102471712'


def _journal_column(cfg, uuid):
    """name of a column of a document journal by its uuid (the configuration names do not hold them), or None"""
    if not hasattr(cfg, '_journal_columns'):
        cfg._journal_columns = {}
        for it in cfg.items.values():
            if it.cls == 'DocumentJournals' and '.' not in it.path.split('.', 1)[1] and cfg.src.has(it.uuid):
                t = text(cfg.src.raw(it.uuid))
                i = t.find(JOURNAL_COLUMNS)
                for u, n in re.findall(r'\{\d+,0,([0-9a-f-]{36})\},"([^"]+)"', t[i:] if i >= 0 else ''):
                    cfg._journal_columns[u] = n
    return cfg._journal_columns.get(uuid)


def _platform_chain(decoded):
    """the start of a chain of places: the name of a platform type (ReportBuilder …) when it is the only type"""
    return decoded[0][1] if len(decoded) == 1 and decoded[0][0] == 'Type' and '.' not in decoded[0][1] else None


def data_path(cfg, form, steps, partial=False, unknown=None):
    """the Data of a control as the designer shows it: a field of the main attribute by its name (Организация),
    another attribute with its path (Отбор.Склад); None when a step is not known — or, partial, the known part with
    #<step> for the rest. unknown: a list to get (<chain of places>, <index of the step>) of a property of a platform
    object that is not known"""
    from v8std import STD_IDS, STD_TS, _ru
    from v8forms import _class_of
    if not steps:
        return None
    raw = lambda rest: ['#' + ':'.join(x for x in st if isinstance(x, str)) for st in rest]
    names = cfg.comp_context().names
    attrs = {a[0]: a for a in form.attributes}
    s0 = steps[0]
    if s0 == ['-2'] and len(steps) > 2 and len(steps[1]) == 1 and steps[2] == ['0']:
        table = next((c for d, p, c in walk(form.controls) if c.id == steps[1][0]), None)
        base = form.bindings.get(table.id) if table else None
        if not base:
            return '.'.join(raw(steps)) if partial else None
        rel = ''
        if len(steps) > 3:
            whole, b = data_path(cfg, form, base + steps[3:], partial, unknown), data_path(cfg, form, base, partial)
            if whole is None:
                return None
            rel = '.' + (whole[len(b) + 1:] if b and whole.startswith(b + '.') else whole)
        return 'ЭлементыФормы.%s.ТекущиеДанные%s' % (table.name, rel)
    if len(s0) != 1 or s0[0] not in attrs:
        return '.'.join(raw(steps)) if partial else None
    a = attrs[s0[0]]
    out = [] if a[3] else [a[1]]
    decoded = cfg.decode(a[2]) if isinstance(a[2], list) else []
    cls = _class_of(cfg, decoded)
    chain = _platform_chain(decoded)
    learned = names_table().get('platform', {})
    in_ts, mode, std_ts = False, None, None
    if not hasattr(cfg, '_form_ftypes'):
        cfg._form_ftypes = {f.uuid: f.types for f in cfg.fields()}
    for i, st in enumerate(steps[1:]):
        step = None
        if chain and len(st) == 1 and st[0].isdigit():
            key = chain + ':' + st[0]
            step = PLATFORM_PROPS.get(key) or learned.get(key)
            if step is None and unknown is not None:
                unknown.append((key, i + 1))
            chain = PROP_TYPE.get(key, key)
        elif chain and len(st) == 1 and st[0][:1] == '"' and unq(st[0]):         # a column of a value table by its name
            step, chain = unq(st[0]), None
        elif mode == 'filter item' and len(st) == 1:
            step, mode = FILTER_ITEM.get(st[0]), None
        elif len(st) == 2 and st[0] == '0' and st[1] == SETTINGS_COMPOSER:
            step, chain = 'КомпоновщикНастроек', 'SettingsComposer'
        elif len(st) == 2 and st[1] in EXT_DIM_STEPS and st[0].isdigit():
            step = '%s%d' % (EXT_DIM_STEPS[st[1]], int(st[0]) + 1)
        elif len(st) == 2 and st[0] in CORR_SIDES and cls == 'AccountingRegisters' and names.get(st[1]):
            step = names[st[1]].split('.')[-1] + CORR_SIDES[st[0]]
        elif len(st) == 2 and st[0] == '0' and GUID.match(st[1]):
            p = names.get(st[1])
            if p is None:
                step = _journal_column(cfg, st[1]) if cls == 'DocumentJournals' else None
            else:
                step = p.split('.')[-1]
                in_ts = p.split('.')[-2:-1] == ['TabularSections']
                ft = cfg._form_ftypes.get(st[1]) or []
                chain = _platform_chain(ft)
                if p.count('.') == 1:
                    cls = p.split('.')[0]
                elif not in_ts and mode != 'filter':
                    cls = _class_of(cfg, ft)
            if mode == 'filter':
                mode = 'filter item'
        elif len(st) == 1 and st[0] == LIST_FILTER:
            step, mode = 'Отбор', 'filter'
        elif len(st) == 1 and st[0] == '-8' and cls == 'Documents':
            step = 'Движения'
        elif len(st) == 1 and std_ts is None and st[0] in STD_TS.get(cls, {}):
            name, ru, std_ts = STD_TS[cls][st[0]]
            step = ru
        elif len(st) == 1 and std_ts is not None and st[0] in std_ts:
            step = _ru(cls, std_ts[st[0]])
        elif len(st) == 1 and st[0].startswith('-'):
            nm = 'LineNumber' if in_ts and st[0] == '-2' else STD_IDS.get(cls, {}).get(st[0])
            step = _ru(cls, nm) if nm else CORR_ACCOUNTS.get(st[0]) if cls == 'AccountingRegisters' else None
            if mode == 'filter':
                mode = 'filter item'
        if step is None:
            if not partial:
                return None
            out += raw(steps[1 + i:])
            break
        out.append(step)
    return '.'.join(out) if out else (a[1] if not a[3] else '')


def column_path(cfg, form, table_steps, col, which='steps', partial=False):
    """(a data of a column as the designer shows it — from the data of its table —, the whole path), or (None, None);
    which: steps (Данные), check (ДанныеФлажка), picture (ДанныеКартинки)"""
    steps = getattr(col, which)
    if not steps:
        return None, None
    if not table_steps:                     # a table without data (filled by the module): what the column names alone
        st = steps[0] if len(steps) == 1 else []
        n = unq(st[0]) if len(st) == 1 and st[0][:1] == '"' else \
            cfg.comp_context().names.get(st[1], '').split('.')[-1] if len(st) == 2 and st[0] == '0' else ''
        return (n, n) if n else (None, None)
    base = data_path(cfg, form, table_steps, partial)
    if len(steps) == 1 and len(steps[0]) == 1 and steps[0][0][:1] == '"':          # named by a string
        return unq(steps[0][0]), ((base + '.') if base else '') + unq(steps[0][0]) if base is not None else None
    whole = data_path(cfg, form, table_steps + steps, partial)
    if whole is None:
        return None, None
    return (whole[len(base) + 1:] if base and whole.startswith(base + '.') else whole), whole


PROC = re.compile(r'(?im)^\s*(?:Процедура|Функция|Procedure|Function)\s+([A-Za-zА-Яа-яЁё_0-9]+)\s*\(')
OWN_REF = re.compile(r'(?<![.\w])ЭлементыФормы\.([A-Za-zА-Яа-яЁё_0-9]+)')


def rows(cfg, it, f=None):
    """[(control path, kind, data path, actions, events)] of an ordinary form, for export"""
    f = f or read(cfg, it)
    if f is None:
        return []
    out = []

    def go(cs, prefix):
        for c in cs:
            path = prefix + [c.name]
            steps = f.bindings.get(c.id)
            out.append(('/'.join(path), c.kind, data_path(cfg, f, steps, True) or '' if steps else '',
                        '; '.join('%s=%s' % (b.name, b.action) for b in c.buttons if b.action),
                        '; '.join('%s=%s' % ev for ev in c.events)))
            for col in c.columns:
                rel, whole = column_path(cfg, f, steps, col, 'steps', True)
                out.append(('/'.join(path + [col.name]), 'Колонка', whole or '' if col.steps else '', '',
                            '; '.join('%s=%s' % ev for ev in col.events)))
            go(c.children, path)
    go(f.controls, [])
    return out


def consistency(f, stream_text, cfg=None):
    """what a check can say about an ordinary form without a dump: Counter of results; with cfg, the data of controls
    and columns too"""
    res = collections.Counter()
    procs = set(PROC.findall(f.module))
    names = set()
    for d, p, c in walk(f.controls):
        res['controls'] += 1
        res['kind known' if not GUID.match(c.kind) else 'kind unknown'] += 1
        names.add(c.name)
        for e, h in c.events:
            res['handler in module' if h in procs else 'handler not in module'] += 1
        for b in c.buttons:
            res['button: ' + (b.kind or 'unknown kind')] += 1
            if b.action:
                res['button action in module' if b.action in procs else 'button action not in module'] += 1
        for col in c.columns:
            res['columns'] += 1
            for e, h in col.events:
                res['column handler in module' if h in procs else 'column handler not in module'] += 1
            for which in ('steps', 'check', 'picture') if cfg is not None else ():
                if getattr(col, which):
                    whole = column_path(cfg, f, f.bindings.get(c.id), col, which)[1]
                    res['column data resolved' if whole is not None else 'column data not resolved'] += 1
    for cid, steps in f.bindings.items() if cfg is not None else ():
        res['data path resolved' if data_path(cfg, f, steps) is not None else 'data path not resolved'] += 1
    for e, h in f.events:
        res['form handler in module' if h in procs else 'form handler not in module'] += 1
    for r in set(OWN_REF.findall(f.module)):
        if r in names:
            res['ЭлементыФормы.X decoded'] += 1
        elif re.search(r'\{14,"%s",' % re.escape(r), stream_text):
            res['ЭлементыФормы.X in the form, not decoded'] += 1
    return res
