# Metadata of a 1C configuration read straight from its storage files (Config table rows or a .cf container):
# object tree and names, module texts, typed fields. All tables below are platform constants found empirically
# (26.11.2026, УТ 2.3 and УТ 3.1, platform 8.3.27) and cross-checked against XML dumps of the same configurations.
import os, re, json, collections
from v8cfg import Source, text, parse_brace, unq, inflate, is_container, container_entries, GUID_RE

G = GUID_RE
GUID = re.compile(G + '$')
NAMED = re.compile(r'\{\d+,\d+,(' + G + r')\},"((?:[^"]|"")*)"')
LIST = re.compile(r'\{(' + G + r'),\s*(\d+)((?:,\s*' + G + r')*)\s*\}')

# collection GUID in the configuration description -> class folder (as in XML dumps)
CLASS = {
    '09736b02-9cac-4e3f-b4f7-d3e9576ab948': 'Roles', '0c89c792-16c3-11d5-b96b-0050bae0a95d': 'CommonTemplates',
    '0fe48980-252d-11d6-a3c7-0050bae0a776': 'CommonModules', '0fffc09c-8f4c-47cc-b41c-8d5c5a221d79': 'HTTPServices',
    '11bdaf85-d5ad-4d91-bb24-aa0eee139052': 'ScheduledJobs', '15794563-ccec-41f6-a83c-ec5f7b9a5bc1': 'CommonAttributes',
    '24c43748-c938-45d0-8d14-01424a72b11e': 'SessionParameters', '30d554db-541e-4f62-8970-a1c6dcfeb2bc': 'FunctionalOptionsParameters',
    '37f2fa9a-b276-11d4-9435-004095e12fc7': 'Subsystems', '39bddf6a-0c3c-452b-921c-d99cfa1c2f1b': 'Interfaces',
    '3e5404af-6ef8-4c73-ad11-91bd2dfac4c8': 'Styles', '3e7bfcc0-067d-11d6-a3c7-0050bae0a776': 'FilterCriteria',
    '46b4cd97-fd13-4eaa-aba2-3bddd7699218': 'SettingsStorages', '4e828da6-0f44-4b5b-b1c0-a2b3cfe7bdcc': 'EventSubscriptions',
    '58848766-36ea-4076-8800-e91eb49590d7': 'StyleItems', '7dcd43d9-aca5-4926-b549-1842e6a4e8cf': 'CommonPictures',
    '857c4a91-e5f4-4fac-86ec-787626f1c108': 'ExchangePlans', '8657032e-7740-4e1d-a3ba-5dd6e8afb78f': 'WebServices',
    '9cd510ce-abfc-11d4-9434-004095e12fc7': 'Languages', 'af547940-3268-434f-a3e7-e47d6d2638c3': 'FunctionalOptions',
    'c045099e-13b9-4fb6-9d50-fca00202971e': 'DefinedTypes', 'cc9df798-7c94-4616-97d2-7aa0b7bc515e': 'XDTOPackages',
    'd26096fb-7a5d-4df9-af63-47d04771fa9b': 'WSReferences', '0195e80c-b157-11d4-9435-004095e12fc7': 'Constants',
    '061d872a-5787-460e-95ac-ed74ea3a3e84': 'Documents', '07ee8426-87f1-11d5-b99c-0050bae0a95d': 'CommonForms',
    '13134201-f60b-11d5-a3c7-0050bae0a776': 'InformationRegisters', '1c57eabe-7349-44b3-b1de-ebfeab67b47d': 'CommandGroups',
    '2f1a5187-fb0e-4b05-9489-dc5dd6412348': 'CommonCommands', '36a8e346-9aaa-4af9-bdbd-83be3c177977': 'DocumentNumerators',
    '4612bd75-71b7-4a5c-8cc5-2b0b65f9fa0d': 'DocumentJournals', '631b75a0-29e2-11d6-a3c7-0050bae0a776': 'Reports',
    '82a1b659-b220-4d94-a9bd-14d757b95a48': 'ChartsOfCharacteristicTypes', 'b64d9a40-1642-11d6-a3c7-0050bae0a776': 'AccumulationRegisters',
    'bc587f20-35d9-11d6-a3c7-0050bae0a776': 'Sequences', 'bf845118-327b-4682-b5c6-285d2a0eb296': 'DataProcessors',
    'cf4abea6-37b2-11d4-940f-008048da11f9': 'Catalogs', 'f6a80749-5ad7-400b-8519-39dc5dff2542': 'Enums',
    '238e7e88-3c5f-48b2-8a3b-81ebbecb20ed': 'ChartsOfAccounts', '2deed9b8-0056-4ffe-a473-c20a6c32a0bc': 'AccountingRegisters',
    '30b100d6-b29f-47ac-aec7-cb8ca8a54767': 'ChartsOfCalculationTypes', 'f2de87a8-64e5-45eb-a22d-b3aedab050e7': 'CalculationRegisters',
    '3e63355c-1378-4953-be9b-1deb5fb6bec5': 'Tasks', 'fcd3404e-1523-48ce-9bc0-ecdb822684a1': 'BusinessProcesses',
    '5274d9fc-9c3a-4a71-8f5e-a0db8ab23de5': 'ExternalDataSources',
}
TEMPLATES = '3daea016-69b7-4ed4-9453-127911372fe6'
# the "forms" collection inside an object has its own GUID in every class
FORM_LISTS = {
    'fdf816d2-1ead-11d5-b975-0050bae0a95d', 'fb880e93-47d7-4127-9357-a20e69c17545', 'd5b0e5ed-256d-401c-9c36-f630cafd8a62',
    'a3b368c0-29e2-11d6-a3c7-0050bae0a776', '13134204-f60b-11d5-a3c7-0050bae0a776', 'b64d9a44-1642-11d6-a3c7-0050bae0a776',
    '3f7a8120-b71a-4265-98bf-4d9bc09b7719', 'eb2b78a8-40a6-4b7e-b1b3-6ca9966cbc94', 'ec81ad10-ca07-11d5-b9a5-0050bae0a95d',
    '33f2e54b-37ce-4a7a-a569-b648d7aa4634', '87c509ab-3d38-4d67-b379-aca796298578', '00867c40-06b1-11d6-a3c7-0050bae0a776',
    'b8533c0c-2342-4db3-91a2-c2b08cbf6b23', '3f58cbfb-4172-4e54-be49-561a579bb38b',
    # charts of accounts, accounting registers, charts of calculation types, calculation registers (learned on УТП 1.2)
    '5372e285-03db-4f8c-8565-fe56f1aea40e', 'd3b5d6eb-4ea2-4610-a3e2-624d4e815934', 'a7f8f92a-7a4b-484b-937e-42d242e64144',
    'a2cb086c-db98-43e4-a1a9-0760ab048f8d',
}
# (class, file suffix) -> module kind (XML file name without .bsl); a module lives in "<uuid>.<suffix>"
MODULE = {
    ('Catalogs', '0'): 'ObjectModule', ('Catalogs', '3'): 'ManagerModule',
    ('Documents', '0'): 'ObjectModule', ('Documents', '2'): 'ManagerModule',
    ('DataProcessors', '0'): 'ObjectModule', ('DataProcessors', '2'): 'ManagerModule',
    ('Reports', '0'): 'ObjectModule', ('Reports', '2'): 'ManagerModule',
    ('InformationRegisters', '1'): 'RecordSetModule', ('InformationRegisters', '2'): 'ManagerModule',
    ('AccumulationRegisters', '1'): 'RecordSetModule', ('AccumulationRegisters', '2'): 'ManagerModule',
    ('ExchangePlans', '2'): 'ObjectModule', ('ExchangePlans', '3'): 'ManagerModule',
    ('ChartsOfCharacteristicTypes', '15'): 'ObjectModule', ('ChartsOfCharacteristicTypes', '16'): 'ManagerModule',
    ('BusinessProcesses', '6'): 'ObjectModule', ('BusinessProcesses', '8'): 'ManagerModule',
    ('Tasks', '6'): 'ObjectModule', ('Tasks', '7'): 'ManagerModule',
    ('Enums', '0'): 'ManagerModule', ('DocumentJournals', '1'): 'ManagerModule', ('SettingsStorages', '8'): 'ManagerModule',
    ('AccountingRegisters', '6'): 'RecordSetModule', ('AccountingRegisters', '7'): 'ManagerModule',
    ('ChartsOfAccounts', '14'): 'ObjectModule', ('ChartsOfAccounts', '15'): 'ManagerModule', ('Sequences', '0'): 'RecordSetModule',
    ('ChartsOfCalculationTypes', '0'): 'ObjectModule', ('ChartsOfCalculationTypes', '3'): 'ManagerModule',
    ('CalculationRegisters', '1'): 'RecordSetModule', ('CalculationRegisters', '2'): 'ManagerModule',
    ('FilterCriteria', '0'): 'ManagerModule',
    ('Constants', '0'): 'ValueManagerModule', ('CommonModules', '0'): 'Module', ('WebServices', '0'): 'Module',
    ('HTTPServices', '0'): 'Module', ('CommonCommands', '2'): 'CommandModule', ('Commands', '2'): 'CommandModule',
    ('Forms', '0'): 'FormModule', ('CommonForms', '0'): 'FormModule',
    ('Configuration', '0'): 'OrdinaryApplicationModule', ('Configuration', '5'): 'ExternalConnectionModule',
    ('Configuration', '6'): 'ManagedApplicationModule', ('Configuration', '7'): 'SessionModule',
}
SINGULAR = {
    'Catalogs': 'Catalog', 'Documents': 'Document', 'Enums': 'Enum', 'ChartsOfCharacteristicTypes': 'ChartOfCharacteristicTypes',
    'ChartsOfAccounts': 'ChartOfAccounts', 'ChartsOfCalculationTypes': 'ChartOfCalculationTypes', 'ExchangePlans': 'ExchangePlan',
    'BusinessProcesses': 'BusinessProcess', 'Tasks': 'Task', 'InformationRegisters': 'InformationRegister',
    'AccumulationRegisters': 'AccumulationRegister', 'AccountingRegisters': 'AccountingRegister',
    'CalculationRegisters': 'CalculationRegister', 'DataProcessors': 'DataProcessor', 'Reports': 'Report', 'Constants': 'Constant',
    'DocumentJournals': 'DocumentJournal', 'FilterCriteria': 'FilterCriterion', 'Sequences': 'Sequence',
    'SettingsStorages': 'SettingsStorage', 'DefinedTypes': 'DefinedType',
}
# where generated type ids sit in an object description: (class, category) -> index path
GEN_POS = {
    ('AccumulationRegisters', 'Record'): (1, 1), ('AccumulationRegisters', 'Manager'): (1, 3), ('AccumulationRegisters', 'Selection'): (1, 5),
    ('AccumulationRegisters', 'List'): (1, 7), ('AccumulationRegisters', 'RecordSet'): (1, 9), ('AccumulationRegisters', 'RecordKey'): (1, 11),
    ('BusinessProcesses', 'Object'): (1, 3), ('BusinessProcesses', 'Ref'): (1, 5), ('BusinessProcesses', 'Selection'): (1, 7),
    ('BusinessProcesses', 'List'): (1, 9), ('BusinessProcesses', 'Manager'): (1, 11), ('BusinessProcesses', 'RoutePointRef'): (1, 13),
    ('Catalogs', 'Object'): (1, 1), ('Catalogs', 'Ref'): (1, 3), ('Catalogs', 'Selection'): (1, 5), ('Catalogs', 'List'): (1, 7),
    ('Catalogs', 'Manager'): (1, 34),
    ('ChartsOfCharacteristicTypes', 'Object'): (1, 1), ('ChartsOfCharacteristicTypes', 'Ref'): (1, 3),
    ('ChartsOfCharacteristicTypes', 'Selection'): (1, 5), ('ChartsOfCharacteristicTypes', 'List'): (1, 7),
    ('ChartsOfCharacteristicTypes', 'Characteristic'): (1, 9), ('ChartsOfCharacteristicTypes', 'Manager'): (1, 11),
    ('Constants', 'Manager'): (1, 2), ('Constants', 'ValueManager'): (1, 4), ('Constants', 'ValueKey'): (1, 13),
    ('DataProcessors', 'Object'): (1, 1), ('DataProcessors', 'Manager'): (1, 7),
    ('DefinedTypes', 'DefinedType'): (1, 1),
    ('DocumentJournals', 'List'): (1, 1), ('DocumentJournals', 'Manager'): (1, 8), ('DocumentJournals', 'Selection'): (1, 10),
    ('Documents', 'Object'): (1, 1), ('Documents', 'Ref'): (1, 3), ('Documents', 'Selection'): (1, 5), ('Documents', 'List'): (1, 7),
    ('Documents', 'Manager'): (1, 26),
    ('Enums', 'Ref'): (1, 1), ('Enums', 'Manager'): (1, 3), ('Enums', 'List'): (1, 7),
    ('ExchangePlans', 'Object'): (1, 1), ('ExchangePlans', 'Ref'): (1, 3), ('ExchangePlans', 'Selection'): (1, 5),
    ('ExchangePlans', 'List'): (1, 7), ('ExchangePlans', 'Manager'): (1, 9),
    ('FilterCriteria', 'Manager'): (1, 1), ('FilterCriteria', 'List'): (1, 3),
    ('InformationRegisters', 'Record'): (1, 1), ('InformationRegisters', 'Manager'): (1, 3), ('InformationRegisters', 'Selection'): (1, 5),
    ('InformationRegisters', 'List'): (1, 7), ('InformationRegisters', 'RecordSet'): (1, 9), ('InformationRegisters', 'RecordKey'): (1, 11),
    ('InformationRegisters', 'RecordManager'): (1, 13),
    ('Reports', 'Object'): (1, 1), ('Reports', 'Manager'): (1, 12),
    ('Sequences', 'Record'): (1, 1), ('Sequences', 'Manager'): (1, 3), ('Sequences', 'RecordSet'): (1, 5),
    ('SettingsStorages', 'Manager'): (1, 2),
    ('Tasks', 'Object'): (1, 3), ('Tasks', 'Ref'): (1, 5), ('Tasks', 'Selection'): (1, 7), ('Tasks', 'List'): (1, 9), ('Tasks', 'Manager'): (1, 11),
    ('ChartsOfAccounts', 'Object'): (1, 1), ('ChartsOfAccounts', 'Ref'): (1, 3), ('ChartsOfAccounts', 'Selection'): (1, 5),
    ('ChartsOfAccounts', 'List'): (1, 7), ('ChartsOfAccounts', 'Manager'): (1, 9), ('ChartsOfAccounts', 'ExtDimensionTypes'): (1, 11),
    ('ChartsOfAccounts', 'ExtDimensionTypesRow'): (1, 13),
    ('AccountingRegisters', 'Record'): (1, 1), ('AccountingRegisters', 'ExtDimensions'): (1, 3), ('AccountingRegisters', 'RecordSet'): (1, 5),
    ('AccountingRegisters', 'RecordKey'): (1, 7), ('AccountingRegisters', 'Selection'): (1, 9), ('AccountingRegisters', 'List'): (1, 11),
    ('AccountingRegisters', 'Manager'): (1, 13),
    ('ChartsOfCalculationTypes', 'Object'): (1, 2), ('ChartsOfCalculationTypes', 'Ref'): (1, 4), ('ChartsOfCalculationTypes', 'Selection'): (1, 6),
    ('ChartsOfCalculationTypes', 'List'): (1, 8), ('ChartsOfCalculationTypes', 'Manager'): (1, 10),
    ('ChartsOfCalculationTypes', 'DisplacingCalculationTypes'): (1, 12), ('ChartsOfCalculationTypes', 'DisplacingCalculationTypesRow'): (1, 14),
    ('ChartsOfCalculationTypes', 'BaseCalculationTypes'): (1, 16), ('ChartsOfCalculationTypes', 'BaseCalculationTypesRow'): (1, 18),
    ('ChartsOfCalculationTypes', 'LeadingCalculationTypes'): (1, 20), ('ChartsOfCalculationTypes', 'LeadingCalculationTypesRow'): (1, 22),
    ('CalculationRegisters', 'Record'): (1, 1), ('CalculationRegisters', 'Manager'): (1, 3), ('CalculationRegisters', 'Selection'): (1, 5),
    ('CalculationRegisters', 'List'): (1, 7), ('CalculationRegisters', 'RecordSet'): (1, 9), ('CalculationRegisters', 'RecordKey'): (1, 11),
    ('CalculationRegisters', 'Recalcs'): (1, 13),
}
# platform types after "#" (names as in XML dumps; old dump formats call AnyIBRef "AnyRef")
PLATFORM = {
    'e199ca70-93cf-46ce-a54b-6edc88c3a296': ('Type', 'ValueStorage'), 'fc01b5df-97fe-449b-83d4-218a090e681e': ('Type', 'UUID'),
    '2fdc88ec-7c9b-43cd-8ba5-873f043bdd88': ('Type', 'StandardPeriod'), '0387f3a2-7df5-4804-948b-4580a51e4a15': ('Type', 'StandardBeginningDate'),
    'acf6192e-81ca-46ef-93a6-5a6968b78663': ('Type', 'ValueTable'), 'e603c0f2-92fb-4d47-8f38-a44a381cf235': ('Type', 'ValueTree'),
    '4772b3b4-f4a3-49c0-a1a5-8cb5961511a3': ('Type', 'ValueListType'), '4500381b-db30-4a10-9db4-990038032acf': ('Type', 'FixedArray'),
    '3ee983d7-ace7-40f9-bb7e-2e916fcddd56': ('Type', 'FixedStructure'), '220455ea-6c85-4513-996f-bbe79ed07774': ('Type', 'FixedMap'),
    'cab0d12b-3c88-4993-8edc-8c3827cadc7d': ('Type', 'SettingsComposer'), '3543ef08-3316-4f7e-9447-0cd0a1cbf1d5': ('Type', 'Chart'),
    '4652c4ec-1d1d-4af4-b835-e33fcb43af8c': ('Type', 'Filter'), '0dda99d9-ae9f-43d2-b7ac-44f3fb0d4059': ('Type', 'ReportBuilder'),
    '4d599114-9432-447f-ab67-2d9aafbce68e': ('Type', 'CustomFields'), 'dcfc3784-a14f-4786-ac7b-c82db5ba275f': ('Type', 'ConstantsSet'),
    'b1b064f3-ae38-49bf-8c6d-390c65fd94af': ('Type', 'ComparisonType'), '8acd280e-c29c-4543-8be7-7f78cad52c06': ('Type', 'SortDirection'),
    '5878e725-50de-4998-b589-3c56ea63e735': ('Type', 'ChartType'), 'e603103e-a318-4edc-a014-b1c6cf94d49f': ('Type', 'SpreadsheetDocument'),
    '280f5f0e-9c8a-49cc-bf6d-4d296cc17a63': ('TypeSet', 'AnyIBRef'), 'e61ef7b8-f3e1-4f4b-8ac7-676e90524997': ('TypeSet', 'CatalogRef'),
    '38bfd075-3e63-4aaa-a93e-94521380d579': ('TypeSet', 'DocumentRef'), '474c3bf6-08b5-4ddc-a2ad-989cedf11583': ('TypeSet', 'EnumRef'),
    '99892482-ed55-4fb5-a7f7-20888820a758': ('TypeSet', 'ChartOfCharacteristicTypesRef'),
    'ac606d60-0209-4159-8e4c-794bc091ce38': ('TypeSet', 'ChartOfAccountsRef'),
    '593cd424-0877-470d-91f9-b90a982059b4': ('TypeSet', 'ChartOfCalculationTypesRef'),
    '0a52f9de-73ea-4507-81e8-66217bead73a': ('TypeSet', 'ExchangePlanRef'), '214fa4d8-6ba4-4748-a5e1-6332b5887780': ('TypeSet', 'BusinessProcessRef'),
    '11e5f865-1501-40c6-b4d4-022095a296a5': ('TypeSet', 'BusinessProcessRoutePointRef'), '6291e9b3-8df5-44e1-b6b2-d9fe008016c0': ('TypeSet', 'TaskRef'),
    # event subscription sources "all objects of a class" are stored as the class GUID itself
    '061d872a-5787-460e-95ac-ed74ea3a3e84': ('TypeSet', 'DocumentObject'), 'cf4abea6-37b2-11d4-940f-008048da11f9': ('TypeSet', 'CatalogObject'),
    '82a1b659-b220-4d94-a9bd-14d757b95a48': ('TypeSet', 'ChartOfCharacteristicTypesObject'),
    '238e7e88-3c5f-48b2-8a3b-81ebbecb20ed': ('TypeSet', 'ChartOfAccountsObject'),
    '30b100d6-b29f-47ac-aec7-cb8ca8a54767': ('TypeSet', 'ChartOfCalculationTypesObject'),
    '857c4a91-e5f4-4fac-86ec-787626f1c108': ('TypeSet', 'ExchangePlanObject'), 'fcd3404e-1523-48ce-9bc0-ecdb822684a1': ('TypeSet', 'BusinessProcessObject'),
    '3e63355c-1378-4953-be9b-1deb5fb6bec5': ('TypeSet', 'TaskObject'), '0195e80c-b157-11d4-9435-004095e12fc7': ('TypeSet', 'ConstantValueManager'),
    '13134201-f60b-11d5-a3c7-0050bae0a776': ('TypeSet', 'InformationRegisterRecordSet'),
    'b64d9a40-1642-11d6-a3c7-0050bae0a776': ('TypeSet', 'AccumulationRegisterRecordSet'),
    '2deed9b8-0056-4ffe-a473-c20a6c32a0bc': ('TypeSet', 'AccountingRegisterRecordSet'),
    'f2de87a8-64e5-45eb-a22d-b3aedab050e7': ('TypeSet', 'CalculationRegisterRecordSet'),
    'bc587f20-35d9-11d6-a3c7-0050bae0a776': ('TypeSet', 'SequenceRecordSet'),
    '274bf899-db0e-4df6-8ab5-67bf6371ec0b': ('TypeSet', 'RecalculationRecordSet'),
}
# field collection GUID -> kind of its fields
KIND = {
    'cf4abea7-37b2-11d4-940f-008048da11f9': 'Attribute', '45e46cbc-3e24-4165-8b7b-cc98a6f80211': 'Attribute',
    '888744e1-b616-11d4-9436-004095e12fc7': 'Attribute', 'ec6bb5e5-b7a8-4d75-bec9-658107a699cf': 'Attribute',
    '5d24a9d1-098e-11d6-b9b8-0050bae0a95d': 'Attribute', '7e7123e0-29e2-11d6-a3c7-0050bae0a776': 'Attribute',
    'c339c860-29e2-11d6-a3c7-0050bae0a776': 'Attribute', '87c988de-ecbf-413b-87b0-b9516df05e28': 'Attribute',
    '8ddfb495-c5fc-46b9-bdc5-bcf58341bff0': 'Attribute', 'e97c0570-251c-4566-b0f1-10686820f143': 'AddressingAttribute',
    '31182525-9346-4595-81f8-6f91a72ebe06': 'Attribute', '1a1b4fea-e093-470d-94ff-1d2f16cda2ab': 'Attribute',
    '13134202-f60b-11d5-a3c7-0050bae0a776': 'Resource', '13134203-f60b-11d5-a3c7-0050bae0a776': 'Dimension',
    'a2207540-1400-11d6-a3c7-0050bae0a776': 'Attribute', 'b64d9a41-1642-11d6-a3c7-0050bae0a776': 'Resource',
    'b64d9a42-1642-11d6-a3c7-0050bae0a776': 'Attribute', 'b64d9a43-1642-11d6-a3c7-0050bae0a776': 'Dimension',
    '437488c0-35e2-11d6-a3c7-0050bae0a776': 'Dimension',
    '35b63b9d-0adf-4625-a047-10ae874c19a3': 'Dimension', '63405499-7491-4ce3-ac72-43433cbe4112': 'Resource',
    '9d28ee33-9c7e-4a1b-8f13-50aa9b36607b': 'Attribute', 'b12fc850-8210-43c8-ae05-89567e698fbb': 'Dimension',
    '702b33ad-843e-41aa-8064-112cd38cc92c': 'Resource', '1b304502-2216-440b-960f-60decd04bb5d': 'Attribute',
    '6e65cbf5-daa8-4d8d-bef8-59723f4e5777': 'Attribute', '78bd1243-c4df-46c3-8138-e147465cb9a4': 'AccountingFlag',
    'c70ca527-5042-4cad-a315-dcb4007e32a3': 'ExtDimensionAccountingFlag', '0dc22ad2-476a-4794-afae-cfa7ed251752': 'Attribute',
}
# Russian names accepted in queries
RU = {
    'Справочник': 'Catalogs', 'Документ': 'Documents', 'Перечисление': 'Enums', 'ПланВидовХарактеристик': 'ChartsOfCharacteristicTypes',
    'ПланСчетов': 'ChartsOfAccounts', 'ПланВидовРасчета': 'ChartsOfCalculationTypes', 'ПланОбмена': 'ExchangePlans',
    'БизнесПроцесс': 'BusinessProcesses', 'Задача': 'Tasks', 'РегистрСведений': 'InformationRegisters',
    'РегистрНакопления': 'AccumulationRegisters', 'РегистрБухгалтерии': 'AccountingRegisters', 'РегистрРасчета': 'CalculationRegisters',
    'Обработка': 'DataProcessors', 'Отчет': 'Reports', 'Константа': 'Constants', 'ЖурналДокументов': 'DocumentJournals',
    'КритерийОтбора': 'FilterCriteria', 'Последовательность': 'Sequences', 'ХранилищеНастроек': 'SettingsStorages',
    'ОпределяемыйТип': 'DefinedTypes', 'ОбщийМодуль': 'CommonModules', 'ОбщаяФорма': 'CommonForms', 'ОбщаяКоманда': 'CommonCommands',
    'ОбщийМакет': 'CommonTemplates', 'ОбщийРеквизит': 'CommonAttributes', 'ВебСервис': 'WebServices', 'HTTPСервис': 'HTTPServices',
    'ПодпискаНаСобытие': 'EventSubscriptions', 'РегламентноеЗадание': 'ScheduledJobs', 'ПараметрСеанса': 'SessionParameters',
    'Роль': 'Roles', 'Подсистема': 'Subsystems', 'Конфигурация': 'Configuration',
    'Форма': 'Forms', 'Команда': 'Commands', 'Макет': 'Templates',
    'МодульОбъекта': 'ObjectModule', 'МодульМенеджера': 'ManagerModule', 'МодульНабораЗаписей': 'RecordSetModule',
    'МодульМенеджераЗначения': 'ValueManagerModule', 'МодульКоманды': 'CommandModule', 'МодульФормы': 'FormModule',
    'Модуль': 'Module', 'МодульСеанса': 'SessionModule', 'МодульУправляемогоПриложения': 'ManagedApplicationModule',
    'МодульОбычногоПриложения': 'OrdinaryApplicationModule', 'МодульВнешнегоСоединения': 'ExternalConnectionModule',
}


