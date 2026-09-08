#!/usr/bin/env python3
"""Create two local copy-on-write capture guests from a live libvirt snapshot.

The original guest keeps its new writable overlay. Never commit or rebase that
overlay into the shared base while capture guests still depend on it. Local XML
and disk paths stay outside Git; VM disks contain local data and are not media.
"""
import argparse
from pathlib import Path
import subprocess
import uuid
import xml.etree.ElementTree as ET


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--prefix', default='pixiu-video')
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    args.record.mkdir(parents=True, exist_ok=True)
    names = [args.prefix + '-b', args.prefix + '-c']
    existing = run('virsh', 'list', '--all', '--name').splitlines()
    if any(n in existing for n in names):
        raise RuntimeError('Capture guest already exists; inspect it instead of recreating')
    original = run('virsh', 'dumpxml', args.domain, '--inactive')
    tree = ET.fromstring(original)
    disk = tree.find("./devices/disk[@device='disk']")
    base = Path(disk.find('source').get('file'))
    target = disk.find('target').get('dev')
    overlay = args.directory / 'original-active.qcow2'
    if overlay.exists() or any((args.directory / (n + '.qcow2')).exists() for n in names):
        raise RuntimeError('Output disk exists; refusing to overwrite')
    (args.record / 'original-before.xml').write_text(original)
    run('virsh', 'snapshot-create-as', args.domain, args.prefix + '-base',
        '--disk-only', '--atomic', '--diskspec',
        f'{target},snapshot=external,file={overlay}')
    (args.record / 'original-after.xml').write_text(run('virsh', 'dumpxml', args.domain, '--inactive'))
    (args.record / 'RESTORE.txt').write_text(
        'The original guest uses original-active.qcow2. Keep its base and overlay.\n'
        'Do not blockcommit/rebase shared base while capture guests exist.\n'
        'Capture overlays are separate; original user data has not been reset.\n')
    for i, name in enumerate(names):
        clone_disk = args.directory / (name + '.qcow2')
        run('sudo', '-n', '/usr/bin/qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(base), str(clone_disk))
        run('sudo', '-n', 'chown', '--reference=' + str(base), str(clone_disk))
        clone = ET.fromstring(original)
        clone.attrib.pop('id', None)
        clone.find('name').text = name
        clone.find('uuid').text = str(uuid.uuid4())
        for tag in ('memory', 'currentMemory'):
            clone.find(tag).text = str(4 * 1024 * 1024)
        clone.find('vcpu').text = '4'
        clone.find('./cpu/topology').set('cores', '4')
        source = clone.find("./devices/disk[@device='disk']/source")
        source.set('file', str(clone_disk))
        nic = clone.find('./devices/interface')
        nic.find('mac').set('address', f'52:54:00:71:90:{i + 2:02x}')
        for label in list(clone.findall('seclabel')):
            clone.remove(label)
        graphic = clone.find('./devices/graphics')
        graphic.set('port', '-1')
        graphic.set('autoport', 'yes')
        xml = args.record / (name + '.xml')
        xml.write_text(ET.tostring(clone, encoding='unicode'))
        run('virsh', 'define', str(xml))
        print(name, 'defined; start explicitly after inspection', flush=True)


if __name__ == '__main__':
    main()
