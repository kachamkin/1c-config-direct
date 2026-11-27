# Standard attributes (Ref, Code, Description, Owner, Parent, Date, Number, Period, Recorder, LineNumber ...).
# Their types are not stored: the platform derives them from object properties, and which of them exist depends on
# the properties too (Parent only in a hierarchical catalog, Recorder only in a register subordinate to a recorder).
# The rules below were checked against what the platform itself reports over COM. Settings changed in the designer
# (synonym, tooltip, fill checking ...) are stored per attribute as a property bag
#     {-id},510405d3-…,{14,N,<property GUID>,<value>,…}
# in a list near the object header (or in the header of a tabular section); the ids per class and the property GUIDs
# were learned against XML dumps. The list is absent when nothing was changed.
import collections
from v8meta import unq, at, is_collection, find_name_block, KIND

StdAttr = collections.namedtuple('StdAttr', 'obj ts name ru types settings how')
STD_SA = '510405d3-2a0c-4fea-960a-7fee59b32f9b'
STD_LSTR = '87024738-fc2a-4436-ada1-df79d395c424'
STD_KEYS = {
    'cf4abea3-37b2-11d4-940f-008048da11f9': 'Synonym', '4690ff70-e3fa-4914-9127-6a9acc5fc949': 'ToolTip',
    'cf4abea4-37b2-11d4-940f-008048da11f9': 'Comment', '2723eb98-b4c1-498a-a6f3-70444757902f': 'FillChecking',
    'f49e4ced-4033-4e6c-8755-9fbaaccd6078': 'Mask', '2c8143d5-4248-4c43-8bfb-307c0be2e415': 'FillFromFillingValue',
}
STD_FILLCHECK = {'0': 'DontCheck', '1': 'ShowError'}
# id of a standard attribute in the stored list -> its name, per class
STD_IDS = {
    'Catalogs': {'-13': 'PredefinedDataName', '-10': 'Predefined', '-8': 'Ref', '-7': 'DeletionMark', '-6': 'IsFolder',
                 '-5': 'Owner', '-4': 'Parent', '-3': 'Description', '-2': 'Code'},
    'ChartsOfCharacteristicTypes': {'-14': 'PredefinedDataName', '-11': 'ValueType', '-9': 'Description', '-8': 'Code',
                                    '-7': 'IsFolder', '-6': 'Parent', '-5': 'Predefined', '-4': 'DeletionMark', '-2': 'Ref'},
    'Documents': {'-7': 'Posted', '-5': 'Ref', '-4': 'DeletionMark', '-3': 'Date', '-2': 'Number'},
    'Enums': {'-3': 'Order', '-2': 'Ref'},
    'ExchangePlans': {'-13': 'ThisNode', '-10': 'ReceivedNo', '-9': 'SentNo', '-6': 'Ref', '-4': 'DeletionMark',
                      '-3': 'Description', '-2': 'Code'},
    'BusinessProcesses': {'-9': 'Started', '-8': 'HeadTask', '-7': 'Completed', '-5': 'Ref', '-4': 'DeletionMark',
                          '-3': 'Date', '-2': 'Number'},
    'Tasks': {'-10': 'Executed', '-9': 'Description', '-8': 'RoutePoint', '-7': 'BusinessProcess', '-5': 'Ref',
              '-4': 'DeletionMark', '-3': 'Date', '-2': 'Number'},
    'DocumentJournals': {'-60003': 'Type', '-101': 'Ref', '-100': 'Date', '-7': 'Posted', '-4': 'DeletionMark', '-2': 'Number'},
    'InformationRegisters': {'-5': 'Active', '-4': 'LineNumber', '-3': 'Recorder', '-2': 'Period'},
    'AccumulationRegisters': {'-9': 'RecordType', '-5': 'Active', '-4': 'LineNumber', '-3': 'Recorder', '-2': 'Period'},
}
TS_LINE_ID = {'DataProcessors': '-3', 'Reports': '-3'}      # elsewhere LineNumber of a tabular section is '-10'
# collection of tabular sections per class ('' = not seen yet: any collection that is not a field collection)
TS_COLL = {'Catalogs': '932159f9-95b2-4e76-a8dd-8849fe5c5ded', 'Documents': '21c53e09-8950-4b5e-a6a0-1054f1bbc274',
           'ChartsOfCharacteristicTypes': '54e36536-7863-42fd-bea3-c5edd3122fdc', 'ExchangePlans': '52293f4b-f98c-43ea-a80f-41047ae7ab58',
           'BusinessProcesses': 'a3fe6537-d787-40f7-8a06-419d2f0c1cfd', 'ChartsOfCalculationTypes': '054aa8cf-faa6-4634-aef4-1087ca0d88fc',
           'DataProcessors': '2bcef0d1-0981-11d6-b9b8-0050bae0a95d', 'Reports': 'b077d780-29e2-11d6-a3c7-0050bae0a776',
           'Tasks': '', 'ChartsOfAccounts': ''}
