"""GUI executable entry point and noninteractive installation diagnostic."""
import argparse
import json
import os
from pathlib import Path
import sys
import traceback

if not getattr(sys,'frozen',False):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from tools.app_paths import app_root,local_root
from tools.version import APP_NAME,APP_VERSION


def self_test(report):
    import tkinter as tk
    import PIL
    from PIL import Image,ImageDraw,ImageFont
    import numpy
    from tools.live.data_paths import active_pack
    from tools.live.source_cards import SourceReader
    from tools.live.offer_reader import load_names
    from tools.items.static_sets import load_export
    from tools.live.ocr_session import OcrSession
    from tools.items.import_sets import Importer
    result={'app':APP_NAME,'version':APP_VERSION,'frozen':bool(getattr(sys,'frozen',False)),
            'python':sys.version.split()[0],'application_dir':str(app_root()),'user_dir':str(local_root())}
    try:
        from tools.app_identity import set_app_id,apply_icon,icon_path
        set_app_id()
        window=tk.Tk();window.withdraw()
        apply_icon(window)
        with Image.open(icon_path()) as app_icon:
            result['app_icon']=app_icon.format=='ICO' and (32,32) in app_icon.info['sizes']
        if not result['app_icon']:raise RuntimeError('Invalid application icon')
        result['tk']=window.tk.call('info','patchlevel')
        window.destroy()
        result['Pillow']=PIL.__version__;result['numpy']=numpy.__version__
        if result['frozen']:
            bundle=Path(sys._MEIPASS).resolve()
            if not all(Path(m.__file__).resolve().is_relative_to(bundle) for m in (PIL,numpy)):
                raise RuntimeError('Dependency resolved outside the executable bundle')
        pack=active_pack(app_root())
        if pack is None:
            raise RuntimeError('Missing installed data pack')
        folder,manifest=pack
        result['data_generation']=manifest['generation']
        reader=SourceReader(app_root(),runtime_directory=folder)
        try:
            result['card_read']=reader.read(18,3078)['champion_id']==18
            result['combo_read']=bool(reader.read(17,3086,[1030,1098])['combo_evidence']['observed'])
        finally:
            reader.close()
        result['recognized_names']=len(load_names(app_root()))
        from tools.launcher.state import ChampionData
        launcher = ChampionData(app_root())
        result['launcher_champions']=len(launcher.champions)
        result['launcher_spells']=bool(launcher.spells(103))
        from tools.launcher.portraits import Portraits
        portrait_root=tk.Tk();portrait_root.withdraw()
        try:
            portraits=Portraits(app_root(),portrait_root)
            if portraits.zipped is None:raise RuntimeError('Missing champion portraits')
            result['champion_portraits']=len(portraits.manifest['portraits'])
            result['portrait_render']=portraits.photo(103,64).width()==64
            required_spells={i for c in launcher.champions.values() for row in launcher.spells(c['id']) for i in row['ids']}
            result['summoner_icons']=len(portraits.manifest.get('spells',{}))
            if not {str(i) for i in required_spells}<=portraits.manifest.get('spells',{}).keys():
                raise RuntimeError('Incomplete summoner spell icons')
            result['spell_render']=all(portraits.spell_photo(i,28).width()==28 for i in required_spells)
            portraits.close()
        finally:portrait_root.destroy()
        if result['champion_portraits']!=173 or not result['portrait_render']:
            raise RuntimeError('Incomplete champion portraits')
        if result['launcher_champions']!=173 or not result['launcher_spells']:
            raise RuntimeError('Incomplete launcher data')
        bundle,_=load_export(app_root())
        result['item_sets']=len(bundle['itemSets'])
        result['champions']=len({s['associatedChampions'][0] for s in bundle['itemSets']})
        if result['champions']!=manifest['champions'] or not result['card_read'] or not result['combo_read']:
            raise RuntimeError('Incomplete installed data')
        importer=Importer(bundle)
        if result['frozen'] and importer.folder.is_relative_to(app_root()):
            raise RuntimeError('User backups resolve inside the installation')
        temporary=local_root()/'diagnostics'
        temporary.mkdir(parents=True,exist_ok=True)
        image=Image.new('RGB',(1920,1080),'white')
        font=ImageFont.truetype(str(Path(os.environ.get('SystemRoot','C:/Windows'))/'Fonts/arial.ttf'),40)
        ImageDraw.Draw(image).text((100,100),'TESTE CARTINHA',font=font,fill='black')
        path=temporary/'ocr-self-test.bmp';image.save(path)
        session=OcrSession()
        try:
            screen=session.recognize(path)
        finally:
            session.close()
        result['ocr_status']=screen.get('ocr_status')
        if screen.get('ocr_status')!='recognized':
            raise RuntimeError('Windows OCR is unavailable: '+str(screen.get('ocr_error','unknown error')))
        text=' '.join(line.get('text','') for line in screen.get('ocr_lines',[])).upper()
        result['synthetic_ocr_read']='CARTINHA' in text
        if not result['synthetic_ocr_read']:
            raise RuntimeError('Windows OCR did not read the synthetic test text')
        result['ok']=True
    except Exception as error:
        result.update(ok=False,error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc())
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return 0 if result['ok'] else 1


def main():
    if '--self-test' in sys.argv:
        parser=argparse.ArgumentParser()
        parser.add_argument('--self-test',action='store_true')
        parser.add_argument('--report',type=Path,default=local_root()/'diagnostics/self-test.json')
        args=parser.parse_args()
        return self_test(args.report)
    if '--version' in sys.argv:
        if sys.stdout is not None:
            print(APP_VERSION)
        return 0
    try:
        from tools.live.debug_overlay import main as overlay_main
        overlay_main()
        return 0
    except Exception:
        folder=local_root();folder.mkdir(parents=True,exist_ok=True)
        log=folder/'startup-error.log'
        with log.open('a',encoding='utf8') as stream:
            traceback.print_exc(file=stream)
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,'Não foi possível abrir o overlay.\nDetalhes em:\n'+str(log),APP_NAME,0x10)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
