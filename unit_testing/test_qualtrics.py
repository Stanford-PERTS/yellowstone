"""Test reading and writing of program data."""

# Always import core first.
import core

# Libraries App Engine has built in.
from google.appengine.ext import db

# Libraries App Engine doesn't know about, for which we much include the
# code ourselves. They live in a special folder.
## add third party libraries here

# Our libraries.
from id_model import Program
from named_model import QualtricsLink
import unit_test_helper


class QualtricsTestCase(unit_test_helper.PopulatedInconsistentTestCase):

    def test_unique_retrieval(self):
        """Test that QualtricsLink.get_link catches inconsistent results
        proving that get_link() handles inconsistency and doesn't return
        deleted (already used and thus non-unique) links"""

        p = Program.create(name='Test Program', abbreviation='TP1')

        # Create two links and put them to the db
        a = QualtricsLink.create(key_name='test_a', link='test_a',
                                 session_ordinal=1, program=p.id)
        b = QualtricsLink.create(key_name='test_b', link='test_b',
                                 session_ordinal=1, program=p.id)
        a.put()
        b.put()

        # db.get by key forces consistency
        a, b = db.get([a.key(), b.key()])

        # delete link a to put db into inconsistent state.
        db.delete(a)

        # get_link pulls in alphabetical order by link, so
        # a is retrieved first, then b.
        b_link = QualtricsLink.get_link(p, 1, default_link='qualtrics.com')

        # If we have consistency issues, get_link() may not see that a has been
        # deleted, and thus return it rather than b. We want to assert that we
        # don't have those issues.
        self.assertEquals(b_link, 'test_b')

    def test_default(self):
        """If no link entities exist, the default link is returned."""
        p = Program.create(name='Test Program', abbreviation='TP1')
        default_link = 'qualtrics.com'
        link = QualtricsLink.get_link(p, 1, default_link=default_link)
        self.assertEquals(link, default_link)