STD_RU = {
    'Ref': 'Ссылка', 'DeletionMark': 'ПометкаУдаления', 'Predefined': 'Предопределенный', 'PredefinedDataName': 'ИмяПредопределенныхДанных',
    'Code': 'Код', 'Description': 'Наименование', 'Owner': 'Владелец', 'Parent': 'Родитель', 'IsFolder': 'ЭтоГруппа',
    'Date': 'Дата', 'Number': 'Номер', 'Posted': 'Проведен', 'Period': 'Период', 'Recorder': 'Регистратор',
    'LineNumber': 'НомерСтроки', 'Active': 'Активность', 'RecordType': 'ВидДвижения', 'ValueType': 'ТипЗначения',
    'ThisNode': 'ЭтотУзел', 'SentNo': 'НомерОтправленного', 'ReceivedNo': 'НомерПринятого', 'Started': 'Стартован',
    'Completed': 'Завершен', 'HeadTask': 'ВедущаяЗадача', 'Executed': 'Выполнена', 'BusinessProcess': 'БизнесПроцесс',
    'RoutePoint': 'ТочкаМаршрута', 'Order': 'Порядок', 'Type': 'Тип',
}
REF_OF = {'Catalogs': 'CatalogRef', 'Documents': 'DocumentRef', 'Enums': 'EnumRef', 'ExchangePlans': 'ExchangePlanRef',
          'ChartsOfCharacteristicTypes': 'ChartOfCharacteristicTypesRef', 'ChartsOfAccounts': 'ChartOfAccountsRef',
          'ChartsOfCalculationTypes': 'ChartOfCalculationTypesRef', 'BusinessProcesses': 'BusinessProcessRef', 'Tasks': 'TaskRef'}
# header positions the property learner has too few objects for (14 business processes and 5 tasks in 7 configurations)
EXTRA = {'BusinessProcesses': {'NumberLength': (1, 18)},
         'Tasks': {'NumberLength': (1, 19), 'DescriptionLength': (1, 22), 'NumberAllowedLength': (1, 43)}}
ALLOWED = {'0': 'Fixed', '1': 'Variable'}
BOOL, DATETIME = [('Boolean', None)], [('Date', 'DateTime')]


def _refs(paths):
    out = []
    for p in paths or []:
        cls, _, name = p.partition('.')
        if cls in REF_OF and name and '.' not in name:
            out.append(('Type', '%s.%s' % (REF_OF[cls], name)))
    return sorted(out)


def _string(length, allowed='Variable'):
    return [('String', (length, 'Fixed' if allowed == 'Fixed' else 'Variable'))]


def _code(kind, length, allowed):
    return [('Number', (length, '0', 'Nonnegative'))] if kind == 'Number' else _string(length, allowed)


def _sa_list(node, depth):
    """first stored standard-attribute list within `depth` levels, not entering child collections"""
    if not isinstance(node, list):
        return None
    if len(node) > 4 and isinstance(node[1], str) and node[1].isdigit() and STD_SA in node:
        return node
    if depth > 0:
        for x in node:
            if isinstance(x, list) and not is_collection(x):
                r = _sa_list(x, depth - 1)
                if r is not None:
                    return r
    return None


