
name = "High School Mindsets"

registration_email_subject = "PERTS High School Mindsets registration confirmation"

# Email subject and body text is first parsed by jinja, then as markdown.
# https://pypi.python.org/pypi/Markdown
# Hanging spaces are intentional!
# http://markdown-guide.readthedocs.org/en/latest/basics.html#line-return
# For registration, the user's email and cohort_id are available.
registration_email_body = """
Welcome!

You've created an account with the %s. We're excited to work with you!

Please [sign in][1] using this email address ({{email}}) and your password.

[1]: https://www.perts.net/login "PERTS log in page"

Yours truly,
The PERTS Team
""" % name

# Email subject and body text is first parsed by jinja, then as markdown.
# https://pypi.python.org/pypi/Markdown
# Hanging spaces are intentional!
# http://markdown-guide.readthedocs.org/en/latest/basics.html#line-return
# For reminder emails, the relevant user, classroom, and activity available.
reminder_email_greeting = """Dear {{user.first_name}},

This is a reminder that """

# Hanging spaces are intentional!
# http://markdown-guide.readthedocs.org/en/latest/basics.html#line-return
reminder_email_closing = """

If you haven't already done so, please [log in to perts.net][1] to
download the instructions for running a session and distribute those to
participating teachers.

[1]: https://www.perts.net/login "PERTS log in page"

Warm regards,
The PERTS Team"""

normal_school_instructions = """Instructions

1. Add a class by clicking on the blue *Add Class* button below.
2. Schedule when classes will participate under the *Date* column. Be sure to
   follow the scheduling guidelines in the *Coordinator Instructions* provided
   on the *Documents* page.
3. Upload student rosters for each class. To upload a roster, click on a class
   under *Class Name*, which will take you to the classroom view. From there,
   click *Add Student(s)*.
4. View important documents by clicking on *Documents* in the dropdown list
   under the *Home* tab at the top of the screen. Here you will be able to find
   the, 1) Coordinator Instructions, 2) Parent Information Letter, and 3)
   Session Instructions.
"""

alias_school_instructions = """Instructions

1. Add a class by clicking on the blue *Add Class* button below.
2. Schedule when classes will participate under the *Date* column. Be sure to
   follow the scheduling guidelines in the *Coordinator Instructions* provided
   on the *Documents* page.
3. Your school is using student aliases! Please use the *Student Alias Sheet*
   provided on the *Documents* page to assign an alias name to each of your
   students. Students will sign in to the program with their code names, NOT
   their real names.
4. View important documents by clicking on *Documents* in the dropdown list
   under the *Home* tab at the top of the screen. Here you will be able to find
   the, 1) Coordinator Instructions, 2) Parent Information Letter, 3) Session
   Instructions, and 4) Student Alias Sheet.
"""

student_config = {
    'qualtrics_based': True,

    'outline': [
        {
            'id': 'start',
            'name': 'Consent',
            'nodes': [
                'checkConsent()',
                'consent',
                'menuBranch()',
            ],
        },
        {
            'id': 'menu',
            'name': 'Student Menu',
            'nodes': [
                'menu',
            ],
        },
        {
            'id': 'demo_end',
            'name': 'Demo Over Message',
            'nodes': [
                'demo_end',
            ],
        },
        {
            'id': 'session_1',
            'name': 'Session 1',
            'type': 'activity',
            'activity_ordinal': 1,
            # if it is this day or after, then the session is open
            'date_open': '2015-01-12',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2017-01-01',
            'nodes': [
                'randomizeCondition()',
                'getQualtricsLinks()',
                'goToQualtrics(1)',
            ],
            'qualtrics_default_link': 'https://sshs.qualtrics.com/SE/?SID=SV_6hAH97hlQgECqOh',
        },
        {
            'id': 'session_1_alternate',
            'name': 'Session 1 Alternate Activity',
            'type': 'alternate',
            'activity_ordinal': 1,
            'nodes': [
                'markStudentRefusal(1)',
                'alternate',
            ],
        },
        {
            'id': 'session_2',
            'name': 'Session 2',
            'type': 'activity',
            'activity_ordinal': 2,
            # This combines with the relative dates; users won't be allowed
            # in until the LATEST of the two dates.
            'date_open': '2015-01-12',
            'date_open_relative_to': ['student', 1],  # user type, ordinal
            'date_open_relative_interval': 14,  # days after
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2017-01-01',
            'date_closed_relative_to': ['student', 1],  # user type, ordinal
            'date_closed_relative_interval': 45,  # days after
            'nodes': [
                # If, for any reason, a student's data wasn't set up right by
                # going through session 1, these functions should be called
                # again to make sure it's right for session 2. Consequently,
                # these functions should also be idempotent.
                'randomizeCondition()',
                'getQualtricsLinks()',
                # Now it's safe to go to Qualtrics.
                'goToQualtrics(2)',
            ],
            'qualtrics_default_link': 'https://sshs.qualtrics.com/SE/?SID=SV_0rDr1cU8ND2g9dr',
        },
        {
            'id': 'session_2_alternate',
            'name': 'Session 2 Alternate Activity',
            'type': 'alternate',
            'activity_ordinal': 2,
            'nodes': [
                'markStudentRefusal(2)',
                'alternate',
            ],
        },
    ],

    'stratifiers': {
        'student_condition': {
            'treatment': 1
        },
    },


    # Email greetings, bodies, and closings are first parsed by jinja, with the
    # relevant user, classroom, and activity available. The emailer then parses
    # the resulting text as markdown (https://pypi.python.org/pypi/Markdown).
    'reminder_emails': [
        # For the National Pilot Dissemination, we don't expect anyone to be
        # scheduling sessions, so don't send any reminder emails!
    ]

}
