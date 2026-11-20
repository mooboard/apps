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

ORDER = ('format', 'id', 'name', 'version', 'by', 'description', 'category', 'runtime', 'font', 'minFirmware', 'boards', 'settings', 'controls', 'sources', 'complications')
SETTING_ORDER = ('key', 'type', 'label', 'default', 'max', 'options')
CONTROL_ORDER = ('key', 'type', 'label', 'arg', 'min', 'max', 'chars', 'add')
SOURCE_ORDER = ('key', 'url', 'refresh', 'headers', 'near')
COMPLICATION_ORDER = ('key', 'label', 'source', 'path', 'icon', 'format', 'decimals', 'change', 'size', 'refresh', 'levels')
IMAGE = re.compile('images/[a-z0-9-]{1,32}\\.png\\Z')
ICON_WORDS = 'A complication icon is a board icon or a 7 x 7 PNG in the package'
KEY = re.compile('[a-z][a-z0-9_]{0,15}\\Z')
TOKEN = re.compile('\\{(settings|secrets|place)\\.([a-z][a-z0-9_]{0,15})\\}')
VERSION = re.compile('\\d+\\.\\d+\\.\\d+(?:-[0-9A-Za-z.-]+)?\\Z')
CAP = 352 * 1024

def text(value, maximum):
    return isinstance(value, str) and bool(value.strip()) and (len(value) <= maximum) and package._plain(value)

def label(value, maximum):
    """the board's validLabel + plain text that holds no link"""
    return text(value, maximum) and '://' not in value

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
        refuse(not label(man.get(field), limit), '%s must be 1 to %d plain characters' % (field, limit))
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
        if kind == 'secret':
            maximum = setting.get('max')
            refuse(type(maximum) is not int or not 1 <= maximum <= 256 or 'default' in setting, 'A secret setting needs a max of 1 to 256 and no default')
        elif kind == 'text':
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
            raise package.Refused('Setting types are text, secret, toggle, color and choice')
        allowed = {'key', 'type', 'label'} | (set() if kind == 'secret' else {'default'}) | ({'max'} if kind in ('text', 'secret') else {'options'} if kind == 'choice' else set())
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
        refuse(not label(control.get('label'), 24), 'A control needs a label')
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
            refuse(type(control.get('max')) is not int or not 1 <= control['max'] <= 8 or type(control.get('chars')) is not int or (not 1 <= control['chars'] <= 16) or (not label(control.get('add'), 24)), 'A list needs max, chars and add')
    sources = man.get('sources', [])
    refuse(not isinstance(sources, list) or len(sources) > 4, 'An app has at most 4 data sources')
    seen_sources = set()
    for source in sources:
        refuse(not isinstance(source, dict) or set(source) - set(SOURCE_ORDER), 'Invalid source fields')
        key, url, refresh = (source.get('key'), source.get('url'), source.get('refresh'))
        refuse(not isinstance(key, str) or not KEY.fullmatch(key) or key in seen_sources, 'Data source keys must be unique')
        seen_sources.add(key)
        refuse(not isinstance(url, str) or not 1 <= len(url) <= 512 or (not package._plain(url)), 'A source needs a URL or a setting placeholder')
        secrets = {s['key'] for s in settings if s.get('type') == 'secret'}
        for group, field in TOKEN.findall(url):
            refuse(not (group == 'settings' and field in seen or (group == 'place' and field in ('lat', 'lon'))), 'Source URLs may refer only to declared settings, place.lat, and place.lon')
            refuse(field in secrets, 'A secret setting goes only in a header')
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
                refuse(group == 'place', "The board's place goes only in a source URL")
            sample = TOKEN.sub('sample', value)
            refuse('{' in sample or '}' in sample, 'Invalid source header placeholder')
        if 'near' in source:
            near = source['near']
            parts = near.split(',') if isinstance(near, str) and len(near) <= 40 and re.fullmatch('[-0-9.,]+', near) else []
            try:
                lat, lon, km = (float(p) for p in parts) if len(parts) == 3 else (None, None, None)
            except ValueError:
                lat = lon = km = None
            refuse(lat is None or not (-90 <= lat <= 90 and -180 <= lon <= 180 and (1 <= km <= 2000)), "A source's near is lat,lon,km with km 1 to 2000")
    complications = man.get('complications', [])
    refuse(not isinstance(complications, list) or len(complications) > 2, 'An app has at most 2 complications')
    seen_complications = set()
    for item in complications:
        refuse(not isinstance(item, dict) or set(item) - set(COMPLICATION_ORDER) or any((k not in item for k in ('key', 'label', 'source', 'path'))), 'A complication has a key, label, source, and path')
        key = item['key']
        refuse(not isinstance(key, str) or not KEY.fullmatch(key), 'A complication key is a lowercase name of at most 16 characters')
        refuse(key in seen_complications, 'Complication keys must be unique')
        seen_complications.add(key)
        refuse(not label(item['label'], 24), 'A complication needs a label of at most 24 characters')
        refuse(not complication.label_template(item['label'], settings), "A complication label names only the app's settings")
        refuse(not isinstance(item['source'], str) or item['source'] not in seen_sources, "A complication reads one of the app's sources")
        path = complication.path_template(item['path'], settings)
        refuse(path == 1, "A complication path names only the app's settings")
        refuse(path != 0, 'A complication path is keys and [n] indexes of at most 64 characters')
        if 'icon' in item:
            icon = item['icon']
            refuse(not isinstance(icon, str) or not (icon in complication.icons() or IMAGE.fullmatch(icon)), ICON_WORDS)
        refuse('format' in item and (not complication.valid_format(item['format'])), 'A complication format has one {value} and at most 16 bytes')
        refuse('decimals' in item and (type(item['decimals']) is not int or not 0 <= item['decimals'] <= 2), 'Complication decimals are 0 to 2')
        if 'levels' in item:
            levels = item['levels']
            good = isinstance(levels, list) and 2 <= len(levels) <= 12 and (len(levels) % 2 == 0) and all((type(levels[i]) is int and -1000000 <= levels[i] <= 1000000 and isinstance(levels[i + 1], str) and re.fullmatch('#[0-9a-fA-F]{6}', levels[i + 1]) for i in range(0, len(levels), 2)))
            refuse(not good or any((levels[i] >= levels[i + 2] for i in range(0, len(levels) - 2, 2))), 'Complication levels are 1 to 6 tops each with its "#rrggbb", the tops rising')
        if 'change' in item:
            change = complication.path_template(item['change'], settings) if item['change'] != '' else 2
            refuse(change == 1, "A complication path names only the app's settings")
            refuse(change != 0, "A complication change is a path as its value's is")
        refuse('size' in item and item['size'] not in ('small', 'wide'), 'A complication size is small or wide')
        refuse('refresh' in item and (type(item['refresh']) is not int or not 300 <= item['refresh'] <= 86400), 'A complication refresh is 300 to 86400 seconds')
    newer = any((k in item for item in complications for k in ('change', 'size', 'refresh'))) or any(('{' in str(item.get(k, '')) for item in complications for k in ('path', 'change', 'label'))) or any((s.get('type') == 'secret' for s in settings))
    floor = tuple((int(n) for n in man['minFirmware'].split('-')[0].split('.')))
    refuse(newer and floor < (0, 4, 4), 'Complication change, size, refresh, setting paths, and secret settings need minFirmware 0.4.4 or later')
    placed = any(('levels' in item for item in complications)) or any(('near' in s or '{place.' in str(s.get('url', '')) for s in sources))
    refuse(placed and floor < (0, 4, 4), "Complication levels, the board's place, and near need minFirmware 0.4.4 or later")
    return man