def normalize_query(q):
    """'Справочник.Валюты.МодульОбъекта' -> 'Catalogs.Валюты.ObjectModule'"""
    return '.'.join(RU.get(p, p) for p in q.split('.')) if q else q


def at(node, path):
    for i in path:
        if not isinstance(node, list) or i >= len(node):
            return None
        node = node[i]
    return node


def is_name_block(n):
    return (isinstance(n, list) and len(n) > 2 and isinstance(n[1], list) and len(n[1]) == 3
            and isinstance(n[1][2], str) and GUID.match(n[1][2]) is not None and isinstance(n[2], str) and n[2][:1] == '"')


def is_collection(n):
    return isinstance(n, list) and len(n) > 1 and isinstance(n[0], str) and GUID.match(n[0]) is not None and isinstance(n[1], str) and n[1].isdigit()


def find_name_block(n, depth=0):
    """first {n,{a,b,uuid},"Name",…} within a few levels, not descending into child collections"""
    if is_name_block(n):
        return n
    if depth < 4 and isinstance(n, list):
        for x in n:
            if isinstance(x, list) and not is_collection(x):
                r = find_name_block(x, depth + 1)
                if r:
                    return r
    return None


def typed_fields(node, coll=None, ctx=()):
    """yield (collection guid, context names, field uuid, field name, pattern node)"""
    if not isinstance(node, list):
        return
    if is_collection(node):
        coll = node[0]
    for i, x in enumerate(node):
        if isinstance(x, list) and x and x[0] == '"Pattern"' and i > 0:
            nb = find_name_block(node[i - 1])
            if nb:
                yield coll, ctx, nb[1][2], unq(nb[2]), x
    for x in node:
        if isinstance(x, list):
            sub = ctx
            if x and isinstance(x[0], list) and any(is_collection(y) for y in x[1:]):
                nb = find_name_block(x[0])
                if nb:
                    sub = ctx + (unq(nb[2]),)          # tabular section
            yield from typed_fields(x, coll, sub)


