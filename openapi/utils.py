from json import dumps as json_dumps
from typing import Any
from xml.etree import ElementTree as EleTree


def dict_to_xml(data):
    xml_list = ['<xml>']
    for k, v in data.items():
        if not v:
            continue

        if str(v).isdigit():
            xml_list.append(f'<{k}>{v}</{k}>')
        else:
            xml_list.append(f'<{k}><![CDATA[{v}]]></{k}>')
    xml_list.append('</xml>')
    return ''.join(xml_list)


def xml_to_dict(xml_string):
    try:
        return dict((child.tag, child.text) for child in EleTree.fromstring(xml_string))
    except EleTree.ParseError:
        return {}


def encode_json(json: Any) -> str:
    return json_dumps(json, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
