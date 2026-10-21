"""Retrieve the immutable, licensed WORLD-001 input; never install or download UE."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import urllib.request
import zipfile

URL='https://github.com/DavrosMTY/MonterreySANDBOX/releases/download/geo003-world001-3f5c050a07c6/MonterreyOpenWorld_GEO003_WORLD001.zip'
SHA256='9ddc39d80f91b86794629f24b836c74ae64defdfb1f0729143750fbf566def4e'
ARCHIVE_BYTES=69133118
PREFIX='MonterreyOpenWorld/Data/city/geo003_world001/'
PROBES='MonterreyOpenWorld/evidence/WORLD001/route/traversal_probes.json'


def extract_world(archive, output, expected_sha256=SHA256):
    archive=Path(archive);output=Path(output)
    if output.exists():raise FileExistsError('Refusing to overwrite input directory')
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected_sha256:raise ValueError('Release ZIP checksum mismatch')
    selected=[];total=0;destinations=set()
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if item.is_dir():continue
            if item.filename.startswith(PREFIX):relative='world/'+item.filename[len(PREFIX):]
            elif item.filename==PROBES:relative='traversal_probes.json'
            else:continue # Do not extract archived scripts or old repository files.
            path=PurePosixPath(relative)
            if path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative:
                raise ValueError('Unsafe ZIP path')
            if stat.S_ISLNK(item.external_attr>>16) or item.file_size>256*1024**2:raise ValueError('Unsafe ZIP entry')
            total+=item.file_size
            if total>512*1024**2 or relative in destinations:raise ValueError('Oversized or duplicate archive content')
            destinations.add(relative);selected.append((item,relative))
        if 'world/manifest.json' not in destinations or 'traversal_probes.json' not in destinations:
            raise ValueError('Incomplete WORLD-001 archive')
        output.mkdir(parents=True,exist_ok=False)
        for item,relative in selected:
            path=output/relative;path.parent.mkdir(parents=True,exist_ok=True)
            with z.open(item) as source,path.open('xb') as target:shutil.copyfileobj(source,target)
    receipt={'release_url':URL,'archive_sha256':expected_sha256,'files_extracted':len(selected),
        'world_directory':'world','probes':'traversal_probes.json','engine_downloaded':False}
    (output/'input-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--archive')
    a=p.parse_args()
    if Path(a.output).exists():p.error('Output directory already exists')
    if a.archive:print(json.dumps(extract_world(a.archive,a.output),indent=2));return
    with tempfile.TemporaryDirectory(prefix='ue001-download-') as directory:
        archive=Path(directory)/'world.zip';size=0
        request=urllib.request.Request(URL,headers={'User-Agent':'MonterreyOpenWorld-UE001'})
        with urllib.request.urlopen(request,timeout=120) as source,archive.open('xb') as target:
            while chunk:=source.read(1024**2):
                size+=len(chunk)
                if size>ARCHIVE_BYTES:raise ValueError('Release response exceeds pinned size')
                target.write(chunk)
        if size!=ARCHIVE_BYTES:raise ValueError('Release response is truncated')
        print(json.dumps(extract_world(archive,a.output),indent=2))


if __name__=='__main__':main()
