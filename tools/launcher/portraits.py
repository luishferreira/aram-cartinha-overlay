"""Offline Riot portraits and read-only roster strips; all Tk images stay on the UI thread."""
import io
import json
from pathlib import Path
import sys
import tkinter as tk
import zipfile

from tools.live.data_paths import active_pack,resource

if not getattr(sys,'frozen',False):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'data/local/overlay-deps'))
from PIL import Image,ImageDraw,ImageTk


class Portraits:
    def __init__(self,root,master):
        self.master,self.cache,self.zipped=master,{},None
        pack=active_pack(root,verify_files=False)
        if pack and 'champion-portraits.zip' in pack[1]['files']:
            path=resource(root,'champion-portraits.zip','')
            self.zipped=zipfile.ZipFile(path)
            self.manifest=json.loads(self.zipped.read('manifest.json'))

    def photo(self,ident,size):
        key=(ident,size)
        if key not in self.cache:
            if self.zipped and str(ident) in self.manifest['portraits']:
                with Image.open(io.BytesIO(self.zipped.read(f'{ident}.png'))) as raw:
                    image=raw.convert('RGB').resize((size,size),Image.Resampling.LANCZOS)
            else:
                image=Image.new('RGB',(size,size),'#253247');draw=ImageDraw.Draw(image)
                draw.ellipse((size*.34,size*.14,size*.66,size*.46),fill='#60718b')
                draw.ellipse((size*.16,size*.50,size*.84,size*1.12),fill='#60718b')
            self.cache[key]=ImageTk.PhotoImage(image,master=self.master)
        return self.cache[key]

    def close(self):
        self.cache.clear()
        if self.zipped:self.zipped.close()

    def spell_photo(self,ident,size):
        key=('spell',ident,size)
        if key not in self.cache:
            if self.zipped and str(ident) in self.manifest.get('spells',{}):
                with Image.open(io.BytesIO(self.zipped.read(f'spell-{ident}.png'))) as raw:
                    image=raw.convert('RGB').resize((size,size),Image.Resampling.LANCZOS)
            else:
                image=Image.new('RGB',(size,size),'#253247')
                ImageDraw.Draw(image).text((size//3,size//5),'?',fill='#93a4bd')
            self.cache[key]=ImageTk.PhotoImage(image,master=self.master)
        return self.cache[key]

    def spell_name(self,ident):
        from tools.launcher.state import SPELLS
        return getattr(self,'manifest',{}).get('spells',{}).get(str(ident),{}).get('name',SPELLS.get(ident,str(ident)))


class PortraitStrip(tk.Frame):
    def __init__(self,parent,portraits,on_choose,*,size=52,team=False):
        super().__init__(parent,bg='#141d2a')
        self.portraits,self.on_choose,self.size,self.team=portraits,on_choose,size,team
        self.cards=[]
        self.canvas=tk.Canvas(self,bg='#141d2a',height=size+44,highlightthickness=0,borderwidth=0)
        self.canvas.pack(fill='x')
        self.inner=tk.Frame(self.canvas,bg='#141d2a')
        self.inner_id=self.canvas.create_window(0,0,window=self.inner,anchor='nw')
        self.scrollbar=tk.Scrollbar(self,orient='horizontal',command=self.canvas.xview,
                                    bg='#263449',troughcolor='#141d2a',width=10,relief='flat',borderwidth=0)
        self.canvas.configure(xscrollcommand=self.scrollbar.set)
        self.inner.bind('<Configure>',lambda e:self.layout())
        self.canvas.bind('<Configure>',lambda e:self.layout())
        self.canvas.bind('<MouseWheel>',lambda e:self.canvas.xview_scroll(-1 if e.delta>0 else 1,'units'))

    def layout(self):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        overflow=self.inner.winfo_reqwidth()>self.canvas.winfo_width()+1
        if overflow and not self.scrollbar.winfo_manager():self.scrollbar.pack(fill='x')
        elif not overflow and self.scrollbar.winfo_manager():self.scrollbar.pack_forget()

    def render(self,entries,selected):
        x=self.canvas.xview()[0]
        for child in self.inner.winfo_children():child.destroy()
        self.cards=[]
        if not entries:
            tk.Label(self.inner,text='O banco ainda está vazio.',bg='#141d2a',fg='#93a4bd',
                     font=('Segoe UI',10)).pack(pady=25,padx=8)
        for entry in entries:
            ident=entry['id'];is_self=entry.get('is_self',False)
            border='#7edbc4' if is_self else ('#89b5f7' if ident and ident==selected else '#263449')
            card=tk.Frame(self.inner,bg='#192536',highlightbackground=border,highlightthickness=2,
                          width=110 if self.team else 94,height=self.size+42)
            card.pack(side='left',padx=(0,8));card.pack_propagate(False)
            photo=self.portraits.photo(ident,self.size)
            portrait=tk.Label(card,image=photo,bg='#192536',borderwidth=0,cursor='hand2' if ident else 'arrow')
            portrait.pack(pady=(3,0))
            name=tk.Label(card,text=entry.get('name') or 'Sem campeão',bg='#192536',fg='#edf3ff',
                          font=('Segoe UI',9 if self.team else 8))
            name.pack()
            metrics=tk.Label(card,text=f'{entry.get("tier") or "—"} · {entry.get("win_rate") or "—"}',
                             bg='#192536',fg=entry.get('color','#93a4bd'),font=('Segoe UI',9))
            metrics.pack()
            badge=None
            if self.team and is_self:
                # Show ownership without moving this player out of their actual team slot.
                name.configure(fg='#7edbc4')
                badge=tk.Label(portrait,text='Você',bg='#7edbc4',fg='#0b1018',font=('Segoe UI',7,'bold'),padx=3)
                badge.place(relx=.5,rely=1,anchor='s')
            if ident:
                for widget in (card,portrait,name,metrics):
                    widget.bind('<Button-1>',lambda e,i=ident:self.on_choose(i))
                if badge:badge.bind('<Button-1>',lambda e,i=ident:self.on_choose(i))
            self.cards.append({'widget':card,'id':ident,'is_self':is_self,'metrics':metrics,'portrait':portrait})
        self.inner.update_idletasks();self.layout()
        self.canvas.xview_moveto(x)
