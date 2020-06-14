"""Test randomized stratification.

See core.Stratifier
"""

# Always import core first.
import core

# Libraries App Engine has built in.
import random

# Libraries App Engine doesn't know about, for which we much include the
# code ourselves. They live in a special folder.
## add third party libraries here

# Our libraries.
import util
import unit_test_helper
from id_model import Stratifier, StratifierHistory


class StratiferTestCase(unit_test_helper.PertsTestCase):

    def set_up(self):
        ### we want the uncomplicated version for now
        self.testbed.init_datastore_v3_stub()
        
    ### functions that just assist the testing functions ###

    def init(self):
        kwargs = {
            'name': 'Test Stratifier',
            'program': 'Program_triohASht84561oASgh8',
            'proportions': {'exp1': 1, 'exp2': 2, 'con': 3},
        }
        return Stratifier.create(**kwargs)

    ### testing functions ###

    # See: http://docs.python.org/2/library/unittest.html#assert-methods

    def test_create(self):
        """Fidelity with datastore saving/loading."""
        s = self.init()
        s.put()
        # fetch to see if initial settings work
        s_fetched = Stratifier.get_by_id(s.id)
        self.assertEqual(s, s_fetched)
        self.assertEquals(s_fetched.groups(), set([
            'exp1', 'exp2', 'con']))
        # stratify some people
        profile1 = {'race': 'white', 'gender': 'female'}
        profile2 = {'race': 'black', 'gender': 'male'}
        s.stratify(profile1)
        s.stratify(profile1)
        s.stratify(profile2)
        s.put()
        # fetch again to make sure that changes are also correctly saved
        s_fetched = Stratifier.get_by_id(s.id)
        key1 = util.hash_dict(profile1)
        key2 = util.hash_dict(profile2)
        # did each of the profiles get saved?
        self.assertIn(key1, s.histories())
        self.assertIn(key2, s.histories())
        # did nesting also work?
        self.assertIsInstance(s.histories()[key1]._history, dict)
        self.assertIsInstance(s.histories()[key2]._history, dict)

    def test_hash_dict(self):
        """History hashes are unique and reliable."""
        same1 = {'a': 1, 'b': 2, 'c': 3}
        same2 = {'b': 2, 'a': 1, 'c': 3}
        same3 = {'c': 3, 'b': 2, 'a': 1}
        different = {'a': 2, 'd': 7}
        self.assertEqual(util.hash_dict(same1), util.hash_dict(same2))
        self.assertEqual(util.hash_dict(same2), util.hash_dict(same3))
        self.assertEqual(util.hash_dict(same1), util.hash_dict(same3))
        self.assertNotEqual(util.hash_dict(same1), util.hash_dict(different))

    def test_candidates(self):
        """Finds valid groups to which to stratify."""
        s = self.init()
        # If no one has been assigned, return all groups
        history = StratifierHistory(s, 'blah')
        groups = s.get_candidate_groups(history)
        self.assertEqual(groups, s.groups())
        # if all groups are proportionally represented, return all
        history._history = {'exp1': 1, 'exp2': 2, 'con': 3}
        groups = s.get_candidate_groups(history)
        self.assertEqual(groups, s.groups())
        # One group has ideal ratios for a given profile, we should get the
        # other two
        history._history = {'exp1': 1, 'exp2': 0, 'con': 0}
        groups = s.get_candidate_groups(history)
        self.assertEqual(groups, set(['exp2', 'con']))
        # Two groups have ideal ratios, we should get the third
        history._history = {'exp1': 1, 'exp2': 2, 'con': 0}
        candidates = s.get_candidate_groups(history)
        self.assertEqual(candidates, set(['con']))

    def test_stratification(self):
        """Stratifies 1000 users with various attributes within tolerances."""
        # todo: is this a good test that proportions hold true in aggregate?
        s = self.init()
        runs = 1000
        tolerance = 10
        profiles = {
            'white': {'race': 'white'},
            'black': {'race': 'black'},
            'mom': {'gender': 'female'},
            'petunia': {'gender': 'male'},
            'white_female': {'race': 'white', 'gender': 'female'},
            'white_male': {'race': 'white', 'gender': 'male'},
            'black_female': {'race': 'black', 'gender': 'female'},
            'black_male': {'race': 'black', 'gender': 'male'},
        }
        big_set = [random.choice(profiles.values()) for x in range(runs)]
        # counts should never differ from their ideal by more than a little bit
        results = [s.stratify(p) for p in big_set]
        self.assertLess(abs(results.count('exp1') - runs / float(6)), tolerance)
        self.assertLess(abs(results.count('exp2') - runs / float(3)), tolerance)
        self.assertLess(abs(results.count('con') - runs / float(2)), tolerance)

    def test_changing_groups(self):
        """Can handle a change in groups."""
        s = self.init()
        runs = 100
        profiles = {
            'white':  {'race': 'white'},
            'black':  {'race': 'black'},
            'mom':  {'gender': 'female'},
            'petunia':  {'gender': 'male'},
            'white_female':  {'race': 'white', 'gender': 'female'},
            'white_male':  {'race': 'white', 'gender': 'male'},
            'black_female':  {'race': 'black', 'gender': 'female'},
            'black_male':  {'race': 'black', 'gender': 'male'},
        }
        # stratify according to original groups
        big_set = [random.choice(profiles.values()) for x in range(runs)]
        results = [s.stratify(p) for p in big_set]
        # change the groups and stratify again
        s.proportions({'alt1': 1, 'alt2': 3})
        big_set = [random.choice(profiles.values()) for x in range(runs)]
        results = [s.stratify(p) for p in big_set]
        # we should see no evidence of the old groups in the new results
        # counts = {g: results.count(g) for g in s.groups()}
        correct_groups = set(['alt1', 'alt2'])
        self.assertEqual(s.groups(), correct_groups)
        self.assertEqual(set(results), correct_groups)
