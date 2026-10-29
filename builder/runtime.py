"""Custom live app schema shared with dev kit v3. Regenerate from mooboard/live.py when its schema changes."""
import json
import re
import struct
import zlib
import unicodedata
from pathlib import Path
from types import SimpleNamespace

_categories=()
package=None

def categories():
    return _categories

def _plain(value):
    if isinstance(value,str):
        try:value.encode("utf-8")
        except UnicodeError:return False
        return not any(unicodedata.category(c).startswith("C") for c in value)
    if isinstance(value,list):return all(_plain(v) for v in value)
    if isinstance(value,dict):return all(_plain(k) and _plain(v) for k,v in value.items())
    return True

ORDER = ('format', 'id', 'name', 'version', 'by', 'description', 'category', 'runtime', 'font', 'minFirmware', 'boards', 'settings', 'controls', 'sources')
SETTING_ORDER = ('key', 'type', 'label', 'default', 'max', 'options')
CONTROL_ORDER = ('key', 'type', 'label', 'arg', 'min', 'max', 'chars', 'add')
SOURCE_ORDER = ('key', 'url', 'refresh', 'headers')
KEY = re.compile('[a-z][a-z0-9_]{0,15}\\Z')
TOKEN = re.compile('\\{(settings|secrets)\\.([a-z][a-z0-9_]{0,15})\\}')
VERSION = re.compile('\\d+\\.\\d+\\.\\d+(?:-[0-9A-Za-z.-]+)?\\Z')
CAP = 352 * 1024

def text(value, maximum):
    return isinstance(value, str) and bool(value.strip()) and (len(value) <= maximum) and package._plain(value)

def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise package.Refused('Duplicate manifest field: ' + key)
        result[key] = value
    return result

def refuse(condition, message):
    if condition:
        raise package.Refused(message)

