"""Normal desktop window for preparation; the game overlay remains a separate surface."""
import json
import os
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import ttk

from tools.app_paths import app_root,local_root
from tools.app_identity import set_app_id,apply_icon
from tools.items.static_sets import load_export
from tools.launcher.state import ChampionData,SelectionService,percent,import_status,tier_key
from tools.launcher.updates import UpdateService,install_after_exit
from tools.launcher.portraits import Portraits,PortraitStrip
from tools.launcher.spells import SpellPair
from tools.live.common import normalized
from tools.version import APP_VERSION

BG='#0b1018'; PANEL='#141d2a'; BORDER='#263449'; TEXT='#edf3ff'; MUTED='#93a4bd'; ACCENT='#7edbc4'
SOURCES={'ARAMKit':'aramkit','Mayhem.com':'arammayhem'}
TIER_COLORS={'S':'#f3cf7a','A':'#7edbc4','B':'#89b5f7','C':'#c5a4e5','D':'#b3bccb'}


class Launcher:
    def __init__(self,master,stop,on_exit,*,root=None,demo=False,on_overlay=None):
        self.stop,self.on_exit,self.demo = stop,on_exit,demo
        self.root = Path(root or app_root())
        self.data = ChampionData(self.root)
        self.bundle,self.manifest = load_export(self.root)
        self.service = SelectionService(stop,self.root,demo=demo)
        self.updates = UpdateService(self.root,demo=demo)
        set_app_id()
        self.window = tk.Toplevel(master)
        apply_icon(self.window)
        self.window.title('Aram Cartinha · Pré-jogo'+(' · SIMULAÇÃO' if demo else ''))
        self.window.geometry('1120x760')
        self.window.minsize(1000,680)
        self.window.configure(bg=BG)
        self.window.protocol('WM_DELETE_WINDOW',self.window.iconify)
        self.selected = None
        self.drawn = None
        self.previous_phase = None
        self.in_game = False
        self.previous_own = None
        self.source = tk.StringVar(value='ARAMKit')
        self.order = tk.StringVar(value='Tier')
        self.search = tk.StringVar()
        self.page = 'select'
        self.overlay_active = True
        self.on_overlay = on_overlay
        self.build()
        self.window.after(100,self.tick)
        if not demo:
            self.window.after(1500,lambda:self.updates.task('check'))

    def text(self,parent,text,size=10,color=TEXT,**kwargs):
        return tk.Label(parent,text=text,bg=parent.cget('bg'),fg=color,font=('Segoe UI',size),
                        anchor='w',justify='left',**kwargs)

    def button(self,parent,text,command,*,accent=False):
        return tk.Button(parent,text=text,command=command,bg=ACCENT if accent else '#233247',
                         fg=BG if accent else TEXT,activebackground='#36516b',activeforeground=TEXT,
                         relief='flat',borderwidth=0,padx=14,pady=8,font=('Segoe UI',10),cursor='hand2')

    def build(self):
        w=self.window
        header=tk.Frame(w,bg=BG,padx=24,pady=18);header.pack(fill='x')
        self.text(header,'CARTINHA',19,color=ACCENT).pack(side='left')
        self.text(header,'  /  ARAM MAYHEM',10,color=MUTED).pack(side='left',pady=(6,0))
        nav=tk.Frame(w,bg=BG,padx=24);nav.pack(fill='x')
        self.nav_buttons={}
        for key,label in [('select','Campeões'),('updates','Atualizações')]:
            button=self.button(nav,label,lambda page=key:self.set_page(page),accent=key=='select')
            button.pack(side='left',padx=(0,8));self.nav_buttons[key]=button
        self.button(nav,'Sair do app',self.on_exit).pack(side='right')
        if self.demo:
            self.text(nav,'SIMULAÇÃO',9,color='#f3cf7a').pack(side='right',padx=12)
        status=tk.Frame(w,bg=BG,padx=24,pady=12);status.pack(fill='x')
        self.connection=self.text(status,'',9,color=MUTED);self.connection.pack(side='left')
        self.import_badge=self.text(status,'',9,color=ACCENT)
        self.overlay_badge=self.text(status,'Overlay oculto · Ctrl+F8',9,color=MUTED)
        self.content=tk.Frame(w,bg=BG,padx=24,pady=12);self.content.pack(fill='both',expand=True)
        self.select_page=tk.Frame(self.content,bg=BG)
        self.update_page=tk.Frame(self.content,bg=PANEL,padx=26,pady=24)
        self.build_selection()
        self.build_updates()
        self.select_page.pack(fill='both',expand=True)

    def build_selection(self):
        self.portraits=Portraits(self.root,self.window)
        self.window.bind('<Destroy>',lambda e:self.portraits.close() if e.widget==self.window else None,add='+')
        self.browse_view=tk.Frame(self.select_page,bg=BG);self.browse_view.pack(fill='both',expand=True)
        left=tk.Frame(self.browse_view,bg=PANEL,padx=16,pady=14);left.pack(side='left',fill='both',expand=True,padx=(0,14))
        right=tk.Frame(self.browse_view,bg=PANEL,padx=18,pady=16,width=340);right.pack(side='right',fill='both');right.pack_propagate(False)
        self.pool_title=self.text(left,'Campeões',12);self.pool_title.pack(fill='x')
        controls=tk.Frame(left,bg=PANEL);controls.pack(fill='x',pady=12)
        self.text(controls,'Fonte',9,color=MUTED).pack(side='left',padx=(0,6))
        for variable,values,width in [(self.source,list(SOURCES),14),(self.order,['Tier','Win rate','Nome'],10)]:
            combo=ttk.Combobox(controls,textvariable=variable,values=values,state='readonly',width=width,style='Cartinha.TCombobox')
            combo.pack(side='left',padx=(0,10));combo.bind('<<ComboboxSelected>>',lambda e:self.redraw())
        search_box=tk.Frame(controls,bg='#233247');search_box.pack(side='left',fill='x',expand=True)
        self.search_entry=tk.Entry(search_box,textvariable=self.search,bg='#233247',fg=TEXT,
                                   insertbackground=TEXT,relief='flat',font=('Segoe UI',10),width=16)
        self.search_entry.pack(fill='x',padx=8,pady=4)
        self.search_placeholder=self.text(search_box,'Buscar campeão',10,color=MUTED)
        self.search_placeholder.configure(bg='#233247',cursor='xterm')
        self.search_placeholder.bind('<Button-1>',lambda e:self.search_entry.focus_set())
        self.search_entry.bind('<FocusIn>',lambda e:self.search_placeholder.place_forget())
        self.search_entry.bind('<FocusOut>',lambda e:self.search_changed())
        self.search_entry.bind('<Return>',self.search_champion)
        self.search.trace_add('write',self.search_changed)
        self.search_changed()
        style=ttk.Style(self.window);style.theme_use('clam')
        style.configure('Cartinha.TCombobox',fieldbackground='#233247',background=BORDER,
                        foreground=TEXT,arrowcolor=MUTED,bordercolor=BORDER)
        style.map('Cartinha.TCombobox',fieldbackground=[('readonly','#233247')],foreground=[('readonly',TEXT)])
        style.layout('Cartinha.Vertical.TScrollbar',[
            ('Vertical.Scrollbar.trough',{'sticky':'ns','children':[
                ('Vertical.Scrollbar.thumb',{'expand':1,'sticky':'nswe'})]})])
        style.configure('Cartinha.Vertical.TScrollbar',background='#50647d',troughcolor=PANEL,
                        bordercolor=PANEL,lightcolor='#50647d',darkcolor='#50647d',borderwidth=0,
                        width=10,gripcount=0,arrowsize=10)
        style.map('Cartinha.Vertical.TScrollbar',background=[('active','#7894b3'),('pressed','#89b5f7')])
        style.configure('Cartinha.Treeview',background=PANEL,fieldbackground=PANEL,foreground=TEXT,
                        rowheight=43,borderwidth=0,bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER,font=('Segoe UI',11))
        # A flat list: use the tree column for portraits, without an expander gutter.
        style.layout('Cartinha.Treeview.Item',[('Treeitem.padding',{'sticky':'nswe','children':[
            ('Treeitem.image',{'side':'left','sticky':''}),('Treeitem.text',{'side':'left','sticky':''})]})])
        style.configure('Cartinha.Treeview.Heading',background='#1c293b',foreground=MUTED,
                        font=('Segoe UI',9),relief='flat')
        style.map('Cartinha.Treeview',background=[('selected','#29485a')],foreground=[('selected',TEXT)])
        table_frame=tk.Frame(left,bg=PANEL);table_frame.pack(fill='both',expand=True)
        self.table=ttk.Treeview(table_frame,columns=('name','tier','wr','role'),show='tree headings',
                               style='Cartinha.Treeview',selectmode='browse',height=7)
        self.table.heading('#0',text='')
        self.table.column('#0',width=44,minwidth=44,stretch=False)
        for key,label,width in [('name','Campeão',190),('tier','Tier',55),('wr','Vitória',85),('role','',105)]:
            self.table.heading(key,text=label);self.table.column(key,width=width,stretch=(key=='name'),anchor='w')
        scrollbar=ttk.Scrollbar(table_frame,orient='vertical',command=self.table.yview,style='Cartinha.Vertical.TScrollbar')
        self.champion_scrollbar=scrollbar
        self.table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y');self.table.pack(fill='both',expand=True)
        for tier,color in TIER_COLORS.items():self.table.tag_configure(tier,foreground=color)
        self.table.bind('<<TreeviewSelect>>',self.choose)
        self.empty_results=self.text(left,'Nenhum resultado',10,color=MUTED)
        self.details_content=tk.Frame(right,bg=PANEL);self.details_content.pack(fill='both',expand=True)
        right=self.details_content
        self.focus_name=self.text(right,'',22);self.focus_name.pack(fill='x',pady=(0,10))
        self.focus_hint=SpellPair(right,self.portraits,size=22)
        self.source_rows=[]
        for source in SOURCES:
            label=self.text(right,'',11,wraplength=300);label.pack(fill='x',pady=3);self.source_rows.append((source,label))
        self.spell_rows=self.spell_table(right)
        self.text(right,'Caminhos de build',10,color=ACCENT).pack(fill='x',pady=(16,0))
        self.paths=self.text(right,'',10,wraplength=300);self.paths.pack(fill='x',pady=(8,0))
        self.build_draft()

    def spell_table(self,parent):
        frame=tk.Frame(parent,bg=PANEL);frame.pack(fill='x',pady=(16,0))
        frame.columnconfigure(0,weight=1)
        for col,title in enumerate(('Feitiços · ARAMKit','Escolha','Vitória')):
            self.text(frame,title,8,color=MUTED).grid(row=0,column=col,sticky='w',padx=(0,10),pady=(0,6))
        rows=[]
        for row in range(1,4):
            labels=[]
            for col in range(3):
                label=SpellPair(frame,self.portraits) if col==0 else self.text(frame,'',9)
                label.grid(row=row,column=col,sticky='w',padx=(0,10),pady=4)
                labels.append(label)
            rows.append(labels)
        return rows

    def build_draft(self):
        self.draft_view=tk.Frame(self.select_page,bg=BG)
        bench=tk.Frame(self.draft_view,bg=PANEL,padx=12,pady=8);bench.pack(fill='x',pady=(0,6))
        heading=tk.Frame(bench,bg=PANEL);heading.pack(fill='x',pady=(0,6))
        self.bench_title=self.text(heading,'BANCO DE CAMPEÕES',11);self.bench_title.pack(side='left')
        source=ttk.Combobox(heading,textvariable=self.source,values=list(SOURCES),state='readonly',
                            width=14,style='Cartinha.TCombobox')
        source.pack(side='right');source.bind('<<ComboboxSelected>>',lambda e:self.redraw())
        self.text(heading,'Fonte ',9,color=MUTED).pack(side='right')
        self.bench_strip=PortraitStrip(bench,self.portraits,self.choose_portrait,size=52)
        self.bench_strip.pack(fill='x')
        team=tk.Frame(self.draft_view,bg=PANEL,padx=12,pady=8);team.pack(fill='x',pady=(0,6))
        heading=tk.Frame(team,bg=PANEL);heading.pack(fill='x',pady=(0,6))
        self.text(heading,'SEU TIME',11).pack(side='left')
        self.team_strip=PortraitStrip(team,self.portraits,self.choose_portrait,size=64,team=True)
        self.team_strip.pack(fill='x')
        focus=tk.Frame(self.draft_view,bg=PANEL,padx=14,pady=10);focus.pack(fill='both',expand=True)
        left=tk.Frame(focus,bg=PANEL);left.pack(side='left',fill='both',expand=True,padx=(0,20))
        self.draft_name=self.text(left,'',19);self.draft_name.pack(fill='x')
        self.draft_hint=SpellPair(left,self.portraits,size=22)
        self.draft_metrics=self.text(left,'',10);self.draft_metrics.pack(fill='x')
        right=tk.Frame(focus,bg=PANEL);right.pack(side='right',fill='both')
        self.draft_spells=self.spell_table(right)

    def choose_portrait(self,ident):
        self.selected=ident
        self.redraw()
        self.render_select(self.service.snapshot())

    def build_updates(self):
        self.text(self.update_page,'Atualizações',22).pack(anchor='w')
        self.text(self.update_page,f'Instalado: {APP_VERSION}',11,color=MUTED).pack(anchor='w',pady=(8,24))
        self.update_message=self.text(self.update_page,'',12,wraplength=800);self.update_message.pack(anchor='w')
        self.update_button=self.button(self.update_page,'Verificar atualizações',self.update_action,accent=True)
        self.update_button.pack(anchor='w',pady=18)
        self.notes=self.text(self.update_page,'',10,color=MUTED,wraplength=900);self.notes.pack(fill='x',pady=12)

    def set_page(self,page):
        self.page=page
        for key,button in self.nav_buttons.items():
            button.configure(bg=ACCENT if key==page else '#233247',fg=BG if key==page else TEXT)
        self.select_page.pack_forget();self.update_page.pack_forget()
        (self.select_page if page=='select' else self.update_page).pack(fill='both',expand=True)

    def search_champion(self,event=None):
        self.redraw();self.render_select(self.service.snapshot())

    def search_changed(self,*args):
        if not self.search.get() and self.window.focus_get()!=self.search_entry:
            self.search_placeholder.place(x=8,rely=.5,anchor='w')
        else:self.search_placeholder.place_forget()
        self.redraw()

    def choose(self,event=None):
        rows=self.table.selection()
        if rows:self.selected=int(rows[0]);self.render_details()

    def redraw(self):
        self.drawn=None

    def render_details(self):
        c=self.data.champion(self.selected)
        if not c:
            self.details_content.pack_forget()
            return
        self.details_content.pack(fill='both',expand=True)
        snapshot=self.service.snapshot()
        current=c['id']==snapshot.get('champion_id')
        self.focus_name.configure(text=c['name'])
        hint=[i for i in snapshot.get('spells',[]) if i] if current else []
        self.focus_hint.set(hint)
        if hint:self.focus_hint.pack(fill='x',before=self.source_rows[0][1],pady=(0,10))
        else:self.focus_hint.pack_forget()
        for name,label in self.source_rows:
            source=SOURCES[name];metrics=self.data.metrics(c['id'],source)
            info=c['sources'].get(source,{})
            label.configure(text=f'{name}   {metrics.get("tier","—")}  ·  {percent(metrics.get("win_rate"))}'
                            +f'   ·   patch {info.get("patch") or "—"}')
        spells=self.data.spells(c['id'])
        for labels,row in zip(self.spell_rows,spells[:3]+[None]*3):
            labels[0].set(row['ids'] if row else [])
            for label,value in zip(labels[1:],(percent(row.get('pick_rate')),percent(row.get('win_rate'))) if row else ('—','—')):
                label.configure(text=value)
        self.paths.configure(text=' · '.join(c['paths']) or 'Sem caminho disponível')
        self.draft_name.configure(text=c['name'])
        self.draft_hint.set(hint)
        if hint:self.draft_hint.pack(fill='x',before=self.draft_metrics,pady=(1,5))
        else:self.draft_hint.pack_forget()
        self.draft_metrics.configure(text='\n'.join(label.cget('text') for _,label in self.source_rows))
        for labels,source_labels in zip(self.draft_spells,self.spell_rows):
            labels[0].set(source_labels[0].ids)
            for label,source_label in zip(labels[1:],source_labels[1:]):label.configure(text=source_label.cget('text'))

    def render_draft(self,snapshot):
        self.browse_view.pack_forget()
        self.draft_view.pack(fill='both',expand=True)
        source=SOURCES[self.source.get()]
        own=snapshot.get('champion_id')
        slots=snapshot.get('team_slots')
        if slots is None:
            slots=[{'champion_id':i,'is_self':i==own} for i in snapshot.get('team',[])[:5]]
        slots=list(slots[:5])+[{'champion_id':None,'is_self':False}]*(5-len(slots))
        available=[own]+snapshot.get('bench',[])+[s['champion_id'] for s in slots]
        if self.selected not in available or own and self.previous_own!=own:
            self.selected=own or next((i for i in available if i),None)
        self.previous_own=own
        def entry(ident,is_self=False):
            c=self.data.champion(ident) or {}
            m=self.data.metrics(ident,source);tier=m.get('tier','—')
            return {'id':ident if c else None,'name':c.get('name'),'tier':tier,
                    'win_rate':percent(m.get('win_rate')),'is_self':is_self,
                    'color':TIER_COLORS.get(tier[:1],MUTED)}
        self.bench_title.configure(text=f'BANCO DE CAMPEÕES · {len(snapshot.get("bench",[]))}')
        self.bench_strip.render([entry(i) for i in snapshot.get('bench',[])],self.selected)
        self.team_strip.render([entry(s['champion_id'],s['is_self']) for s in slots],self.selected)
        self.render_details()

    def render_select(self,snapshot):
        signature=(snapshot.get('state'),snapshot.get('champion_id'),tuple(snapshot.get('bench',[])),
                   tuple(snapshot.get('team',[])),tuple(snapshot.get('spells',[])),self.source.get(),self.order.get(),
                   tuple((s.get('champion_id'),s.get('is_self')) for s in snapshot.get('team_slots',[])),self.search.get())
        if signature==self.drawn:return
        self.drawn=signature
        if snapshot.get('state')=='select':
            self.render_draft(snapshot)
            return
        self.draft_view.pack_forget()
        self.browse_view.pack(fill='both',expand=True)
        own=snapshot.get('champion_id')
        available=list(dict.fromkeys(([own] if own else [])+snapshot.get('bench',[])))
        source=SOURCES[self.source.get()]
        offline=snapshot.get('state')!='select'
        if offline:
            available=[c['id'] for c in self.data.champions.values()]
        self.pool_title.configure(text='Campeões')
        def key(ident):
            c=self.data.champion(ident) or {'name':str(ident)};m=self.data.metrics(ident,source)
            if self.order.get()=='Nome':return (c['name'],)
            if self.order.get()=='Win rate':return (-(m.get('win_rate') or 0),c['name'])
            return (tier_key(m.get('tier')),
                    m.get('rank') or 999,-(m.get('win_rate') or 0),c['name'])
        query=normalized(self.search.get())
        available=sorted((i for i in available if self.data.champion(i) and
                          query in normalized(self.data.champion(i)['name'])),key=key)
        self.table.delete(*self.table.get_children())
        for ident in available:
            c=self.data.champion(ident);m=self.data.metrics(ident,source);tier=m.get('tier','—')
            self.table.insert('', 'end',iid=str(ident),image=self.portraits.photo(ident,32),values=(c['name'],tier,percent(m.get('win_rate')),
                              'Seu campeão' if ident==own else ('Banco' if not offline else '')),tags=(tier[:1],))
        if own and (self.selected is None or self.previous_own!=own):self.selected=own
        if self.selected not in available:self.selected=available[0] if available else None
        self.previous_own=own
        if str(self.selected) in self.table.get_children():self.table.selection_set(str(self.selected))
        if available:self.empty_results.pack_forget()
        else:self.empty_results.pack(fill='x',pady=12)
        self.render_details()

    def update_action(self):
        value=self.updates.snapshot();state=value['state']
        if self.demo:return
        if state=='available':self.updates.task('download')
        elif state=='downloaded':
            with self.updates.lock:
                self.updates.value.update(state='preparing',message='Conferindo se é possível instalar…')
            def prepare():
                try:
                    if not getattr(sys,'frozen',False):raise RuntimeError('Instale a versão empacotada para atualizar pelo app.')
                    install_after_exit(value['path'],value['sha256'],sys.executable)
                    self.install_ready=True
                except Exception:
                    with self.updates.lock:self.updates.value.update(state='downloaded',message='Não foi possível instalar. Saia da seleção/partida e tente novamente.')
            threading.Thread(target=prepare,daemon=True).start()
        else:self.updates.task(value.get('retry_action','check') if state=='error' else 'check')

    def tick(self):
        if self.stop.is_set():return
        if getattr(self,'install_ready',False):self.on_exit();return
        snapshot=self.service.snapshot();state=snapshot['state']
        labels={'offline':'LoL desconectado','connecting':'Conectando ao LoL…',
                'unavailable':'Conexão indisponível','select':'Seleção de Mayhem',
                'other_queue':'Outra fila','game':'Em partida','transition':'Atualizando seleção…'}
        color=ACCENT if state in ('connected','select','game') else '#f3cf7a' if state in ('unavailable','connecting','transition') else MUTED
        self.connection.configure(text='● '+labels.get(state,'LoL conectado'),fg=color)
        if not self.overlay_active:self.overlay_badge.pack(side='right')
        else:self.overlay_badge.pack_forget()
        try:status=json.loads((local_root(self.root)/'item-sets/status.json').read_text('utf8'))
        except (OSError,ValueError):status={}
        if self.demo:status={'state':'imported','champion_id':103,'generation':self.manifest['generation'],'paths':1,'owner_pid':os.getpid()}
        title,_=import_status(status,snapshot,self.manifest['generation'],os.getpid())
        if state=='select':
            ready=title=='Arsenais prontos'
            self.import_badge.configure(text='·  '+title,fg=ACCENT if ready else '#f3cf7a')
            self.import_badge.pack(side='left',padx=(16,0))
        else:self.import_badge.pack_forget()
        self.render_select(snapshot)
        update=self.updates.snapshot();self.update_message.configure(text=update['message'])
        self.update_button.configure(text={'busy':'Aguarde…','preparing':'Aguarde…','available':'Baixar atualização','downloaded':'Instalar e reiniciar','error':'Tentar novamente'}.get(update['state'],'Verificar atualizações'),
                                     state='disabled' if update['state'] in ('busy','preparing') or self.demo else 'normal')
        self.notes.configure(text=(update.get('release') or {}).get('notes','')[:1500])
        phase=snapshot.get('phase')
        if state=='game':
            if not self.in_game:self.window.iconify()
            self.in_game=True
        elif state in ('connected','select','other_queue'):
            if self.in_game or phase=='ChampSelect' and phase!=self.previous_phase:self.show()
            self.in_game=False
        # A transient LCU disconnect is not evidence that the match ended.
        self.previous_phase=phase
        self.window.after(300,self.tick)

    def show(self):
        self.window.deiconify();self.window.lift()


def preview():
    root=tk.Tk();root.withdraw();stop=threading.Event()
    def close():stop.set();root.destroy()
    Launcher(root,stop,close,demo=True)
    root.mainloop()


if __name__=='__main__':preview()
