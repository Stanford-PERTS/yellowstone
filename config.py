"""Collection of hard-coded settings."""

from collections import namedtuple

unit_test_directory = 'unit_testing'

# Auth types
# * direct - For those who sign in by typing in their email address and
#     password. They have a password hash. Their auth_ids look like
#     ''
# * google - For those who sign in via google. They don't have a password
#     hash; google just tells us they're legit. Their auth_ids look like
#     'google_1234567890', where the numbers are their google identifier.
# * public - For those who register for public-access programs (like NP14F).
#     They are blocked from all forms of authentication: login, normal
#     registration, and password resets. Their data and relationships look
#     just like any other user, however, e.g. from the dashboard.
allowed_auth_types = ['direct', 'google', 'public']

# These are ranked! Higher types can impersonate lower types.
allowed_user_types = ['student', 'teacher', 'school_admin', 'researcher',
                      'god']

# This one isn't actually enforced anywhere yet.
allowed_activity_states = ['incomplete', 'completed', 'aborted']

# The various ways that participants identify themselves.
allowed_identification_types = ['default', 'alias', 'dissemination']


# Who can create what type of object?
# (gods can create anything; they're excluded from this list)
user_type_can_create = {
    'public': ['user'],
    'student': ['pd', 'activity'],
    'teacher': ['pd', 'classroom', 'user', 'activity'],
    'school_admin': ['pd', 'classroom', 'user', 'activity'],
    'researcher': ['pd', 'classroom', 'user', 'activity', 'cohort', 'program',
                   'activity_template', 'school'],
}

user_type_can_delete = {
    'teacher': ['classroom', 'activity'],
    'school_admin': ['classroom', 'activity', 'user'],
    'researcher': ['classroom', 'user', 'activity', 'cohort', 'school'],
}

# todo: the above list doesn't even bother to list what god can do...
# probably this code should be parallel, which involves modifying the code
# that checks this list.
can_put_user_type = {
    'public': ['student', 'teacher'],
    'student': [],
    'teacher': [],
    # School_admins can upload rosters of students. They can also create
    # test teachers via the browser test in the home page.
    'school_admin': ['student', 'teacher'],
    # Researchers can put school_admins so that they can promote users who
    # have signed up (and are teachers by default) to be school admins.
    # They can put students so they can create test student users to run
    # through program apps. There's no reason for them to create regular
    # students.
    'researcher': ['student', 'school_admin'],
    'god': ['student', 'teacher', 'school_admin', 'researcher', 'god'],
}

# some kinds require additional update validation, e.g., cohorts
# must have unique codes
kinds_requiring_put_validation = [
    'cohort', 'user',
]

# variables with special rules about filters to apply
kinds_with_get_filters = [
    'pd',
]

# These define the initial relationships between the created entity and the
# creating user.
creator_relationships = {
    'program': 'set_owner',
    'classroom': 'set_owner',
    'cohort': 'set_owner',
    'user': None,
    'activity': 'set_owner',
    'school': 'associate',
    'pd': None,  # pd visibility is based on cohort and program assc.
    'email': None,  # email is called via internal apis
    'qualtrics_link': None,
}

# These pd variables names, when generated within an activity (not, for
# instance, from the teacher panel or the dashboard), will get marked as
# public = True.
pd_whitelist = [
    'time', 'position_history', 'consent', 'condition',
    's1__qualtrics_link',
    's2__qualtrics_link',
    's3__qualtrics_link',
    's4__qualtrics_link',
    's5__qualtrics_link',
    's1__progress',
    's2__progress',
    's3__progress',
    's4__progress',
    's5__progress',
    'checklist-teacher-1',
    'checklist-teacher-2',
    'checklist-teacher-3',
    'checklist-teacher-4',
    'checklist-teacher-5',
    'checklist-teacher-6',
    'checklist-teacher-7',
    'checklist-teacher-8',
    'checklist-teacher-9',
    'checklist-school_admin-1',
    'checklist-school_admin-2',
    'checklist-school_admin-3',
    'checklist-school_admin-4',
    'checklist-school_admin-5',
    'checklist-school_admin-6',
    'educator_agreement_accepted',
    'parent_info_confirmed',
    # This is used by the cross-site client test.
    'cross_site_test',
]

# certain types need to perform custom validation before creation
custom_create = ['pd']

