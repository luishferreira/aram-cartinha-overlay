"""Layout and consultation contracts, with a simulated select and no game side effects."""
import threading
import gc
import tkinter as tk
import unittest

from tools.launcher.window import Launcher


class LauncherWindowTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.root.withdraw();self.stop=threading.Event()
        self.app=Launcher(self.root,self.stop,lambda:None,demo=True)
        self.app.tick();self.root.update()

    def tearDown(self):
        self.stop.set()
        for callback in self.root.tk.splitlist(self.root.tk.call('after','info')):
            self.root.tk.call('after','cancel',callback)
        self.root.destroy()
        # Tcl objects must be finalized here, before another test's worker triggers GC.
        self.app=None;self.root=None
        gc.collect()

    def test_browsing_a_bench_champion_does_not_change_the_actual_selection(self):
        self.assertEqual(self.app.service.snapshot()['champion_id'],103)
        self.app.choose_portrait(11)
        self.assertEqual(self.app.focus_name.cget('text'),'Master Yi')
        self.assertEqual(self.app.service.snapshot()['champion_id'],103)
        self.assertEqual(self.app.focus_hint.ids,())
        self.app.set_page('updates');self.root.update_idletasks()
        self.assertTrue(self.app.update_page.winfo_ismapped())
        self.assertFalse(self.app.select_page.winfo_ismapped())

    def test_portraits_preserve_team_slots_and_bench_order_and_source_changes(self):
        self.assertEqual([c['id'] for c in self.app.bench_strip.cards],[11,21,145,17,81,22,40,45])
        self.assertEqual([c['id'] for c in self.app.team_strip.cards],[103,222,12,99,64])
        self.assertTrue(self.app.team_strip.cards[0]['is_self'])
        self.assertTrue(self.app.draft_view.winfo_ismapped())
        self.assertFalse(self.app.browse_view.winfo_ismapped())
        card=self.app.team_strip.cards[0]
        self.assertIn('52,24%',card['metrics'].cget('text'))
        self.source_before=self.app.service.snapshot()
        self.app.source.set('Mayhem.com');self.app.redraw();self.app.tick()
        self.assertIn('51,83%',self.app.team_strip.cards[0]['metrics'].cget('text'))
        self.assertEqual(self.app.service.snapshot(),self.source_before)

    def test_empty_slots_are_retained_and_large_bench_scrolls(self):
        value=self.app.service.value
        value['team_slots']=[{'champion_id':103,'is_self':True},{'champion_id':None,'is_self':False},
                             {'champion_id':12,'is_self':False}]
        value['bench']=[int(i) for i in list(self.app.data.champions)[:15]]
        self.app.redraw();self.app.tick();self.root.update_idletasks()
        self.assertEqual([c['id'] for c in self.app.team_strip.cards],[103,None,12,None,None])
        self.assertEqual(len(self.app.bench_strip.cards),15)
        self.assertTrue(self.app.bench_strip.scrollbar.winfo_ismapped())

    def test_outside_select_the_approved_consultation_table_is_preserved(self):
        self.app.service.value={'state':'connected','phase':'Lobby','champion_id':None,'bench':[],'team':[],'spells':[]}
        self.app.tick();self.root.update_idletasks()
        self.assertTrue(self.app.browse_view.winfo_ismapped())
        self.assertFalse(self.app.draft_view.winfo_ismapped())
        self.assertEqual(len(self.app.table.get_children()),173)
        self.app.table.selection_set('145');self.app.choose()
        self.assertEqual(self.app.focus_name.cget('text'),"Kai'Sa")

    def test_scrollbar_reaches_both_ends_of_the_champion_list(self):
        self.app.service.value={'state':'offline','champion_id':None,'bench':[],'team':[],'spells':[]}
        self.app.tick();self.root.update_idletasks()
        self.assertGreaterEqual(self.app.champion_scrollbar.winfo_width(),8)
        self.app.table.yview_moveto(1);self.root.update_idletasks()
        first,last=self.app.champion_scrollbar.get()
        self.assertGreater(first,0)
        self.assertEqual(last,1)
        self.app.table.yview_moveto(0);self.root.update_idletasks()
        self.assertEqual(self.app.champion_scrollbar.get()[0],0)

    def test_spell_icons_follow_each_champions_pairs_without_changing_own_spells(self):
        self.assertEqual(self.app.draft_hint.ids,(4,32))
        for ident in (103,11,145):
            self.app.choose_portrait(ident)
            expected=self.app.data.spells(ident)[:3]
            for index,row in enumerate(expected):
                self.assertEqual(self.app.spell_rows[index][0].ids,tuple(row['ids']))
                self.assertEqual(self.app.draft_spells[index][0].ids,tuple(row['ids']))
                self.assertTrue(self.app.draft_spells[index][0].icons[0].cget('image'))
            self.assertEqual(self.app.service.snapshot()['spells'],[4,32])

    def test_build_paths_and_controls_fit_the_minimum_window_size(self):
        self.app.window.geometry('1000x680');self.root.update_idletasks()
        paths=self.app.paths
        self.assertTrue(paths.cget('text'))
        focus=self.app.draft_spells[-1][-1]
        self.assertLessEqual(focus.winfo_rooty()+focus.winfo_height(),
                             self.app.select_page.winfo_rooty()+self.app.select_page.winfo_height())

    def test_search_filters_as_you_type_and_clears_stale_details_on_no_results(self):
        self.app.service.value={'state':'offline','champion_id':None,'bench':[],'team':[],'spells':[]}
        self.app.search.set('kaisa');self.app.tick();self.root.update_idletasks()
        self.assertEqual(self.app.table.get_children(),('145',))
        self.assertEqual(self.app.focus_name.cget('text'),"Kai'Sa")
        self.assertTrue(self.app.details_content.winfo_ismapped())
        self.app.search.set('not-a-champion');self.app.tick();self.root.update_idletasks()
        self.assertEqual(self.app.table.get_children(),())
        self.assertFalse(self.app.details_content.winfo_ismapped())
        self.assertTrue(self.app.empty_results.winfo_ismapped())
        self.app.search.set('');self.app.tick();self.root.update_idletasks()
        self.assertEqual(len(self.app.table.get_children()),173)
        self.assertTrue(self.app.details_content.winfo_ismapped())

    def test_game_lifecycle_waits_for_a_confirmed_end_even_after_a_disconnect(self):
        for state,phase in [('game','InProgress'),('offline',None),('game','PreEndOfGame')]:
            self.app.service.value={'state':state,'phase':phase,'champion_id':None,'bench':[],'team':[],'spells':[]}
            self.app.tick();self.root.update_idletasks()
            self.assertEqual(self.app.window.state(),'iconic')
        self.app.service.value={'state':'connected','phase':'EndOfGame','champion_id':None,'bench':[],'team':[],'spells':[]}
        self.app.tick();self.root.update_idletasks()
        self.assertEqual(self.app.window.state(),'normal')


if __name__=='__main__':unittest.main()
