"""Build a portable Windows app and per-user installer from a verified local data pack."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from tools.app_paths import app_root
from tools.live.data_paths import active_pack,file_hash
from tools.version import APP_VERSION


def build(compiler):
    root=app_root()
    folder,manifest=active_pack(root)
    output=root/'dist'/APP_VERSION
    if not output.resolve().is_relative_to((root/'dist').resolve()):
        raise ValueError('Build output must remain inside the project dist directory')
    output.mkdir(parents=True,exist_ok=True)
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm',
        '--distpath',str(output),'--workpath',str(root/'build/windows'),
        str(root/'packaging/windows/overlay.spec')],cwd=root,check=True)
    app=output/'AramCartinhaOverlay'
    runtime=app/'data/runtime'
    target=runtime/'runs'/manifest['generation']
    target.mkdir(parents=True,exist_ok=True)
    for name in [*manifest['files'],'manifest.json']:
        shutil.copyfile(folder/name,target/name)
    shutil.copyfile(root/'data/runtime/current.json',runtime/'current.json')
    shutil.copyfile(root/'packaging/windows/LEIA-ME.txt',app/'LEIA-ME.txt')
    shutil.copyfile(root/'packaging/windows/THIRD-PARTY-NOTICES.txt',app/'THIRD-PARTY-NOTICES.txt')
    shutil.copyfile(root/'assets/app.ico',app/'app.ico')
    # Preserve full upstream license texts along with their runtime binaries.
    for package in ('Pillow','numpy','PyInstaller'):
        distribution=importlib.metadata.distribution(package)
        for name in distribution.files or ():
            if not any(term in str(name).lower() for term in ('license','copying')):
                continue
            path=Path(distribution.locate_file(name))
            if not path.is_file() or path.suffix.lower() not in ('','.txt','.terms','.md','.rst'):
                continue
            relative=Path(str(name))
            if relative.is_absolute() or '..' in relative.parts:
                continue
            license_target=app/'licenses'/package/relative
            license_target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,license_target)
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    if not python_license.exists():
        raise RuntimeError('Missing Python runtime license')
    (app/'licenses/Python').mkdir(parents=True,exist_ok=True)
    shutil.copyfile(python_license,app/'licenses/Python/LICENSE.txt')
    # Fail if any accumulated local state could leak into a release.
    if (app/'data/local').exists():
        raise RuntimeError('Refusing to package local user data')
    metadata={'app_version':APP_VERSION,'data_generation':manifest['generation'],
              'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
              'source_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=root))}
    (app/'version.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf8')
    archive=output/f'AramCartinhaOverlay-{APP_VERSION}-Portable-x64.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as zipped:
        for path in sorted(app.rglob('*')):
            if path.is_file():
                zipped.write(path,path.relative_to(output))
    compiler=Path(compiler).resolve()
    subprocess.run([str(compiler),'/Qp',f'/DAppVersion={APP_VERSION}',
        f'/DAppSource={app}',f'/DBuildOutput={output}',str(root/'packaging/windows/installer.iss')],
        cwd=root,check=True)
    installer=output/f'AramCartinhaOverlay-{APP_VERSION}-Setup-x64.exe'
    artifacts=[archive,installer]
    (output/'SHA256SUMS.txt').write_text(''.join(f'{file_hash(p)}  {p.name}\n' for p in artifacts),encoding='ascii')
    result={**metadata,'artifacts':[{'path':str(p),'bytes':p.stat().st_size,'sha256':file_hash(p)} for p in artifacts]}
    (output/'build-manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iscc',type=Path,required=True)
    args=parser.parse_args()
    if sys.platform!='win32':
        parser.error('Build on Windows x64')
    build(args.iscc)


if __name__=='__main__':
    main()
