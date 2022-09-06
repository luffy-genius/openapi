from xml.etree import ElementTree as EleTree


def dict_to_xml(data):
    xml_list = ['<xml>']
    for k, v in data.items():
        if not v:
            continue

        if str(v).isdigit():
            xml_list.append('<{0}>{1}</{0}>'.format(k, v))
        else:
            xml_list.append('<{0}><![CDATA[{1}]]></{0}>'.format(k, v))
    xml_list.append('</xml>')
    return ''.join(xml_list)


def xml_to_dict(xml_string):
    try:
        return dict((child.tag, child.text) for child in EleTree.fromstring(xml_string))
    except EleTree.ParseError:
        return {}