def name_synonym(t, uuid):
    m = re.search(r'\{\d+,\d+,' + uuid + r'\},"((?:[^"]|"")*)",\s*\{\d+((?:,\s*"(?:[^"]|"")*")*)\s*\}', t)
    if not m:
        m2 = re.search(r'\{\d+,\d+,' + uuid + r'\},"((?:[^"]|"")*)"', t)
        return (m2.group(1).replace('""', '"') if m2 else None), {}
    vals = [v.replace('""', '"') for v in re.findall(r'"((?:[^"]|"")*)"', m.group(2))]
    return m.group(1).replace('""', '"'), dict(zip(vals[::2], vals[1::2]))


Item = collections.namedtuple('Item', 'uuid cls path name synonyms')
Module = collections.namedtuple('Module', 'file path kind fmt text')
Field = collections.namedtuple('Field', 'obj kind path name uuid types')


def _info_kind(info):
    """module container 'info' entry: {3,1,…} source text, {3,2,…} compiled image only, {3,3,…} text encrypted"""
    m = re.match(r'\s*\{(\d+),(\d+)', info)
    return m.group(2) if m else '1'


class Configuration:
    def __init__(self, src):
        self.src = src if isinstance(src, Source) else Source(src)
        s = self.src
        # a configuration has "root" ({2,<description uuid>,…}) and "version"; an extension (.cfe) has one "configinfo"
        # record that holds both: {0,{216,0,{80316,0}}},{2,<description uuid>,…}
        self.root_name = 'root' if s.has('root') else 'configinfo' if s.has('configinfo') else None
        if not self.root_name:
            raise ValueError('neither root nor configinfo found: not a configuration')
        rt = text(s.raw(self.root_name))
        self.cfg_file = re.search(r'\{2,(' + G + ')', rt).group(1)
        self.is_extension = self.root_name == 'configinfo'
        self.cfg_text = text(s.raw(self.cfg_file))
        m = NAMED.search(self.cfg_text)
        self.inner = m.group(1)
        self.name, self.synonyms = name_synonym(self.cfg_text, self.inner)
        self.items = {self.inner: Item(self.inner, 'Configuration', 'Configuration', self.name, self.synonyms)}
        self.top = []                                   # uuids of top-level objects in description order
        self._texts = {}
        for lm in LIST.finditer(self.cfg_text):
            cls = CLASS.get(lm.group(1))
            if not cls:
                continue
            for u in re.findall(G, lm.group(3)):
                if not s.has(u):
                    continue
                ot = text(s.raw(u))
                self._texts[u] = ot
                nm, syn = name_synonym(ot, u)
                path = '%s.%s' % (cls, nm or u)
                self.items[u] = Item(u, cls, path, nm or u, syn)
                self.top.append(u)
                for sl in LIST.finditer(ot):           # forms and templates: separate files listed by uuid
                    sub = 'Forms' if sl.group(1) in FORM_LISTS else 'Templates' if sl.group(1) == TEMPLATES else None
                    if not sub:
                        continue
                    for su in re.findall(G, sl.group(3)):
                        if s.has(su) and su not in self.items:
                            sn, ss = name_synonym(text(s.raw(su)), su)
                            self.items[su] = Item(su, sub, '%s.%s.%s' % (path, sub, sn or su), sn or su, ss)
                for cm in NAMED.finditer(ot):          # commands are described inside the owner, module in "<uuid>.2"
                    cu = cm.group(1)
                    if cu != u and cu not in self.items and s.has(cu + '.2'):
                        cn = cm.group(2).replace('""', '"')
                        self.items[cu] = Item(cu, 'Commands', '%s.Commands.%s' % (path, cn), cn, {})
        self._trees = None
        self._types = None

    # ------------------------------------------------------------------ properties of the configuration
    def property_strings(self):
        """vendor and version: the two strings right after the 4 uuids that follow the info urls (checked on two configs)"""
        tree = parse_brace(self.cfg_text)
        node = at(tree, (3, 1, 1))
        if not isinstance(node, list):
            return None, None
        for i in range(len(node) - 6):
            if all(isinstance(node[i + k], str) and GUID.match(node[i + k]) for k in range(4)) and node[i + 4] in ('0', '1') \
                    and isinstance(node[i + 5], str) and node[i + 5][:1] == '"' and isinstance(node[i + 6], str) and node[i + 6][:1] == '"':
                return unq(node[i + 5]), unq(node[i + 6])
        return None, None

    def compatibility(self):
        name = 'version' if self.src.has('version') else self.root_name
        m = re.search(r'\{\d+,\d+,\s*\{(8\d{4}),\d+\}', text(self.src.raw(name)))
        if not m:
            return None
        v = m.group(1)
        return '%s.%s.%d' % (v[0], v[2], int(v[3:]))

    # ------------------------------------------------------------------ modules
    def module_text(self, file, kind):
        b = self.src.raw(file)
        if is_container(b):
            ents = {n: inflate(d) for n, d in container_entries(b)}
            flag = _info_kind(text(ents['info'])) if 'info' in ents else '1'
            if 'text' in ents and flag == '3':
                return 'encrypted', None
            if 'text' in ents and flag != '2':
                return 'text', text(ents['text'])
            if 'module' in ents and 'form' in ents:
                return 'ordinary form', text(ents['module'])
            if 'image' in ents:
                return 'image only', None
            return 'container:' + '+'.join(sorted(ents)), None
        if kind == 'FormModule':
            t = text(b)
            tree_items = _top_items(t)
            if len(tree_items) >= 3 and tree_items[1][0] == 'node' and tree_items[2][0] == 'str':
                return 'managed form', tree_items[2][1]
            return 'form without module', None
        if b[:3] == b'\xef\xbb\xbf':
            return 'plain text', text(b)
        return 'binary', None

    def modules(self, with_text=True):
        for name in sorted(self.src.files):
            m = re.fullmatch('(' + G + r')\.([0-9a-f]{1,2})', name)
            if not m:
                continue
            u, suf = m.groups()
            it = self.items.get(u)
            if not it:
                continue
            kind = MODULE.get((it.cls, suf))
            if not kind:
                continue
            fmt, txt = self.module_text(name, kind) if with_text else ('', None)
            yield Module(name, it.path, kind, fmt, txt)

    # ------------------------------------------------------------------ typed fields
    def trees(self):
        if self._trees is None:
            self._trees = [(self.items[u], parse_brace(self._texts[u])) for u in self.top]
        return self._trees

    def types(self):
        if self._types is None:
            types = dict(PLATFORM)
            for it, tree in self.trees():
                for (c, cat), path in GEN_POS.items():
                    if c != it.cls:
                        continue
                    tid = at(tree, path)
                    if isinstance(tid, str) and GUID.match(tid):
                        if cat in ('DefinedType', 'Characteristic'):
                            types[tid] = ('TypeSet', '%s.%s' % (cat, it.name))
                        else:
                            types[tid] = ('Type', '%s%s.%s' % (SINGULAR.get(it.cls, it.cls), cat, it.name))
            self._types = types
        return self._types

    def decode(self, pat):
        types, out = self.types(), []
        for t in pat[1:]:
            if not isinstance(t, list) or not t:
                continue
            k = unq(t[0])
            if k == 'B':
                out.append(('Boolean', None))
            elif k == 'S':
                out.append(('String', (t[1], 'Variable' if t[2] == '1' else 'Fixed') if len(t) > 2 else ('0', 'Variable')))
            elif k == 'N':
                out.append(('Number', (t[1], t[2], 'Nonnegative' if len(t) > 3 and t[3] == '1' else 'Any')))
            elif k == 'D':
                out.append(('Date', {'"D"': 'Date', '"T"': 'Time'}.get(t[1], 'DateTime') if len(t) > 1 else 'DateTime'))
            elif k == '#':
                out.append(types.get(t[1], ('Unknown', t[1])))
            else:
                out.append(('Unknown', repr(t)[:60]))
        return out

    def fields(self):
        for it, tree in self.trees():
            # a defined type or a chart of characteristic types borrowed by an extension keeps a default type there
            # (a borrowed constant keeps its real one)
            no_own_type = it.cls in ('DefinedTypes', 'ChartsOfCharacteristicTypes') and self.adopted(tree)
            if it.cls == 'ChartsOfCharacteristicTypes' and not no_own_type:     # value type of the chart sits in the header
                pat = next((x for x in at(tree, (1,)) or [] if isinstance(x, list) and x and x[0] == '"Pattern"'), None)
                if pat:
                    yield Field(it.path, 'Type', '', it.name, it.uuid, self.decode(pat))
            for coll, ctx, fu, fname, pat in typed_fields(tree):
                if no_own_type and coll is None:
                    continue
                kind = KIND.get(coll, 'Type' if coll is None else 'Field')
                yield Field(it.path, kind, '.'.join(ctx), fname, fu, self.decode(pat))