def _bag_value(prop, v):
    if not isinstance(v, list) or not v:
        return None
    if v[0] == '"#"' and len(v) > 2 and v[1] == STD_LSTR:
        s = [unq(y) for y in v[2][1:] if isinstance(y, str)] if isinstance(v[2], list) else []
        return {lang: t for lang, t in zip(s[::2], s[1::2]) if t} or None
    if v[0] == '"#"' and len(v) > 2 and isinstance(v[2], str) and prop == 'FillChecking':
        return STD_FILLCHECK.get(v[2], '?' + v[2])
    if v[0] == '"S"' and len(v) > 1:
        return unq(v[1]) or None
    if v[0] == '"B"' and len(v) > 1:
        return 'true' if v[1] == '1' else 'false'
    return None


def bags(node, depth):
    """{id: {setting: value}} from the stored list: only settings that differ from the defaults are kept"""
    lst, out = _sa_list(node, depth), {}
    if lst is None:
        return out
    for i, x in enumerate(lst):
        if x != STD_SA or i == 0 or i + 1 >= len(lst) or not isinstance(lst[i - 1], list) or not lst[i - 1]:
            continue
        b, vals = lst[i + 1], {}
        if isinstance(b, list) and len(b) > 1 and isinstance(b[1], str) and b[1].isdigit():
            for j in range(2, len(b) - 1, 2):
                prop = STD_KEYS.get(b[j])
                val = _bag_value(prop, b[j + 1]) if prop else None
                if val is not None and not (prop == 'FillChecking' and val == 'DontCheck') \
                        and not (prop == 'FillFromFillingValue' and val == 'false'):
                    vals[prop] = val
        out[lst[i - 1][0]] = vals
    return out


def tabular_sections(cls, tree):
    """yield (name, node) of every tabular section, with or without attributes: a member of the class's collection of
    tabular sections (URL templates of HTTP services and operations of web services look the same, so the class decides)"""
    want = TS_COLL.get(cls)
    if want is None:
        return
    for coll in tree:
        if is_collection(coll) and (coll[0] == want or (want == '' and coll[0] not in KIND)):
            for x in coll[2:]:
                if isinstance(x, list) and x and isinstance(x[0], list) and any(is_collection(y) for y in x[1:]):
                    nb = find_name_block(x[0])
                    if nb:
                        yield unq(nb[2]), x


