"""Remove speaker-note parts and their package references without altering slide art."""
from lxml import etree as ET

def remove_notes(blobs):
    removed={n for n in blobs if n.startswith(('ppt/notesSlides/','ppt/notesMasters/'))}
    changed=set(removed)
    for n in removed:del blobs[n]
    for name,data in list(blobs.items()):
        if not (name.endswith('.rels') or name in {'[Content_Types].xml','ppt/presentation.xml'}):
            continue
        root=ET.fromstring(data);dirty=False
        for node in list(root.iter()):
            local=ET.QName(node).localname
            if (local=='Relationship' and node.get('Type','').rsplit('/',1)[-1] in {'notesSlide','notesMaster'}) or (local=='Override' and node.get('PartName','').lstrip('/') in removed) or local=='notesMasterIdLst':
                node.getparent().remove(node);dirty=True
        if dirty:
            blobs[name]=ET.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
            changed.add(name)
    return sorted(changed)