_TOK = re.compile(r'"[^"]*(?:""[^"]*)*"|[{}]|[^,{}"\s][^,{}"\r\n]*')


def _top_items(t, limit=3):
    """first items of the root brace list: ('node', None) | ('str', text) | ('atom', text)"""
    items, depth = [], 0
    for m in _TOK.finditer(t):
        s = m.group(0)
        if s == '{':
            depth += 1
            if depth == 2:
                items.append(('node', None))
        elif s == '}':
            depth -= 1
            if depth == 0:
                break
        elif depth == 1:
            items.append(('str', s[1:-1].replace('""', '"')) if s[0] == '"' else ('atom', s))
        if len(items) >= limit and depth == 1:
            break
    return items


def show_type(ts):
    parts = []
    for k, v in ts:
        if k == 'String':
            parts.append('String(%s)' % ('unlimited' if v[0] == '0' else v[0] + ('' if v[1] == 'Variable' else ',Fixed')))
        elif k == 'Number':
            parts.append('Number(%s,%s%s)' % (v[0], v[1], ',Nonnegative' if v[2] == 'Nonnegative' else ''))
        elif k == 'Date':
            parts.append(v)
        elif k == 'Boolean':
            parts.append('Boolean')
        elif k == 'Type':
            parts.append(v)
        else:
            parts.append('%s:%s' % (k, v))
    return ', '.join(parts)


