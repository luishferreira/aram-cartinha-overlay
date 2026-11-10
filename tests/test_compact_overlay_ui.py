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

    def test_full_observations_scroll_and_refresh_without_losing_other_columns(self):
        card = self.card(80)
        full_text = 'Texto longo preservado. '*600+'FIM DA OBSERVAÇÃO'
        card['combo_evidence']['editorial'] = [
            {'text':full_text,'member_names':['Carta escolhida'],'other_names':['Alternativa']},
            {'text':'Segunda observação completa.','member_names':[],'other_names':[]}]
        for slot in range(3):self.app.render_slot(slot,'Carta '+str(slot),card,None)
        self.app.toggle_notes();self.app.render_controls(True,None,0,0,180)
        self.root.update_idletasks()
        text = self.app.notes_texts[0]
        self.assertIn(full_text,text.get('1.0','end'))
        self.assertIn('Segunda observação completa.',text.get('1.0','end'))
        self.assertEqual(text.cget('state'),'disabled')
        text.yview_moveto(1);self.root.update_idletasks()
        position = text.yview()
        self.assertGreater(position[0],0)
        self.app.cards[1] = self.card(70)
        self.app.render_controls(True,None,0,0,180)
        self.root.update_idletasks()
        self.assertEqual(text.yview(),position)
        self.assertIn('Sem observações salvas',self.app.notes_texts[1].get('1.0','end'))
        self.assertLessEqual(self.app.notes.winfo_children()[0].winfo_reqheight(),486)

    def test_observations_and_comparison_are_exclusive_and_reset_with_offer(self):
        self.app.render_slot(0,'Carta',self.card(80),None)
        self.app.toggle_notes()
        self.assertTrue(self.app.notes_open)
        self.app.toggle()
        self.assertTrue(self.app.details_open)
        self.assertFalse(self.app.notes_open)
        self.app.toggle_notes()
        self.assertFalse(self.app.details_open)
        self.app.render_controls(False,None,0,0,180)
        self.assertFalse(self.app.notes_open)
        self.assertEqual(self.app.notes.state(),'withdrawn')
        self.assertEqual(self.app.notes_button.cget('text'),'Observações')
