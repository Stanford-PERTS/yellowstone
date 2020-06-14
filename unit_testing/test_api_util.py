"""Testing accessory functions of api.py."""

# Always import core first.
import core

# Libraries App Engine has built in.
import unittest

# Libraries App Engine doesn't know about, for which we much include the
# code ourselves. They live in a special folder.
## add third party libraries here

# Our libraries.
from api import Api
from cron import Cron
import unit_test_helper


class ApiUtilTestCase(unit_test_helper.PertsTestCase):
    def set_up(self):
        # We don't need to model consistency here. This version of the
        # datastore always returns consistent results.
        self.testbed.init_datastore_v3_stub()