def export_path(mod):
    """module -> relative path in the layout of an XML dump (Catalogs/X/Ext/ObjectModule.bsl ...)"""
    parts = [] if mod.path == 'Configuration' else mod.path.split('.')
    if mod.kind == 'FormModule':
        return os.path.join(*(parts + ['Ext', 'Form', 'Module.bsl']))
    return os.path.join(*(parts + ['Ext', mod.kind + '.bsl']))


# ---------------------------------------------------------------------------------------------------- object properties
# Positions of object properties are learned against XML dumps by learn_props.py, per class and per format version
# of the object description (one configuration can hold objects saved by several platform generations).
_PROPS = None
MDREF = '157fa490-4ce9-11d4-9415-008048da11f9'      # serialized "reference to a metadata object"
FIELD_KIND = {'Attribute': 'Attributes', 'Dimension': 'Dimensions', 'Resource': 'Resources', 'AddressingAttribute': 'AddressingAttributes',
              'AccountingFlag': 'AccountingFlags', 'ExtDimensionAccountingFlag': 'ExtDimensionAccountingFlags'}
SKIP_PROPS = {'Name'}


def prop_tables():
    """learned places (props_tables.json, or $CFGREAD_PROPS) with props_manual.json over them: places the learner
    has too few objects for, found against XML and a synthetic configuration"""
    global _PROPS
    if _PROPS is None:
        here = os.path.dirname(os.path.abspath(__file__))
        p = os.environ.get('CFGREAD_PROPS') or os.path.join(here, 'props_tables.json')
        _PROPS = json.load(open(p, encoding='utf-8')) if os.path.isfile(p) else {}
        m = os.path.join(here, 'props_manual.json')
        if os.path.isfile(m):
            for cls, props in json.load(open(m, encoding='utf-8')).items():
                if not cls.startswith('_'):
                    _PROPS.setdefault(cls, {}).update(props)
    return _PROPS