def check(man):
    refuse(not isinstance(man, dict), 'The live manifest must be an object')
    refuse(set(man) - set(ORDER), 'Unknown live manifest field')
    refuse(type(man.get('format')) is not int or man['format'] != 3, 'A custom live app uses format 3')
    refuse(not isinstance(man.get('id'), str) or not re.fullmatch('[a-z0-9-]{3,32}', man['id']), 'App id must be 3 to 32 letters, numbers and hyphens')
    refuse(man['id'] in package.RESERVED_IDS, 'Choose your own app id')
    for field, limit in (('name', 24), ('by', 32), ('description', 160)):
        refuse(not text(man.get(field), limit), '%s must be 1 to %d plain characters' % (field, limit))
    for field in ('version', 'minFirmware'):
        refuse(not isinstance(man.get(field), str) or not VERSION.fullmatch(man[field]), field + ' must be a semantic version')
    refuse(man.get('runtime') != 'lua54', 'The live runtime is lua54')
    refuse('font' in man and (not (isinstance(man['font'], str) and re.fullmatch('[a-z0-9-]{1,32}', man['font']))), 'font is a family name such as inter')
    refuse(man.get('category') not in categories(), 'Use a current store category: ' + ', '.join(categories()))
    boards = man.get('boards', ['s3', 'p4'])
    refuse(boards not in (['s3'], ['p4'], ['s3', 'p4']), 'Boards must be s3, p4, or both in that order')
    settings = man.get('settings', [])
    refuse(not isinstance(settings, list) or len(settings) > 8, 'An app has at most 8 settings')
    seen = set()
    for setting in settings:
        refuse(not isinstance(setting, dict) or set(setting) - set(SETTING_ORDER), 'Invalid setting fields')
        key, kind, default = (setting.get('key'), setting.get('type'), setting.get('default'))
        refuse(not isinstance(key, str) or not KEY.fullmatch(key) or key in seen, 'Setting keys must be unique')
        seen.add(key)
        refuse(not text(setting.get('label'), 24), 'A setting needs a label of at most 24 characters')
        if kind == 'text':
            maximum = setting.get('max')
            refuse(type(maximum) is not int or not 1 <= maximum <= 256 or (not text(default, maximum)), 'A text setting needs a default and max of 1 to 256')
        elif kind == 'toggle':
            refuse(type(default) is not bool, 'A toggle default must be true or false')
        elif kind == 'color':
            refuse(not isinstance(default, str) or not re.fullmatch('#[0-9a-fA-F]{6}', default), 'A color default must be #rrggbb')
        elif kind == 'choice':
            options = setting.get('options')
            refuse(not isinstance(options, list) or not 2 <= len(options) <= 8 or any((not text(v, 16) for v in options)), 'A choice needs 2 to 8 options')
            refuse(len(set(options)) != len(options) or default not in options, 'A choice needs unique options and a matching default')
        else:
            raise package.Refused('Setting types are text, toggle, color and choice')
        allowed = {'key', 'type', 'label', 'default'} | ({'max'} if kind == 'text' else {'options'} if kind == 'choice' else set())
        refuse(set(setting) != allowed, 'A setting has fields for another type')
    controls = man.get('controls', [])
    refuse(not isinstance(controls, list) or len(controls) > 16, 'An app has at most 16 controls')
    seen_controls = set()
    for control in controls:
        refuse(not isinstance(control, dict) or set(control) - set(CONTROL_ORDER), 'Invalid control fields')
        key, kind = (control.get('key'), control.get('type'))
        refuse(not isinstance(key, str) or not KEY.fullmatch(key) or key in seen_controls, 'Control keys must be unique')
        seen_controls.add(key)
        refuse(kind not in ('button', 'stepper', 'readout', 'list'), 'Unknown control type')
        refuse(not text(control.get('label'), 24), 'A control needs a label')
        allowed = {'key', 'type', 'label'} | ({'arg'} if kind == 'button' and 'arg' in control else {'min', 'max'} if kind == 'stepper' else {'max', 'chars', 'add'} if kind == 'list' else set())
        refuse(set(control) != allowed, 'A control has fields for another type')
        for field in re.findall('\\{([^{}]+)\\}', control['label']):
            refuse(not any((s['key'] == field and s['type'] == 'text' for s in settings)), 'Control labels refer only to text settings')
        if kind == 'stepper':
            low, high = (control.get('min'), control.get('max'))
            refuse(type(low) is not int or type(high) is not int or (not -99999 <= low < high <= 99999), 'A stepper needs min and max')
        if kind == 'button' and 'arg' in control:
            refuse(type(control['arg']) is not int or not 0 <= control['arg'] <= 86400, 'Button arg must be 0 to 86400')
        if kind == 'list':
            refuse(type(control.get('max')) is not int or not 1 <= control['max'] <= 8 or type(control.get('chars')) is not int or (not 1 <= control['chars'] <= 16) or (not text(control.get('add'), 24)), 'A list needs max, chars and add')
    sources = man.get('sources', [])
    refuse(not isinstance(sources, list) or len(sources) > 4, 'An app has at most 4 data sources')
    seen_sources = set()
    for source in sources:
        refuse(not isinstance(source, dict) or set(source) - set(SOURCE_ORDER), 'Invalid source fields')
        key, url, refresh = (source.get('key'), source.get('url'), source.get('refresh'))
        refuse(not isinstance(key, str) or not KEY.fullmatch(key) or key in seen_sources, 'Data source keys must be unique')
        seen_sources.add(key)
        refuse(not isinstance(url, str) or not 1 <= len(url) <= 512 or (not package._plain(url)), 'A source needs a URL or a setting placeholder')
        for group, field in TOKEN.findall(url):
            refuse(group != 'settings' or field not in seen, 'Source URLs may refer only to declared settings')
        sample = TOKEN.sub('sample', url)
        refuse('{' in sample or '}' in sample, 'Invalid source URL placeholder')
        refuse(not (url.startswith('https://') or re.fullmatch('\\{settings\\.[a-z][a-z0-9_]{0,15}\\}', url)), 'Sources use HTTPS')
        refuse(type(refresh) is not int or not 15 <= refresh <= 86400, 'Source refresh must be 15 to 86400 seconds')
        headers = source.get('headers', {})
        refuse(not isinstance(headers, dict) or len(headers) > 4, 'A source has at most 4 headers')
        for key, value in headers.items():
            refuse(not re.fullmatch('[A-Za-z][A-Za-z0-9-]{0,47}', key) or key.lower() in ('host', 'content-length', 'connection', 'cookie'), 'Unsupported source header')
            refuse(not isinstance(value, str) or len(value) > 512 or (not package._plain(value)), 'Invalid source header value')
            refuse(not TOKEN.search(value), 'Put API credentials in local secrets, never in the package')
            for group, field in TOKEN.findall(value):
                refuse(group == 'settings' and field not in seen, 'Header settings must be declared')
            sample = TOKEN.sub('sample', value)
            refuse('{' in sample or '}' in sample, 'Invalid source header placeholder')
    return man