def canonical(man):
    result = {key: man[key] for key in ORDER if key in man}
    for field, order in (('settings', SETTING_ORDER), ('controls', CONTROL_ORDER), ('sources', SOURCE_ORDER), ('complications', COMPLICATION_ORDER)):
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
        if hasattr(build,"floor"):manifest["minFirmware"]=build.floor(manifest["minFirmware"])   # --floor
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

# a live app's complications as the dev kit's mooboard/complication.py reads them, for check() above: keys and [n]
# indexes, one {value} in a format, a path whose whole keys may name a text or choice setting, and the board's icons
_PATH_KEY = re.compile(r"[A-Za-z0-9_-]+")
_PATH_INDEX = re.compile(r"\[(0|[1-9][0-9]{0,2})\]")


def _valid_path(path):
    if not isinstance(path, str) or not path.isascii() or len(path) > 64:
        return False
    if path == "":
        return True
    at = 0
    while True:
        key = _PATH_KEY.match(path, at)
        if not key:
            return False
        at = key.end()
        while at < len(path) and path[at] == "[":
            index = _PATH_INDEX.match(path, at)
            if not index:
                return False
            at = index.end()
        if at == len(path):
            return True
        if path[at] != ".":
            return False
        at += 1


def _valid_format(words):
    if not isinstance(words, str) or len(words.encode("utf-8", "surrogatepass")) > 16:
        return False
    before, found, after = words.partition("{value}")
    return bool(found) and not any(ch in "{}" for ch in before + after)


def _path_template(path, settings):
    if not isinstance(path, str) or len(path) > 64:
        return 2
    declared = {s.get("key") for s in settings or [] if s.get("type") in ("text", "choice")}
    plain, at = "", 0
    while at < len(path):
        if path[at] == "}":
            return 2
        if path[at] != "{":
            plain += path[at]
            at += 1
            continue
        end = path.find("}", at)
        if end < 0:
            return 2
        group, dot, key = path[at + 1:end].partition(".")
        if not dot or group != "settings" or key not in declared:
            return 1
        if (at > 0 and path[at - 1] != ".") or (end + 1 < len(path) and path[end + 1] not in ".["):
            return 2
        plain += "a"
        at = end + 1
    return 0 if _valid_path(plain) else 2


def _label_template(label, settings):
    # u906 c7617 + every {...} of a complication's label is {settings.<key>} of a text or choice setting, no other brace
    declared = {s.get("key") for s in settings or [] if s.get("type") in ("text", "choice")}
    at = 0
    while at < len(label):
        if label[at] == "}":
            return False
        if label[at] != "{":
            at += 1
            continue
        ends = [i for i in (label.find("{", at + 1), label.find("}", at + 1)) if i >= 0]
        end = min(ends) if ends else -1
        if end < 0 or label[end] != "}":
            return False
        group, dot, key = label[at + 1:end].partition(".")
        if not dot or group != "settings" or key not in declared:
            return False
        at = end + 1
    return True


_ICONS = ("sun", "moon", "partSun", "cloud", "rain", "snow", "storm", "fog", "sunUp", "sunDown", "bar", "plane")
complication = SimpleNamespace(valid_path=_valid_path, valid_format=_valid_format, path_template=_path_template,
                               label_template=_label_template, icons=lambda: _ICONS)