def standard_attributes(cfg, objects=None):
    """yield StdAttr: the covered classes, and LineNumber of every tabular section of any class"""
    trees = cfg.trees()
    props = {it.uuid: {p: v for p, v, how in cfg.properties(it, tree)} for it, tree in trees}
    for it, tree in trees:                                   # positions the learned tables lack
        for prop, path in EXTRA.get(it.cls, {}).items():
            v = at(tree, path)
            if prop not in props[it.uuid] and isinstance(v, str):
                props[it.uuid][prop] = ALLOWED.get(v, '?' + v) if prop.endswith('AllowedLength') else v
    path_props = {it.path: props[it.uuid] for it, tree in trees}
    recorders, bp_of_task = collections.defaultdict(list), collections.defaultdict(list)
    for it, tree in trees:
        pr = props[it.uuid]
        if it.cls == 'Documents':
            for r in pr.get('RegisterRecords') or []:
                recorders[r].append(it.path)
        elif it.cls == 'BusinessProcesses' and pr.get('Task'):
            bp_of_task[pr['Task']].append(it.path)
    for it, tree in trees:
        if objects is not None and it.path not in objects:
            continue
        cls, g = it.cls, props[it.uuid].get
        ref = [('Type', '%s.%s' % (REF_OF[cls], it.name))] if cls in REF_OF else []
        rows, assumed = [], set()
        if cfg.adopted(tree):
            pass                        # borrowed by an extension: its properties live in the configuration only
        elif cls in ('Catalogs', 'ChartsOfCharacteristicTypes'):
            hier = g('Hierarchical') == 'true'
            folders = hier and (cls == 'ChartsOfCharacteristicTypes' or g('HierarchyType') != 'HierarchyOfItems')
            rows = [('PredefinedDataName', _string('256')), ('Predefined', BOOL), ('Ref', ref), ('DeletionMark', BOOL)]
            if folders:
                rows.append(('IsFolder', BOOL))
            if cls == 'Catalogs' and g('Owners'):
                rows.append(('Owner', _refs(g('Owners'))))
            if hier:
                rows.append(('Parent', ref))
            if g('DescriptionLength') not in (None, '0'):
                rows.append(('Description', _string(g('DescriptionLength'))))
            if g('CodeLength') not in (None, '0'):
                rows.append(('Code', _code(g('CodeType') or 'String', g('CodeLength'), g('CodeAllowedLength'))))
            if cls == 'ChartsOfCharacteristicTypes':
                rows.append(('ValueType', [('Type', 'TypeDescription')]))
        elif cls in ('Documents', 'BusinessProcesses', 'Tasks'):
            rows = [('Ref', ref), ('DeletionMark', BOOL), ('Date', DATETIME)]
            if g('NumberLength') not in (None, '0'):
                if not g('NumberType'):
                    assumed.add('Number')          # every business process and task seen so far numbers by string
                rows.append(('Number', _code(g('NumberType') or 'String', g('NumberLength'), g('NumberAllowedLength'))))
            if cls == 'Documents':
                rows.append(('Posted', BOOL))
            elif cls == 'BusinessProcesses':
                rows += [('Started', BOOL), ('Completed', BOOL)] + ([('HeadTask', _refs([g('Task')]))] if g('Task') else [])
            else:
                if g('DescriptionLength') not in (None, '0'):
                    rows.append(('Description', _string(g('DescriptionLength'))))
                bps = bp_of_task.get(it.path, [])
                rows += [('Executed', BOOL), ('BusinessProcess', _refs(bps)),
                         ('RoutePoint', sorted(('Type', 'BusinessProcessRoutePointRef.' + p.split('.', 1)[1]) for p in bps))]
        elif cls == 'Enums':
            rows = [('Ref', ref), ('Order', [('Number', ('0', '0', 'Any'))])]
        elif cls == 'ExchangePlans':
            rows = [('Ref', ref), ('DeletionMark', BOOL)]
            if g('CodeLength') not in (None, '0'):
                rows.append(('Code', _string(g('CodeLength'), g('CodeAllowedLength'))))
            if g('DescriptionLength') not in (None, '0'):
                rows.append(('Description', _string(g('DescriptionLength'))))
            rows += [('ThisNode', BOOL), ('SentNo', [('Number', ('10', '0', 'Nonnegative'))]),
                     ('ReceivedNo', [('Number', ('10', '0', 'Nonnegative'))])]
        elif cls == 'DocumentJournals':
            docs = [path_props.get(p, {}) for p in g('RegisteredDocuments') or []]
            lens = [int(d['NumberLength']) for d in docs if (d.get('NumberLength') or '0').isdigit()]
            number = _string(str(max(lens)) if lens else '0',
                             'Fixed' if docs and all(d.get('NumberAllowedLength') == 'Fixed' for d in docs) else 'Variable')
            rows = [('Type', [('Type', 'Type')]), ('Ref', _refs(g('RegisteredDocuments'))), ('Date', DATETIME), ('Posted', BOOL),
                    ('DeletionMark', BOOL), ('Number', number)]
        elif cls in ('InformationRegisters', 'AccumulationRegisters'):
            per = g('InformationRegisterPeriodicity') if cls == 'InformationRegisters' else 'Second'
            sub = cls == 'AccumulationRegisters' or g('WriteMode') == 'RecorderSubordinate'
            if per and per != 'Nonperiodical':
                rows.append(('Period', [('Date', 'DateTime' if per in ('Second', 'RecorderPosition') else 'Date')]))
            if sub:
                rows += [('Recorder', _refs(recorders.get(it.path, []))), ('LineNumber', [('Number', ('9', '0', 'Nonnegative'))]),
                         ('Active', BOOL)]
            if cls == 'AccumulationRegisters' and g('RegisterType') == 'Balance':
                rows.append(('RecordType', [('Type', 'AccumulationMovementType')]))
        if rows:
            ids = {v: k for k, v in STD_IDS.get(cls, {}).items()}
            own = bags(tree, 3)
            for name, types in rows:
                yield StdAttr(it.path, '', name, STD_RU.get(name, name), types, own.get(ids.get(name), {}),
                              'assumed' if name in assumed else '')
        line_id = TS_LINE_ID.get(cls, '-10')
        for ts, node in tabular_sections(cls, tree):
            yield StdAttr(it.path, ts, 'LineNumber', 'НомерСтроки', [('Number', ('5', '0', 'Nonnegative'))],
                          bags(node[0], 5).get(line_id, {}), '')