def canonical(man):
    result = {key: man[key] for key in ORDER if key in man}
    for field, order in (('settings', SETTING_ORDER), ('controls', CONTROL_ORDER), ('sources', SOURCE_ORDER)):
        if field in result:
            result[field] = [{key: item[key] for key in order if key in item} for item in result[field]]
    return (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

def zip_bytes(entries):
    local, central = (bytearray(), bytearray())
    for name, body in entries:
        encoded = name.encode('ascii')
        crc, size, offset = (zlib.crc32(body), len(body), len(local))
        local.extend(struct.pack('<I5H3I2H', 67324752, 10, 0, 0, 0, 33, crc, size, size, len(encoded), 0) + encoded + body)
        central.extend(struct.pack('<I6H3I5H2I', 33639248, 788, 10, 0, 0, 0, 33, crc, size, size, len(encoded), 0, 0, 0, 0, 33188 << 16, offset) + encoded)
    return bytes(local + central + struct.pack('<I4H2IH', 101010256, 0, 0, len(entries), len(entries), len(central), len(local), 0))

def load(base,category,build):
    global package,_categories
    _categories=build.CATEGORIES
    package=SimpleNamespace(Refused=build.Refused,RESERVED_IDS=tuple(build.USES)+("countdowns","messages","sports","ambiance","lua54"),_plain=_plain)
    folder=Path(base)
    allowed={"mooboard.json","app.lua","icon.png","sample-data.json","README.md","LICENSE","listing"}
    for path in folder.iterdir():
        if path.name.startswith("."):continue
        if path.name not in allowed or path.is_symlink():raise build.Refused("unexpected live app file: "+path.name)
    try:
        manifest=check(json.loads((folder/"mooboard.json").read_text(encoding="utf-8"),object_pairs_hook=unique))
        if manifest["category"]!=category:raise build.Refused("category must match its store folder")
        source=(folder/"app.lua").read_bytes()
        if not 0<len(source)<=65536 or source[:1]==b"\x1b":raise build.Refused("live apps require text source of at most 64 KB")
        source.decode("utf-8")
        icon=(folder/"icon.png").read_bytes() if (folder/"icon.png").exists() else default_icon()
        build.check_icon(icon,"icon.png")
        body=zip_bytes((("mooboard.json",canonical(manifest)),("app.lua",source),("icon.png",icon)))
        if len(body)>CAP:raise build.Refused("live package exceeds 352 KB")
        row=dict(manifest,uses="lua54")
        return row,icon,body,manifest.get("boards",["s3","p4"]),3,None
    except (OSError,UnicodeError,ValueError,KeyError,TypeError) as error:
        raise build.Refused(str(error)) from error

def default_icon():
    def chunk(kind,data):return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data))
    rows=(b"\0"+bytes((119,237,215))*32)*32
    return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",32,32,8,2,0,0,0))+chunk(b"IDAT",b"\x78\x01\x01"+struct.pack("<HH",len(rows),len(rows)^0xffff)+rows+struct.pack(">I",zlib.adler32(rows)))+chunk(b"IEND",b"")
