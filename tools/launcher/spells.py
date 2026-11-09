"""Compact spell pairs, using bundled Riot icons and names on hover."""
import tkinter as tk


class SpellPair(tk.Frame):
    def __init__(self,parent,portraits,*,size=28):
        super().__init__(parent,bg=parent.cget('bg'))
        self.portraits,self.size=portraits,size
        self.ids=()
        self.tooltip=None
        self.pending=None
        self.icons=[]
        for index in range(2):
            icon=tk.Label(self,bg=self.cget('bg'),borderwidth=0)
            icon.pack(side='left',padx=(0,5))
            icon.bind('<Enter>',lambda e,i=index:self.hover(i))
            icon.bind('<Leave>',lambda e:self.hide_tooltip())
            self.icons.append(icon)
        self.empty=tk.Label(self,text='—',bg=self.cget('bg'),fg='#93a4bd',font=('Segoe UI',9))
        self.bind('<Unmap>',lambda e:self.hide_tooltip() if e.widget==self else None)
        self.bind('<Destroy>',lambda e:self.hide_tooltip() if e.widget==self else None)

    def set(self,ids):
        ids=tuple(i for i in ids if i)[:2]
        if ids==self.ids and (ids or self.empty.winfo_manager()):return
        self.hide_tooltip()
        self.ids=ids
        self.empty.pack_forget()
        for index,icon in enumerate(self.icons):
            if index<len(ids):
                icon.configure(image=self.portraits.spell_photo(ids[index],self.size))
                icon.pack(side='left',padx=(0,5))
            else:icon.pack_forget()
        if not ids:self.empty.pack(side='left')

    def hover(self,index):
        self.hide_tooltip()
        if index<len(self.ids):self.pending=self.after(350,lambda:self.show_tooltip(index))

    def show_tooltip(self,index):
        self.pending=None
        if not self.winfo_viewable() or index>=len(self.ids):return
        icon=self.icons[index]
        tip=self.tooltip=tk.Toplevel(self)
        tip.withdraw();tip.overrideredirect(True);tip.attributes('-topmost',True)
        tk.Label(tip,text=self.portraits.spell_name(self.ids[index]),bg='#233247',fg='#edf3ff',
                 font=('Segoe UI',9),padx=8,pady=4).pack()
        tip.geometry(f'+{icon.winfo_rootx()}+{icon.winfo_rooty()+icon.winfo_height()+5}')
        tip.deiconify()

    def hide_tooltip(self):
        if self.pending:
            self.after_cancel(self.pending);self.pending=None
        if self.tooltip and self.tooltip.winfo_exists():self.tooltip.destroy()
        self.tooltip=None
