
name = "Middle School Transition Program"

registration_email_subject = "PERTS Middle School Transition Program registration confirmation"

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

Please check with the teachers to make sure they are prepared for the upcoming
session. It is very important to keep to the schedule, but if necessary, please
work with teachers to reschedule so that all project-related activities can be
completed on time.

Warm regards,  
The PERTS Team"""

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
            'date_open': '2014-09-15',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-11-15',
            'nodes': [
                'randomizeCondition()',
                'getQualtricsLinks()',
                'goToQualtrics(1)',
            ],
            # Emotion Regulation 2014 Fall OFFICIAL Session 1
            'qualtrics_default_link': 'https://sshs.qualtrics.com/SE/?SID=SV_0e0PYfBnIOHQGdn',
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
            'date_open': '2014-09-15',
            'date_open_relative_to': ['student', 1],  # user type, ordinal
            'date_open_relative_interval': 7,  # days after
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-11-15',
            'date_closed_relative_to': ['student', 1],  # user type, ordinal
            'date_closed_relative_interval': 28,  # days after
            'nodes': [
                # If, for any reason, a student's data wasn't set up right by
                # going through session 1, these functions should be called
                # again to make sure it's right for session 2. Consequently,
                # these functions should also be idempotent.
                'randomizeCondition()',
                'getQualtricsLinks()',
                'goToQualtrics(2)',
            ],
            # Emotion Regulation 2014 Fall OFFICIAL Session 2
            'qualtrics_default_link': 'https://sshs.qualtrics.com/SE/?SID=SV_brLIDoIzd1fPN65',
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
        {
            'id': 'session_3',
            'name': 'Session 3',
            'type': 'activity',
            'activity_ordinal': 3,
            # This combines with the relative dates; users won't be allowed
            # in until the LATEST of the two dates.
            'date_open': '2014-09-15',
            'date_open_relative_to': ['student', 2],  # user type, ordinal
            'date_open_relative_interval': 7,  # days after
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-12-02',
            'nodes': [
                'randomizeCondition()',
                'getQualtricsLinks()',
                'goToQualtrics(3)',
            ],
            # Emotion Regulation 2014 Fall OFFICIAL Session 3
            'qualtrics_default_link': 'https://sshs.qualtrics.com/SE/?SID=SV_9SUryDnrICnBKLj',
        },
        {
            'id': 'session_3_alternate',
            'name': 'Session 3 Alternate Activity',
            'type': 'alternate',
            'activity_ordinal': 3,
            'nodes': [
                'markStudentRefusal(3)',
                'alternate',
            ],
        },
    ],

    'stratifiers': {
        'student_condition': {'treatment': 1, 'control': 1},
        'all_treatment': {'treatment': 1},
        'all_control': {'control': 1},
    },

    
    # Email greetings, bodies, and closings are first parsed by jinja, with the
    # relevant user, classroom, and activity available. The emailer then parses
    # the resulting text as markdown (https://pypi.python.org/pypi/Markdown).
    'reminder_emails': [
        {
            'activity_ordinal': 1,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'Your first student session is coming up in three days',
            'greeting': reminder_email_greeting,
            'body': "*{{ classroom.name }}* has its first session in "
                    "three days, {{ activity.get_long_form_date_string() }}.",
            'closing': reminder_email_closing,
        },
        {
            'activity_ordinal': 1,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': 0,
            'reply_to': '',
            'from_address': '',
            'subject': 'Your first student session is today',
            'greeting': reminder_email_greeting,
            'body': "*{{ classroom.name }}* has its first session "
                    "today, {{ activity.get_long_form_date_string() }}.",
            'closing': reminder_email_closing,
        },
        {
            'activity_ordinal': 2,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'Your second student session is coming up in three days',
            'greeting': reminder_email_greeting,
            'body': "*{{ classroom.name }}* has its second session in "
                    "three days, {{ activity.get_long_form_date_string() }}.",
            'closing': reminder_email_closing,
        },
        {
            'activity_ordinal': 2,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': 0,
            'reply_to': '',
            'from_address': '',
            'subject': 'Your second student session is today',
            'greeting': reminder_email_greeting,
            'body': "*{{ classroom.name }}* has its second session "
                    "today, {{ activity.get_long_form_date_string() }}.",
            'closing': reminder_email_closing,
        },
    ]

}
