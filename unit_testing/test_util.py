"""Testing functions for the util module."""
# -*- coding: utf-8 -*-
# The above comment (WHICH MUST REMAIN ON LINE 2 OF THIS FILE) instructs
# python to interpret the source code in this file to be of the specified
# encoding. Important because we have unicode literals hard coded here.
# See http://legacy.python.org/dev/peps/pep-0263/

# Always import core first.
import core

# Libraries App Engine has built in.
import datetime
import re

# Libraries App Engine doesn't know about, for which we much include the
# code ourselves. They live in a special folder.
## add third party libraries here

# Our libraries.
import unit_test_helper
import util


class UtilTestCase(unit_test_helper.PertsTestCase):
    def test_clean_string(self):
        """Test that clean_string() returns only lowercase a-z of type str."""
        strings_to_clean = [
            u'Nicholas',
            u'Nicol\u00E1s',
            u'N1colas',
            u'N#$colas',
            u'Nichol"a"s',
            u'Nich\olas',
            'Nicholas',
            'N1colas',
            'N#$colas',
            'Nichol"a"s',
            "Nich\olas",
            # This guy *shouldn't* fail, but it won't return what we want it to
            # (This isn't a problem right now, because the front end is serving
            # us unicode objects, not strs.):
            'Nicol\u00E1s',
        ]

        for index, test_string in enumerate(strings_to_clean):
            # nothing but lowercase alphabetic characters, beginning to end.
            pattern = r'^[a-z]+$'
            cleaned_string = util.clean_string(test_string)
            # re.match() will return None if the pattern doesn't match.
            self.assertIsNotNone(re.match(pattern, cleaned_string),
                                 'string index: {}'.format(index))

            # output must always be a string (not unicode)
            self.assertIsInstance(cleaned_string, str)

    def test_parse_datetime(self):
        """Test that parse_datetime() can handle a variety of date formats."""
        dt = datetime.datetime

        test_values = [
            ('2014-01-01', dt(2014, 1, 1)),
            ('1/13/2014', dt(2014, 1, 13)),
            ('13/1/2014', dt(2014, 1, 13)),
            ('4/5/2014', dt(2014, 4, 5)),
            ('Thursday, August 14th, 2014', dt(2014, 8, 14)),
        ]

        for date_string, datetime_obj in test_values:
            self.assertEquals(util.parse_datetime(date_string), datetime_obj)

        # util.parse_datetime can also handle dates and times and datetimes
        # actual time values in them, but I don't feel like writing tests for
        # those.
