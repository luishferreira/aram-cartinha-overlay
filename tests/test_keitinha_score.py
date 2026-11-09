import copy
import unittest

from tools.recommendation.keitinha_score import calculate,popularity_percentiles,tier_points


def tier(value,*,scope='champion',rarity=False):
    return {'scope':scope,'context':{'ranking_scope':'rarity'} if rarity else {},
            'metrics':{'tier':{'value':value}}}


def population(values):
    ordered=sorted(enumerate(values),key=lambda item:-item[1])
    result={};previous=None;rank=None
    for position,(ident,value) in enumerate(ordered,1):
        if value!=previous:rank=position
        result[str(ident)]={'rank':rank,'published_entries':len(values),'raw_value':value}
        previous=value
    return result


class KeitinhaScoreTests(unittest.TestCase):
    def test_every_source_contributes_once_and_opgg_tier_cannot_change_score(self):
        sources={'aramkit':tier('S'),'blitz':tier('A'),
                 'arammayhem_champion_tier':tier('B',rarity=True),'opgg':tier('D')}
        before=copy.deepcopy(sources)
        score=calculate(sources,{'points':30})
        self.assertEqual(score['value'],60)
        self.assertEqual([c['weight'] for c in score['components']],[.25]*4)
        self.assertEqual([c['source'] for c in score['components']],['aramkit','blitz','arammayhem','opgg'])
        self.assertEqual(sources,before)
        sources['opgg']=tier('S+')
        self.assertEqual(calculate(sources,{'points':30}),score)
        self.assertGreater(calculate(sources,{'points':90})['value'],score['value'])

    def test_absence_redistributes_weight_but_observed_zero_still_counts(self):
        sources={'aramkit':tier('S'),'blitz':tier('A')}
        result=calculate(sources,{'points':50})
        self.assertEqual(result['value'],70)
        self.assertEqual(result['available_sources'],3)
        self.assertEqual([c['weight'] for c in result['components']],[1/3]*3)
        result=calculate(sources,{'points':0})
        self.assertEqual(result['available_sources'],3)
        self.assertAlmostEqual(result['value'],160/3)

    def test_global_tiers_unknown_letters_and_opgg_tier_are_not_fallbacks(self):
        sources={'opgg':tier('S'),'aramkit':tier('unknown'),
                 'blitz':tier('S',scope='global'),'arammayhem_tier':tier('S',scope='global'),
                 'arammayhem_champion_tier':tier('S')}
        result=calculate(sources)
        self.assertIsNone(result['value'])
        self.assertEqual(result['available_sources'],0)
        self.assertEqual(result['components'],[])
        for value in (float('nan'),float('inf'),-1,101,True):
            self.assertIsNone(calculate({}, {'points':value})['value'])

    def test_subtiers_keep_their_order_without_becoming_missing_or_global(self):
        self.assertEqual([tier_points(t) for t in ('S+','S','S-','A+','A','A-','B','C','D')],
                         [95,90,85,75,70,65,50,30,10])
        self.assertEqual(tier_points(' a+ '),75)
        for value in ('X','F','S++',None,0):self.assertIsNone(tier_points(value))

    def test_popularity_uses_the_entire_champion_population(self):
        scores=popularity_percentiles(population([100,80,60,40,20]))
        self.assertEqual([scores[str(i)]['points'] for i in range(5)],[100,75,50,25,0])
        # The same card keeps its percentile regardless of which other cards are offered.
        chosen=[scores[i]['points'] for i in ('1','3','4')]
        self.assertEqual(chosen,[75,25,0])

    def test_ties_get_equal_midranks_and_no_variation_is_neutral(self):
        scores=popularity_percentiles(population([9,8,8,8,2]))
        self.assertEqual([scores[str(i)]['points'] for i in range(5)],[100,50,50,50,0])
        self.assertEqual(scores['1']['tied_entries'],3)
        self.assertEqual([r['points'] for r in popularity_percentiles(population([1,1,1])).values()],[50]*3)
        self.assertEqual(popularity_percentiles(population([1]))['0']['points'],50)
        self.assertEqual(popularity_percentiles({}),{})

    def test_partial_or_inconsistent_rank_populations_are_not_rescaled(self):
        complete=population([5,4,3,2,1])
        self.assertEqual(popularity_percentiles({k:complete[k] for k in ('0','3','4')}),{})
        for rank in (0,6,None,float('nan'),True):
            broken=copy.deepcopy(complete);broken['0']['rank']=rank
            self.assertEqual(popularity_percentiles(broken),{})


if __name__=='__main__':unittest.main()