# These status codes are set manually by teachers on the roster page. All of
# them imply non-participation, but have different ways of being counted in
# the reporting interfaces. They originate with a third-party organization
# collaborating on Yosemite (ICF), and we got their definitions directly from
# them. For more detail, see the "Status Definitions" sheet on the Yosemite
# UI Mockups:
# https://docs.google.com/spreadsheets/d/1K3U5oRtjaZfirRg2AuDOA5OM8brm5d2YSPPOUVrcWjU/edit#gid=1023588647
status_codes = {
    'A': {'label': 'Absent', 'study_eligible': True,
          'makeup_eligible': True, 'counts_as_completed': False,
          'exclude_from_counts': False},
    'SR': {'label': 'Student Refusal', 'study_eligible': True,
           'makeup_eligible': True, 'counts_as_completed': False,
           'exclude_from_counts': False},
    'NFR': {'label': 'No Form Returned', 'study_eligible': True,
            'makeup_eligible': True, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'ISS': {'label': 'In School Suspension', 'study_eligible': True,
            'makeup_eligible': True, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'TRI': {'label': 'Technology-related Issue', 'study_eligible': True,
            'makeup_eligible': True, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'PR': {'label': 'Parent Refusal', 'study_eligible': True,
           'makeup_eligible': False, 'counts_as_completed': False,
           'exclude_from_counts': False},
    'COM': {'label': 'Completed', 'study_eligible': True,
            'makeup_eligible': False, 'counts_as_completed': True,
            'exclude_from_counts': False},
    'CCI': {'label': 'Cannot Complete Independently', 'study_eligible': False,
            'makeup_eligible': False, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'DC': {'label': 'Dropped Class', 'study_eligible': False,
           'makeup_eligible': False, 'counts_as_completed': False,
           'exclude_from_counts': False},
    'DS': {'label': 'Dropped School', 'study_eligible': False,
           'makeup_eligible': False, 'counts_as_completed': False,
           'exclude_from_counts': False},
    'E': {'label': 'Expelled', 'study_eligible': False,
          'makeup_eligible': False, 'counts_as_completed': False,
          'exclude_from_counts': False},
    'EA': {'label': 'Extended Absence', 'study_eligible': False,
           'makeup_eligible': False, 'counts_as_completed': False,
           'exclude_from_counts': False},
    'H': {'label': 'Homebound', 'study_eligible': False,
          'makeup_eligible': False, 'counts_as_completed': False,
          'exclude_from_counts': False},
    'MA': {'label': 'Moved Away', 'study_eligible': False,
           'makeup_eligible': False, 'counts_as_completed': False,
           'exclude_from_counts': False},
    'OGR': {'label': 'Out of Grade Range', 'study_eligible': False,
            'makeup_eligible': False, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'OSS': {'label': 'Out of School Suspension', 'study_eligible': False,
            'makeup_eligible': False, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'TAC': {'label': 'Took in Another Class', 'study_eligible': False,
            'makeup_eligible': False, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'DIS': {'label': 'Discard: Incorrect Sign-in', 'study_eligible': False,
            'makeup_eligible': False, 'counts_as_completed': False,
            'exclude_from_counts': True},
    'MWN': {'label': 'Merge: Wrong Name', 'study_eligible': False,
            'makeup_eligible': False, 'counts_as_completed': False,
            'exclude_from_counts': True},
}

# defines where users go after login, and what the "home" button does
user_home_page = {
    'god': '/d',
    'researcher': '/d',
    'school_admin': '/d',
    # @todo: in future versions, point to a program-agonstic
    # CohortChooserController so any cohort can be selected in any program.
    'teacher': '/d',
    # students: not allowed at the login page
    'public': '/',
}

# These define what kinds of other entity ids must be passed in when an entity
# is created.
required_associations = {
    # Part of being identified as a student is choosing a classroom, so we can
    # insist that it is provided during creation.
    'student': ['classroom'],  # todo: add cohort here
    # A cohort is NOT required on creation for teachers and admins b/c that's
    # part of the registration survey, which doesn't happen right away.
    'teacher': [],
    'school_admin': [],
    'researcher': [],
    'god': [],
    'program': [],
    'activity': ['program', 'cohort'],
    'cohort': ['program', 'school'],
    'classroom': ['program', 'cohort', 'user'],
    'school': [],
    'pd': [],
    'email': [],
    'qualtrics_link': [],
}

# If certain ids are available when an entity is created, they also can be
# associated, but no error will be thrown if they're NOT present.
optional_associations = {
    'activity': ['classroom'],
    'school_admin': ['program'],
    'teacher': ['program', 'cohort'],
}

# These encode the redunant, non-normalized associations between users and
# other entities. For instance, by associating a user to a classroom, that
# user is also automatically associated to the corresponding cohort, which
# continues to recursively trigger other associations. See api.Api.associate().
user_association_cascade = {
    'program': [],
    'cohort': ['program', 'school'],
    'classroom': ['cohort','program'],
}
# Same as above, but applied when disassociating from entities. The only
# difference currently is that the cascade does not continue to programs, b/c
# it makes little sense to have a user without a program association.
user_disassociation_cascade = {
    'program': [],
    'cohort': ['school'],
    'classroom': ['cohort',],
}
# todo: should this cascade apply to all entities, not just users?
# todo: how do we disassociate people?

CascadeInfo = namedtuple('CascadeInfo', ['kind', 'property'])
children_cascade = {
    # "cohorts which have a given program in their assc_program_list are
    # children of the program", etc.
    'program':   [CascadeInfo('cohort', 'assc_program_list')],
    'school':    [CascadeInfo('cohort', 'assc_school_list')],
    'cohort':    [CascadeInfo('classroom', 'assc_cohort_list'),
                  CascadeInfo('teacher_activity', 'assc_cohort_list')],
    'teacher':   [CascadeInfo('classroom', 'assc_user_list'),
                  CascadeInfo('teacher_activity', 'teacher'),
                  # The teacher panel creates pd for a teacher outside of
                  # any activity.
                  CascadeInfo('pd', 'scope')],
    'classroom': [CascadeInfo('student_activity', 'assc_classroom_list')],
    'activity':  [CascadeInfo('pd', 'activity')],
    'student':   [CascadeInfo('pd', 'scope')],
}

# at least 8 characters, ascii only
# http://stackoverflow.com/questions/5185326/java-script-regular-expression-for-detecting-non-ascii-characters
password_pattern = r'^[\040-\176]{8,}$'

# Facebook log in
FACEBOOK_APP_ID = ''
FACEBOOK_APP_SECRET = ''

# We want the entity store to ignore these properties, mostly because they
# can change in ways it doesn't expect, and it shouldn't be writing to them
# anyway. These properties will be prefixed with an underscore before being
# sent to the client.
client_private_properties = [
    'modified',
    'auth_id',
    'aggregated',
    'aggregation_data',
    'student_activity_list',
    'stripped_first_name',
    'stripped_last_name',
]

# These properties should never be exposed to the client.
client_hidden_properties = [
    'hashed_password',
    'aggregation_json',  # b/c it's redundant with aggregated_data
]

boolean_url_arguments = [
    'is_archived',
    'is_test',
    'registration_complete',
    'force_create',  # /api/identify
    'reset_history',  # /api/stratify
    'escape_impersonation',  # used in program app path testing, see also api_handlers.ApiHandler
    'public',  # marks pds that can be sent to the client
    'recurse_children',  # used in api_handlers.UpdateHandler
    'preview',  # used in api_handlers.UpdateHandler and SystematicUpdateHandler
    'certified',  # used to certify students in roster
    'roster_complete',  # used to verify that all students on a roster have been entered
]
integer_url_arguments = [
    'activity_ordinal',
    'fetch_size',
    'session_ordinal',  # used in QualtricsLink
]
# UTC timezone, in ISO date format: YYYY-MM-DD
date_url_arguments = [
    'birth_date',
    'scheduled_date',
]
# UTC timezone, in an ISO-like format (missing the 'T' character between
# date and time): YYYY-MM-DD HH:mm:SS
datetime_url_arguments = [
    'start_time',
    'roster_completed_datetime',
]
# Converted to JSON with json.dumps().
json_url_arugments = [
    'activities',
    'pd',
    'proportions',  # /api/stratify
    'attributes',  # /api/stratify
    'status_codes',
    'merge_ids',
]
# JSON only allows strings as dictionary keys. But for these values, we want
# to interpret the keys as numbers (ints).
json_url_arugments_with_numeric_keys = [
    'status_codes',
    'merge_ids',
]
# These arguments are meta-data and are never applicable to specific entities
# or api actions. They appear in url_handlers.BaseHandler.get().
ignored_url_arguments = [
    'escape_impersonation',
    'impersonate,'
]
# also, any normal url argument suffixed with _json will be interpreted as json

# Converted by util.get_request_dictionary()
# Problem: we want to be able to set null values to the server, but
# angular drops these from request strings. E.g. given {a: 1, b: null}
# angular creates the request string '?a=1'
# Solution: translate javascript nulls to a special string, which
# the server will again translate to python None. We use '__null__'
# because is more client-side-ish, given that js and JSON have a null
# value.
# javascript | request string | server
# -----------|----------------|----------
# p = null;  | ?p=__null__    | p = None
url_values = {
    '__null__': None,
}

# In URL query strings, only the string 'true' ever counts as boolean True.
true_strings = ['true']

systematic_update_settings = {
    'lowercase_login': {
        'kind': 'user',
    },
}

# Allowed Student Aliases.
#
# If a cohort has identification_type = 'alias', then students must sign in as
# one of the following names. What students type is put through
# util.clean_string first, so these must be in all lower case.

allowed_student_aliases = [('dapper', 'designer'), ('real', 'ranger'), ('handy', 'harpist'), ('speedy', 'sheriff'), ('loyal', 'lawyer'), ('mellow', 'mechanic'), ('rare', 'reporter'), ('bold', 'butcher'), ('nifty', 'nurse'), ('honest', 'handyman'), ('equal', 'editor'), ('brave', 'banker'), ('clear', 'coach'), ('expert', 'editor'), ('adept', 'author'), ('bold', 'baker'), ('equal', 'explorer'), ('prime', 'pilot'), ('polite', 'pitcher'), ('famous', 'farmer'), ('speedy', 'singer'), ('chief', 'captain'), ('bold', 'banker'), ('calm', 'captain'), ('equal', 'engineer'), ('daring', 'dancer'), ('regal', 'rancher'), ('brave', 'butcher'), ('crafty', 'coach'), ('super', 'senator'), ('joyful', 'judge'), ('free', 'farmer'), ('able', 'archer'), ('jolly', 'judge'), ('bold', 'barber'), ('chief', 'chef'), ('caring', 'chef'), ('speedy', 'senator'), ('rare', 'rancher'), ('brisk', 'baker'), ('early', 'engineer'), ('busy', 'butcher'), ('snappy', 'singer'), ('shiny', 'senator'), ('tidy', 'tailor'), ('clever', 'coach'), ('amused', 'athlete'), ('rapid', 'reporter'), ('smart', 'senator'), ('happy', 'hunter'), ('modern', 'mayor'), ('gifted', 'golfer'), ('regal', 'reporter'), ('candid', 'coach'), ('bouncy', 'banker'), ('modern', 'manager'), ('super', 'sheriff'), ('cool', 'chef'), ('calm', 'coach'), ('dapper', 'dentist'), ('royal', 'ranger'), ('busy', 'barber'), ('gentle', 'gardener'), ('fancy', 'farmer'), ('mellow', 'manager'), ('sharp', 'singer'), ('smart', 'sheriff'), ('giant', 'golfer'), ('posh', 'pitcher'), ('able', 'author'), ('polite', 'painter'), ('honest', 'harpist'), ('real', 'reporter'), ('strong', 'senator'), ('brave', 'barber'), ('modest', 'manager'), ('wise', 'writer'), ('dizzy', 'dentist'), ('chief', 'cook'), ('bouncy', 'barber'), ('dizzy', 'driver'), ('minty', 'musician'), ('able', 'artist'), ('spiffy', 'singer'), ('crafty', 'captain'), ('giddy', 'gardener'), ('jolly', 'jockey'), ('sunny', 'singer'), ('sharp', 'sheriff'), ('active', 'artist'), ('daring', 'designer'), ('modern', 'mechanic'), ('apt', 'athlete'), ('modest', 'musician'), ('mellow', 'musician'), ('dizzy', 'dancer'), ('gifted', 'gardener'), ('rare', 'ranger'), ('spicy', 'senator'), ('modern', 'musician'), ('even', 'explorer'), ('super', 'singer'), ('tidy', 'teacher'), ('fair', 'farmer'), ('dapper', 'director'), ('modest', 'mayor'), ('royal', 'reporter'), ('even', 'engineer'), ('apt', 'author'), ('candid', 'captain'), ('joyful', 'jockey'), ('alert', 'archer'), ('crisp', 'coach'), ('sunny', 'sheriff'), ('bubbly', 'butcher'), ('bright', 'banker'), ('great', 'golfer'), ('calm', 'cook'), ('wise', 'weaver'), ('happy', 'harpist'), ('clever', 'captain'), ('amused', 'author'), ('tidy', 'trainer'), ('caring', 'captain'), ('crafty', 'cook'), ('able', 'athlete'), ('wise', 'welder'), ('crisp', 'chef'), ('royal', 'rancher'), ('honest', 'hunter'), ('snappy', 'senator'), ('minty', 'manager'), ('nifty', 'novelist'), ('active', 'author'), ('spiffy', 'sheriff'), ('clever', 'cook'), ('busy', 'baker'), ('agile', 'archer'), ('candid', 'chef'), ('cool', 'captain'), ('dapper', 'driver'), ('expert', 'explorer'), ('dizzy', 'doctor'), ('bright', 'baker'), ('amused', 'archer'), ('humble', 'hunter'), ('active', 'athlete'), ('bright', 'butcher'), ('rapid', 'ranger'), ('amused', 'artist'), ('posh', 'painter'), ('bubbly', 'barber'), ('brave', 'baker'), ('alert', 'author'), ('strong', 'sheriff'), ('neat', 'nurse'), ('strong', 'singer'), ('daring', 'doctor'), ('tricky', 'tutor'), ('prime', 'painter'), ('minty', 'mechanic'), ('early', 'editor'), ('minty', 'mayor'), ('smart', 'singer'), ('candid', 'cook'), ('cool', 'cook'), ('rapid', 'rancher'), ('brisk', 'butcher'), ('tricky', 'teacher'), ('posh', 'pilot'), ('gentle', 'golfer'), ('clever', 'chef'), ('apt', 'artist'), ('tricky', 'tailor'), ('apt', 'archer'), ('agile', 'artist'), ('caring', 'coach'), ('busy', 'banker'), ('novel', 'nurse'), ('nice', 'novelist'), ('spicy', 'singer'), ('spiffy', 'senator'), ('witty', 'weaver'), ('calm', 'chef'), ('bubbly', 'baker'), ('brisk', 'banker'), ('agile', 'author'), ('witty', 'welder'), ('sunny', 'senator'), ('humble', 'handyman'), ('clear', 'captain'), ('regal', 'ranger'), ('alert', 'athlete'), ('nice', 'nurse'), ('shiny', 'singer'), ('giddy', 'golfer'), ('great', 'gardener'), ('giant', 'gardener'), ('early', 'explorer'), ('sharp', 'senator'), ('novel', 'novelist'), ('adept', 'archer'), ('modest', 'mechanic'), ('tricky', 'trainer'), ('polite', 'pilot'), ('bright', 'barber'), ('witty', 'writer'), ('prime', 'poet'), ('grand', 'gardener'), ('adept', 'athlete'), ('clear', 'cook'), ('frank', 'farmer'), ('polite', 'poet'), ('lucky', 'lawyer'), ('chief', 'coach'), ('adept', 'artist'), ('neat', 'novelist'), ('caring', 'cook'), ('clear', 'chef'), ('handy', 'handyman'), ('tidy', 'tutor'), ('snappy', 'sheriff'), ('alert', 'artist'), ('expert', 'engineer'), ('daring', 'driver'), ('fast', 'farmer'), ('crafty', 'chef'), ('bouncy', 'butcher'), ('crisp', 'cook'), ('mellow', 'mayor'), ('dapper', 'dancer'), ('brisk', 'barber'), ('grand', 'golfer'), ('bouncy', 'baker'), ('daring', 'dentist'), ('cool', 'coach'), ('dizzy', 'director'), ('dapper', 'doctor'), ('real', 'rancher'), ('shiny', 'sheriff'), ('handy', 'hunter'), ('posh', 'poet'), ('dizzy', 'designer'), ('humble', 'harpist'), ('bubbly', 'banker'), ('even', 'editor'), ('happy', 'handyman'), ('daring', 'director'), ('crisp', 'captain'), ('spicy', 'sheriff'), ('prime', 'pitcher'), ('active', 'archer'), ('agile', 'athlete'), ('minty', 'inventor'), ('polite', 'director'), ('caring', 'lawyer'), ('sharp', 'explorer'), ('wise', 'teacher'), ('apt', 'teacher'), ('fair', 'dancer'), ('busy', 'hunter'), ('dizzy', 'ranger'), ('adept', 'butcher'), ('smart', 'tailor'), ('shiny', 'engineer'), ('active', 'farmer'), ('neat', 'director'), ('famous', 'rancher'), ('cool', 'hunter'), ('loyal', 'welder'), ('regal', 'hunter'), ('amused', 'trainer'), ('free', 'chef'), ('grand', 'jockey'), ('even', 'banker'), ('smart', 'hunter'), ('dizzy', 'baker'), ('cool', 'engineer'), ('jolly', 'butcher'), ('shiny', 'tutor'), ('even', 'lawyer'), ('candid', 'teacher'), ('clear', 'doctor'), ('frank', 'archer'), ('famous', 'poet'), ('smart', 'doctor'), ('free', 'harpist'), ('jolly', 'doctor'), ('fair', 'singer'), ('equal', 'athlete'), ('early', 'handyman'), ('active', 'nurse'), ('candid', 'musician'), ('handy', 'gardener'), ('lucky', 'doctor'), ('clever', 'painter'), ('modest', 'poet'), ('neat', 'captain'), ('crafty', 'designer'), ('modest', 'dancer'), ('snappy', 'inventor'), ('speedy', 'farmer'), ('gentle', 'judge'), ('nifty', 'golfer'), ('equal', 'gardener'), ('speedy', 'explorer'), ('lucky', 'welder'), ('rapid', 'welder'), ('cool', 'lawyer'), ('shiny', 'novelist'), ('able', 'baker'), ('able', 'butcher'), ('giddy', 'doctor'), ('even', 'pilot'), ('rare', 'teacher'), ('spicy', 'novelist'), ('tricky', 'athlete'), ('wise', 'baker'), ('clear', 'trainer'), ('great', 'teacher'), ('honest', 'baker'), ('shiny', 'weaver'), ('calm', 'jockey'), ('novel', 'baker'), ('dizzy', 'teacher'), ('chief', 'lawyer'), ('witty', 'umpire'), ('bouncy', 'golfer'), ('modern', 'artist'), ('novel', 'coach'), ('busy', 'sheriff'), ('sunny', 'barber'), ('humble', 'archer'), ('honest', 'dentist'), ('candid', 'senator'), ('crisp', 'pitcher'), ('royal', 'tailor'), ('gentle', 'hunter'), ('brave', 'welder'), ('smart', 'ranger'), ('snappy', 'engineer'), ('tricky', 'director'), ('rapid', 'farmer'), ('busy', 'pitcher'), ('even', 'director'), ('calm', 'gardener'), ('lucky', 'singer'), ('spicy', 'harpist'), ('novel', 'musician'), ('crafty', 'judge'), ('early', 'author'), ('joyful', 'teacher'), ('busy', 'singer'), ('giant', 'rancher'), ('active', 'cook'), ('honest', 'manager'), ('brave', 'artist'), ('giddy', 'author'), ('early', 'doctor'), ('jolly', 'tailor'), ('witty', 'dancer'), ('candid', 'sheriff'), ('active', 'captain'), ('handy', 'tailor'), ('gentle', 'pilot'), ('humble', 'ranger'), ('speedy', 'golfer'), ('giant', 'umpire'), ('alert', 'mayor'), ('free', 'captain'), ('mellow', 'banker'), ('fancy', 'banker'), ('snappy', 'athlete'), ('agile', 'writer'), ('bubbly', 'mechanic'), ('strong', 'musician'), ('apt', 'inventor'), ('giddy', 'novelist'), ('chief', 'nurse'), ('minty', 'coach'), ('active', 'ranger'), ('equal', 'umpire'), ('expert', 'dentist'), ('gifted', 'designer'), ('equal', 'archer'), ('adept', 'nurse'), ('even', 'butcher'), ('caring', 'dentist'), ('agile', 'inventor'), ('giddy', 'ranger'), ('loyal', 'novelist'), ('bouncy', 'artist'), ('grand', 'tailor'), ('mellow', 'archer'), ('witty', 'ranger'), ('wise', 'engineer'), ('clever', 'lawyer'), ('minty', 'dancer'), ('speedy', 'editor'), ('smart', 'baker'), ('fair', 'banker'), ('calm', 'director'), ('novel', 'umpire'), ('giddy', 'welder'), ('giddy', 'captain'), ('dapper', 'umpire'), ('rare', 'baker'), ('fast', 'dancer'), ('jolly', 'ranger'), ('bright', 'designer'), ('daring', 'umpire'), ('tidy', 'inventor'), ('adept', 'judge'), ('spicy', 'captain'), ('wise', 'novelist'), ('tidy', 'designer'), ('tidy', 'driver'), ('chief', 'editor'), ('fair', 'rancher'), ('loyal', 'artist'), ('amused', 'tailor'), ('humble', 'director'), ('smart', 'novelist'), ('spiffy', 'novelist'), ('speedy', 'engineer'), ('bubbly', 'ranger'), ('royal', 'lawyer'), ('modest', 'golfer'), ('handy', 'tutor'), ('nifty', 'dentist'), ('fair', 'manager'), ('jolly', 'chef'), ('modern', 'archer'), ('candid', 'artist'), ('polite', 'ranger'), ('bold', 'mayor'), ('free', 'dentist'), ('tricky', 'archer'), ('spiffy', 'tutor'), ('equal', 'ranger'), ('lucky', 'nurse'), ('even', 'designer'), ('smart', 'umpire'), ('clever', 'pitcher'), ('free', 'gardener'), ('smart', 'judge'), ('strong', 'nurse'), ('lucky', 'athlete'), ('sunny', 'archer'), ('clear', 'engineer'), ('tricky', 'banker'), ('smart', 'farmer'), ('witty', 'painter'), ('giant', 'baker'), ('honest', 'rancher'), ('prime', 'umpire'), ('snappy', 'driver'), ('grand', 'harpist'), ('spicy', 'jockey'), ('clear', 'inventor'), ('regal', 'manager'), ('expert', 'pilot'), ('chief', 'senator'), ('modern', 'tutor'), ('jolly', 'handyman'), ('speedy', 'ranger'), ('crafty', 'gardener'), ('bold', 'driver'), ('jolly', 'weaver'), ('expert', 'singer'), ('calm', 'singer'), ('crafty', 'umpire'), ('joyful', 'welder'), ('real', 'senator'), ('amused', 'mayor'), ('happy', 'engineer'), ('sharp', 'banker'), ('giant', 'reporter'), ('spiffy', 'inventor'), ('fast', 'dentist'), ('brave', 'painter'), ('even', 'athlete'), ('sharp', 'dancer'), ('tidy', 'handyman'), ('caring', 'baker'), ('novel', 'editor'), ('posh', 'umpire'), ('handy', 'manager'), ('super', 'director'), ('shiny', 'explorer'), ('sharp', 'gardener'), ('bold', 'senator'), ('humble', 'singer'), ('rare', 'tailor'), ('active', 'director'), ('tricky', 'handyman'), ('lucky', 'tailor'), ('bold', 'manager'), ('caring', 'musician'), ('busy', 'inventor'), ('spiffy', 'lawyer'), ('spiffy', 'driver'), ('regal', 'judge'), ('speedy', 'nurse'), ('bright', 'mayor'), ('grand', 'operator'), ('minty', 'butcher'), ('brave', 'musician'), ('busy', 'nurse'), ('apt', 'writer'), ('crafty', 'manager'), ('super', 'painter'), ('royal', 'tutor'), ('gentle', 'nurse'), ('tricky', 'artist'), ('giant', 'handyman'), ('minty', 'doctor'), ('busy', 'farmer'), ('spicy', 'handyman'), ('great', 'artist'), ('giant', 'painter'), ('early', 'welder'), ('prime', 'novelist'), ('wise', 'captain'), ('adept', 'captain'), ('daring', 'harpist'), ('agile', 'pilot'), ('adept', 'engineer'), ('regal', 'teacher'), ('mellow', 'pilot'), ('equal', 'baker'), ('minty', 'hunter'), ('wise', 'singer'), ('fast', 'author'), ('fast', 'director'), ('sunny', 'handyman'), ('giant', 'lawyer'), ('novel', 'manager'), ('calm', 'designer'), ('brave', 'tailor'), ('busy', 'dancer'), ('bright', 'director'), ('loyal', 'handyman'), ('dizzy', 'editor'), ('dizzy', 'lawyer'), ('wise', 'mayor'), ('cool', 'musician'), ('clear', 'manager'), ('caring', 'welder'), ('cool', 'farmer'), ('crafty', 'pitcher'), ('honest', 'author'), ('cool', 'judge'), ('gifted', 'explorer'), ('dizzy', 'engineer'), ('adept', 'singer'), ('frank', 'handyman'), ('bouncy', 'cook'), ('novel', 'banker'), ('giddy', 'rancher'), ('clever', 'golfer'), ('super', 'artist'), ('spicy', 'painter'), ('wise', 'reporter'), ('sunny', 'pitcher'), ('witty', 'artist'), ('apt', 'dentist'), ('bright', 'singer'), ('mellow', 'trainer'), ('polite', 'dancer'), ('royal', 'driver'), ('super', 'tailor'), ('famous', 'butcher'), ('early', 'chef'), ('caring', 'engineer'), ('minty', 'editor'), ('adept', 'golfer'), ('agile', 'judge'), ('minty', 'ranger'), ('posh', 'driver'), ('real', 'inventor'), ('dapper', 'tutor'), ('tricky', 'ranger'), ('posh', 'explorer'), ('rare', 'trainer'), ('minty', 'pitcher'), ('posh', 'operator'), ('mellow', 'sheriff'), ('even', 'hunter'), ('bright', 'umpire'), ('neat', 'golfer'), ('early', 'teacher'), ('bold', 'editor'), ('wise', 'editor'), ('handy', 'engineer'), ('regal', 'dancer'), ('clear', 'archer'), ('super', 'archer'), ('clever', 'welder'), ('fast', 'trainer'), ('giant', 'operator'), ('grand', 'doctor'), ('expert', 'tutor'), ('tricky', 'operator'), ('agile', 'butcher'), ('frank', 'doctor'), ('smart', 'explorer'), ('speedy', 'jockey'), ('giant', 'weaver'), ('bold', 'harpist'), ('real', 'baker'), ('agile', 'painter'), ('chief', 'baker'), ('strong', 'dentist'), ('minty', 'writer'), ('novel', 'painter'), ('active', 'inventor'), ('able', 'editor'), ('honest', 'athlete'), ('snappy', 'jockey'), ('witty', 'reporter'), ('dizzy', 'harpist'), ('lucky', 'farmer'), ('spiffy', 'poet'), ('caring', 'poet'), ('honest', 'designer'), ('bold', 'mechanic'), ('alert', 'reporter'), ('real', 'hunter'), ('grand', 'weaver'), ('jolly', 'dancer'), ('spicy', 'rancher'), ('calm', 'farmer'), ('apt', 'driver'), ('honest', 'driver'), ('modest', 'gardener'), ('joyful', 'poet'), ('dapper', 'captain'), ('modern', 'jockey'), ('bubbly', 'handyman'), ('rapid', 'sheriff'), ('brisk', 'archer'), ('candid', 'jockey'), ('bold', 'welder'), ('loyal', 'tutor'), ('candid', 'mayor'), ('expert', 'dancer'), ('lucky', 'umpire'), ('joyful', 'inventor'), ('regal', 'weaver'), ('frank', 'gardener'), ('rapid', 'athlete'), ('nifty', 'director'), ('wise', 'athlete'), ('real', 'designer'), ('daring', 'farmer'), ('nifty', 'pilot'), ('brisk', 'rancher'), ('crisp', 'designer'), ('spicy', 'coach'), ('real', 'banker'), ('rapid', 'umpire'), ('active', 'engineer'), ('shiny', 'dentist'), ('chief', 'singer'), ('early', 'judge'), ('modest', 'cook'), ('super', 'golfer'), ('clever', 'nurse'), ('amused', 'novelist'), ('caring', 'writer'), ('honest', 'weaver'), ('able', 'engineer'), ('honest', 'chef'), ('dapper', 'cook'), ('witty', 'poet'), ('mellow', 'singer'), ('crisp', 'novelist'), ('apt', 'mechanic'), ('giddy', 'baker'), ('able', 'nurse'), ('honest', 'judge'), ('sunny', 'reporter'), ('grand', 'pilot'), ('bubbly', 'athlete'), ('dizzy', 'jockey'), ('rapid', 'harpist'), ('royal', 'welder'), ('candid', 'reporter'), ('modest', 'trainer'), ('spiffy', 'baker'), ('super', 'author'), ('handy', 'trainer'), ('nice', 'singer'), ('active', 'senator'), ('super', 'farmer'), ('bouncy', 'mayor'), ('regal', 'sheriff'), ('bouncy', 'nurse'), ('alert', 'chef'), ('prime', 'designer'), ('calm', 'driver'), ('prime', 'weaver'), ('rapid', 'senator'), ('cool', 'author'), ('humble', 'athlete'), ('dizzy', 'cook'), ('modest', 'lawyer'), ('sharp', 'pilot'), ('snappy', 'director'), ('equal', 'pilot'), ('free', 'teacher'), ('fair', 'doctor'), ('early', 'designer'), ('able', 'inventor'), ('royal', 'operator'), ('dapper', 'athlete'), ('fancy', 'butcher'), ('busy', 'captain'), ('regal', 'farmer'), ('jolly', 'artist'), ('crafty', 'engineer'), ('dapper', 'farmer'), ('modern', 'butcher'), ('able', 'trainer'), ('tidy', 'director'), ('agile', 'umpire'), ('tricky', 'weaver'), ('regal', 'handyman'), ('rare', 'handyman'), ('witty', 'coach'), ('grand', 'designer'), ('rare', 'sheriff'), ('nice', 'tailor'), ('famous', 'director'), ('neat', 'teacher'), ('snappy', 'lawyer'), ('bright', 'manager'), ('spicy', 'manager'), ('fancy', 'chef'), ('dizzy', 'artist'), ('adept', 'handyman'), ('sharp', 'inventor'), ('nifty', 'trainer'), ('adept', 'musician'), ('real', 'trainer'), ('tricky', 'judge'), ('smart', 'nurse'), ('polite', 'chef'), ('even', 'manager'), ('gentle', 'jockey'), ('amused', 'tutor'), ('spiffy', 'editor'), ('gifted', 'ranger'), ('rapid', 'writer'), ('gentle', 'ranger'), ('nice', 'banker'), ('mellow', 'engineer'), ('joyful', 'rancher'), ('active', 'operator'), ('crafty', 'baker'), ('clever', 'harpist'), ('posh', 'golfer'), ('joyful', 'pitcher'), ('great', 'novelist'), ('modern', 'pitcher'), ('fast', 'engineer'), ('witty', 'judge'), ('great', 'welder'), ('expert', 'archer'), ('spiffy', 'writer'), ('adept', 'baker'), ('tricky', 'hunter'), ('royal', 'umpire'), ('strong', 'pitcher'), ('calm', 'harpist'), ('gentle', 'dancer'), ('even', 'dentist'), ('adept', 'coach'), ('royal', 'writer'), ('sharp', 'director'), ('grand', 'artist'), ('sharp', 'hunter'), ('smart', 'director'), ('bubbly', 'director'), ('snappy', 'umpire'), ('caring', 'tailor'), ('great', 'doctor'), ('brave', 'nurse'), ('loyal', 'dentist'), ('expert', 'lawyer'), ('modest', 'artist'), ('active', 'rancher'), ('chief', 'poet'), ('regal', 'coach'), ('adept', 'tutor'), ('modest', 'captain'), ('mellow', 'inventor'), ('busy', 'driver'), ('sunny', 'mayor'), ('strong', 'writer'), ('giddy', 'judge'), ('apt', 'director'), ('crafty', 'painter'), ('equal', 'barber'), ('novel', 'mayor'), ('nifty', 'athlete'), ('brisk', 'judge'), ('wise', 'coach'), ('alert', 'pitcher'), ('expert', 'painter'), ('prime', 'singer'), ('expert', 'pitcher'), ('candid', 'explorer'), ('crafty', 'athlete'), ('modern', 'operator'), ('fair', 'painter'), ('speedy', 'author'), ('expert', 'welder'), ('crisp', 'engineer'), ('modern', 'pilot'), ('dizzy', 'operator'), ('polite', 'designer'), ('mellow', 'gardener'), ('prime', 'cook'), ('even', 'poet'), ('novel', 'operator'), ('brisk', 'designer'), ('real', 'mayor'), ('snappy', 'explorer'), ('happy', 'weaver'), ('rare', 'novelist'), ('royal', 'baker'), ('wise', 'ranger'), ('nice', 'reporter'), ('candid', 'mechanic'), ('speedy', 'operator'), ('super', 'tutor'), ('polite', 'golfer'), ('bubbly', 'pitcher'), ('spiffy', 'teacher'), ('brisk', 'poet'), ('gentle', 'author'), ('speedy', 'gardener'), ('humble', 'tailor'), ('fair', 'baker'), ('bright', 'musician'), ('apt', 'ranger'), ('happy', 'trainer'), ('even', 'pitcher'), ('grand', 'athlete'), ('novel', 'barber'), ('clever', 'athlete'), ('early', 'harpist'), ('free', 'athlete'), ('calm', 'handyman'), ('tidy', 'dancer'), ('amused', 'dentist'), ('snappy', 'novelist'), ('modern', 'doctor'), ('brave', 'golfer'), ('bouncy', 'hunter'), ('fast', 'novelist'), ('gifted', 'trainer'), ('free', 'editor'), ('cool', 'barber'), ('wise', 'pilot'), ('bold', 'cook'), ('giddy', 'harpist'), ('amused', 'barber'), ('loyal', 'doctor'), ('jolly', 'manager'), ('happy', 'poet'), ('modest', 'inventor'), ('regal', 'lawyer'), ('fast', 'senator'), ('alert', 'operator'), ('neat', 'cook'), ('busy', 'artist'), ('lucky', 'designer'), ('gifted', 'archer'), ('giddy', 'inventor'), ('posh', 'sheriff'), ('loyal', 'ranger'), ('dizzy', 'nurse'), ('dizzy', 'athlete'), ('handy', 'butcher'), ('fair', 'writer'), ('strong', 'chef'), ('spicy', 'chef'), ('great', 'inventor'), ('apt', 'mayor'), ('able', 'jockey'), ('bright', 'sheriff'), ('gifted', 'pilot'), ('amused', 'captain'), ('loyal', 'weaver'), ('great', 'reporter'), ('nifty', 'baker'), ('honest', 'tailor'), ('bouncy', 'rancher'), ('handy', 'sheriff'), ('sharp', 'welder'), ('loyal', 'singer'), ('novel', 'harpist'), ('bright', 'inventor'), ('nice', 'farmer'), ('smart', 'harpist'), ('tidy', 'harpist'), ('bold', 'teacher'), ('fast', 'tutor'), ('nifty', 'harpist'), ('frank', 'editor'), ('clear', 'mechanic'), ('shiny', 'designer'), ('novel', 'archer'), ('active', 'singer'), ('sunny', 'ranger'), ('honest', 'welder'), ('regal', 'novelist'), ('equal', 'weaver'), ('fair', 'welder'), ('able', 'lawyer'), ('speedy', 'lawyer'), ('alert', 'writer'), ('famous', 'jockey'), ('dapper', 'pitcher'), ('modern', 'author'), ('agile', 'engineer'), ('crafty', 'harpist'), ('modern', 'captain'), ('clear', 'operator'), ('bubbly', 'novelist'), ('clear', 'dancer'), ('rapid', 'cook'), ('gentle', 'editor'), ('sunny', 'designer'), ('brave', 'trainer'), ('jolly', 'welder'), ('novel', 'pitcher'), ('smart', 'painter'), ('strong', 'tutor'),]


def make_aliases():
    """Generate aliases. MAKES A DIFFERENT LIST EACH TIME.

    Puts alliterative aliases, where first and last names start with the same
    letter, up front where they are more likely to be used.

    Included here only for reference. The actual list is hard-coded.
    """

    occupations = ["archer", "athlete", "artist", "author", "baker", "banker", "barber", "butcher", "captain", "chef", "coach", "cook", "dancer", "dentist", "designer", "director", "doctor", "driver", "editor", "engineer", "explorer", "farmer", "gardener", "golfer", "handyman", "harpist", "hunter", "inventor", "jockey", "judge", "lawyer", "manager", "mayor", "mechanic", "musician", "novelist", "nurse", "operator", "painter", "pilot", "pitcher", "poet", "rancher", "ranger", "reporter", "senator", "sheriff", "singer", "tailor", "teacher", "trainer", "tutor", "umpire", "weaver", "welder", "writer"]
    adjectives = ["able", "active", "adept", "agile", "alert", "amused", "apt", "bold", "bouncy", "brave", "bright", "brisk", "bubbly", "busy", "calm", "candid", "caring", "chief", "clear", "clever", "cool", "crafty", "crisp", "dapper", "daring", "dizzy", "early", "equal", "even", "expert", "fair", "famous", "fancy", "fast", "frank", "free", "gentle", "giant", "giddy", "gifted", "grand", "great", "handy", "happy", "honest", "humble", "jolly", "joyful", "loyal", "lucky", "mellow", "minty", "modern", "modest", "neat", "nice", "nifty", "novel", "polite", "posh", "prime", "rapid", "rare", "real", "regal", "royal", "sharp", "shiny", "smart", "snappy", "speedy", "spicy", "spiffy", "strong", "sunny", "super", "tidy", "tricky", "wise", "witty"]

    alliterative_aliases = []
    other_aliases = []
    for a in adjectives:
        for o in occupations:
            alias = (a, o)
            if a[0] == o[0]:
                alliterative_aliases.append(alias)
            else:
                other_aliases.append(alias)

    diff_to_1000 = 1000 - len(alliterative_aliases)
    padding = [random.choice(other_aliases) for x in range(diff_to_1000)]
    random.shuffle(alliterative_aliases)
    random.shuffle(padding)
    return alliterative_aliases + padding


def make_alias_csv(aliases):
    """Creates a csv string suitable for importing to Excel.

    CAM created this to make a spreadsheet we could share with schools.
    Included here just for reference.
    """
    names = []
    for a in aliases:
        first = a[0][:1].upper() + a[0][1:]
        last = a[1][:1].upper() + a[1][1:]
        names.append(first + "," + last)
    return "\n".join(names)


# Email settings
#
# Platform generated emails can only be sent from email addresses that have
# viewer permissions or greater on app engine.  So if you are going to change
# this please add the sender as an application viewer on
# https://appengine.google.com/permissions?app_id=s~pegasusplatform
#
# There are other email options if this doesn't suit your needs check the
# google docs.
# https://developers.google.com/appengine/docs/python/mail/sendingmail
from_yellowstone_email_address = ''
# This address should forward to the development team
# Ben says: I could not use  directly because of
# limited permissions, so I created this gmail account which forwards all its
# mail there.
to_dev_team_email_address = ''
# * spam prevention *
# time between emails
# if we exceed this for a give to address, an error will be logged
suggested_delay_between_emails = 1      # 1 day
# whitelist
# some addessess we spam, like our own
# * we allow us to spam anyone at a *@perts.net domain so
# this is the best address for an admin
addresses_we_can_spam = [
    to_dev_team_email_address,
]

reminder_summary_recipients = [
    to_dev_team_email_address,
    from_yellowstone_email_address,
]

# Hard-coded emails

should_deliver_smtp_dev = False

forgot_password_subject = "Password reset requested."
# Hanging spaces are intentional!
# http://markdown-guide.readthedocs.org/en/latest/basics.html#line-return
# Note: you must run a .format() on this string to interpolate the token.
forgot_password_body = """
Greetings,

A password reset has been requested for your PERTS account. Please
use [this link][1] to reset your password:

[1]: https://www.perts.net{} "Temporary password reset link"

This link will expire in one hour. If you did not request this reset, please
email us at  and let us know.

Yours truly,
The PERTS Team
"""

change_password_subject = "Your PERTS password has been changed."
# Hanging spaces are intentional!
# http://markdown-guide.readthedocs.org/en/latest/basics.html#line-return
change_password_body = """
Greetings,

The password on your PERTS account has been changed.

If you did not request this change, please email us at
 and let us know.

Yours truly,
The PERTS Team
"""