def _md_ref(node, names):
    if isinstance(node, list) and len(node) >= 3 and node[0] == '"#"' and node[1] == MDREF and isinstance(node[2], list) and len(node[2]) > 1:
        return names.get(node[2][1], node[2][1])
    return None


def _decode(d, tree, path, names, comp=None, owner=None):
    if d['kind'] in ('fields', 'characteristics'):      # lists of fields and characteristics: v8comp
        from v8comp import decode_fields, decode_characteristics
        node = at(tree, path)
        v = (decode_fields if d['kind'] == 'fields' else decode_characteristics)(comp, owner, node) if node is not None else None
        return (v, True) if v is not None else (None, False)
    if d['kind'] == 'method':
        base = tuple(path[:-1])
        u = at(tree, base)
        m = at(tree, base[:-1] + (base[-1] + 1,))
        if not isinstance(u, str) or not isinstance(m, str):
            return None, False
        return ('' if u == '00000000-0000-0000-0000-000000000000' else '%s.%s' % (names.get(u, u), unq(m))), True
    node = at(tree, path)
    if node is None:
        return None, False
    if d['kind'] == 'list':
        if not (isinstance(node, list) and len(node) >= 2 and node[1].isdigit()):
            return None, False
        return [names.get(x[2][1], x[2][1]) for x in node[2:] if isinstance(x, list) and len(x) >= 3 and x[1] == MDREF], True
    if d['kind'] == 'ref':
        if isinstance(node, list):
            r = _md_ref(node, names)
            return (r, True) if r is not None else (None, False)
        return ('' if node == '00000000-0000-0000-0000-000000000000' else names.get(node, node)), True
    if isinstance(node, list):
        return None, False
    c = d['codec']
    if c is None:
        return node, True
    if c == 'str':
        return unq(node), True
    if c == 'prefix':
        return unq(node).split('_')[0], True
    return (c[node], True) if node in c else ('?' + node, True)


