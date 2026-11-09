"""Verify the compact score stays visible and refreshes without changing source tiers."""
import gc
import tkinter as tk
import unittest

from tools.live.compact_overlay import CompactCards


class Host:
    def make_overlay(self,window_id,**kwargs):return window_id


class CompactScoreLayoutTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.root.withdraw()
        self.app=CompactCards(self.root,Host())
        # Measure the real Tk widgets without displaying extra windows on the desktop.
        self.app.show=lambda window,x,y,width,height,interactive=False:window.geometry(f'{width}x{height}')

    def tearDown(self):
        self.root.destroy();self.app=None;self.root=None;gc.collect()

    def card(self,value):
        return {'sources':{},'opgg_popularity':{'rank':215,'published_entries':300},
                'keitinha_score':{'value':value,'available_sources':3},'combo_evidence':{}}

    def test_score_refreshes_even_when_tiers_and_pick_position_do_not_change(self):
        self.app.render_slot(0,'Carta',self.card(81.3),None)
        label=self.app.headers[0][1]['score']
        self.assertEqual(label.cget('text'),'Keitinha Score  81,3')
        self.app.render_slot(0,'Carta',self.card(74.8),None)
        self.assertEqual(label.cget('text'),'Keitinha Score  74,8')
        self.app.render_slot(0,'Carta',None,None)
        self.assertEqual(label.cget('text'),'Keitinha Score  —')

    def test_header_and_comparison_fit_existing_windows(self):
        name='Uma carta com um nome suficientemente comprido'
        for slot in range(3):self.app.render_slot(slot,name,self.card(100),None)
        self.app.toggle();self.app.render_controls(True,None,0,0,180)
        self.root.update_idletasks()
        window,widgets,_=self.app.headers[0]
        self.assertLessEqual(widgets['pick'].winfo_reqwidth()+widgets['score'].winfo_reqwidth(),290)
        self.assertLessEqual(window.winfo_children()[0].winfo_reqheight(),76)
        self.assertLessEqual(self.app.details.winfo_children()[0].winfo_reqheight(),258)
