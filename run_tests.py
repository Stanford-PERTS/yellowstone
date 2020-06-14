#!/usr/bin/env python

"""Run python unit tests from the command line.

Add a python-style name as the first argument to target specific files,
test cases, and test functions. For example:
> python run_tests.py test_authtoken
> python run_tests.py test_authtoken.AuthTokenTest.test_auth_token_validation
"""

import logging
import os
import ruamel.yaml
import sys
import unittest

# Yellowstone doesn't use gae_server
#sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gae_server'))

import branch_environment

# Tell python where it can find the app engine sdk.
# https://cloud.google.com/appengine/docs/python/tools/localunittesting?hl=en#Python_Setting_up_a_testing_framework
# Path for Codeship.
sys.path.insert(0, '/home/rof/appengine/python_appengine')
# Paths for local testing.
sys.path.insert(0, '/usr/local/google_appengine')
sys.path.insert(0, '/usr/local/google-cloud-sdk/platform/google_appengine')
sys.path.insert(0, '/usr/local/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/platform/google_appengine/')
user_path = os.path.expanduser('~/google-cloud-sdk/platform/google_appengine')
sys.path.insert(0, user_path)

# 2018-10-11 We found that the fix_sys_path() function started changing the
# script's working directory, so any downstream use of the filesystem was
# broken. Hack around this by restoring the cwd. Note that we can't just stop
# using this function because it allows tests to load SDK-provided python libs,
# like webapp2.
original_cwd = os.getcwd()
import dev_appserver
dev_appserver.fix_sys_path()
os.chdir(original_cwd)

# We modify the import paths in this project, so similarly modify them during
# testing.
import appengine_config

# PERTS code expects this to be set so we can detect deployed vs.
# not deployed (SDK i.e. dev_appserver). See environment functions like
# is_localhost() in util.py.
# Also important for unit testing cloudstorage api, which checks this value to
# decide if it will talk to a stub service or the real GCS.
os.environ['SERVER_SOFTWARE'] = 'Development/X.Y'

# Grab the "second word" or first parameter from what the user typed on the
# command line. If it exists, it will be used to target a specific test or set
# of tests.
test_name = sys.argv[1] if len(sys.argv) == 2 else None

# Read through app.yaml and set an environment variables that are present.
with open('app.yaml', 'r') as file_handle:
    # Read as a dictionary.
    app_yaml = ruamel.yaml.load(file_handle.read(), ruamel.yaml.Loader)

for key, value in app_yaml['env_variables'].items():
    os.environ[key] = value

branch = branch_environment.get_branch()
conf = branch_environment.load_branch_conf(branch)
os.environ['APPLICATION_ID'] = conf['app.yaml']['PROJECT_ID']

if test_name:
    suite = unittest.loader.TestLoader().loadTestsFromName(
        'unit_testing.' + test_name)
else:
    # Check the unit_testing folder for test definitions.
    suite = unittest.loader.TestLoader().discover('unit_testing')
    # Suppress most logs when we're running all tests.
    logging.getLogger().setLevel(logging.WARNING)

test_result = unittest.TextTestRunner(verbosity=2).run(suite)

# The wasSuccessful function doesn't do exactly what you expect. It
# returns True even if there are unexpected successes. Fix it.
# https://docs.python.org/2/library/unittest.html#unittest.TestResult
success = (test_result.wasSuccessful() and
           len(test_result.unexpectedSuccesses) is 0)

# This part is essential for communicating to codeship's build process. It will
# stop the build--and stop short of deployment!--if any of the commands run
# during the build return an exit code of 1, which indicates an error.
# Although the TextTestRunner does stream to stderr when there are failures, it
# does NOT exit with code 1 on its own. Do that here.
sys.exit(0 if success else 1)