def _ref_names(self):
    if getattr(self, '_names', None) is None:
        names = {u: it.path for u, it in self.items.items()}
        for f in self.fields():
            kind = FIELD_KIND.get(f.kind)
            if kind:
                names[f.uuid] = ('%s.TabularSections.%s.Attributes.%s' % (f.obj, f.path, f.name)) if f.path else '%s.%s.%s' % (f.obj, kind, f.name)
        self._names = names
    return self._names


def _adopted(self, tree):
    """an object an extension borrows from the configuration: the extension stores its name and the link to the
    extended object ({3,{…},"Name",{…},"",1,…} in the name block, 0 for an own object); every other property keeps
    its default value there"""
    if self.root_name != 'configinfo':
        return False
    nb = find_name_block(tree)
    return bool(nb) and len(nb) > 9 and nb[5] == '1'


def _properties(self, it, tree):
    """[(property, value, how)] for a top-level object; how: 'version' (position learned for this format version)
    or 'assumed' (version not seen in learning, but every learned version keeps the property at the same place).
    An object borrowed by an extension gets ObjectBelonging Adopted and only its non-empty lists, how 'extension':
    they name just the objects the extension holds (owners, movements); its other values are mere defaults."""
    adopted = self.adopted(tree)
    tab = prop_tables().get(it.cls, {})
    ver = tree[1][0] if isinstance(tree[1], list) and tree[1] and isinstance(tree[1][0], str) else 'x'
    names = self.ref_names()
    comp = None
    out = [('ObjectBelonging', 'Adopted', 'version')] if adopted else []
    for prop, d in sorted(tab.items()):
        if d['kind'] in ('fields', 'characteristics') and comp is None:
            comp = self.comp_context()
        if prop in SKIP_PROPS or (adopted and d['kind'] != 'list'):
            continue
        path, how = d['paths'].get(ver), 'version'
        if path is None:
            # a version never seen in learning: use the common place only if every learned version agrees on it;
            # versions where learning saw that place fail are refused outright
            if ver in d.get('refused_versions', ()) or len({tuple(p) for p in d['paths'].values()}) != 1:
                continue
            path, how = d['default_path'], 'assumed'
        value, ok = _decode(d, tree, path, names, comp, it.path)
        if ok and not adopted:
            out.append((prop, value, how))
        elif ok and value:
            out.append((prop, value, 'extension'))
    return out


def _comp_context(self):
    """names of fields, tabular sections and predefined items for composite properties (v8comp), built once"""
    if getattr(self, '_comp', None) is None:
        from v8comp import Context
        self._comp = Context(self)
    return self._comp


Configuration.ref_names = _ref_names
Configuration.adopted = _adopted
Configuration.comp_context = _comp_context
Configuration.properties = _properties


def show_value(v):
    if isinstance(v, list):                  # characteristics read better one per line: joined by '; '
        return ('; ' if any(' | ' in x for x in v if isinstance(x, str)) else ', ').join(x or '' for x in v)
    return '' if v is None else str(v)
