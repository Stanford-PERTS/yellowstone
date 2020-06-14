# Use this as a template for future programs. Any less data will cause problems
# with generating activity entities, etc.
# student_config = {
#     'outline': [
#         {
#             'id': 'session_1',
#             'name': 'Session 1',
#             'type': 'activity',
#             'activity_ordinal': 1,
#             'nodes': [],
#         },
#     ]
# }

# teacher_config = {
#     'outline': [
#         {
#             'id': 'session_1',
#             'name': 'Session 1',
#             'type': 'activity',
#             'activity_ordinal': 1,
#             'nodes': [],
#         },
#     ]
# }

name = "Test Program"

student_config = {
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
            'id': 'alternate_menu',
            'name': 'Alternate Student Menu',
            'nodes': [
                'alternate_menu',
            ],
        },
        {
            'id': 'session_1',
            'name': 'Session 1',
            'type': 'activity',
            'activity_ordinal': 1,
            # if it is this day or after, then the session is open
            'date_open': '2014-01-06',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-12-31',
            'nodes': [
                'randomizeCondition()',
                'prepareToRedirect(1)',
                'intro',
                'goodbye',
            ],
        },
        {
            'id': 'session_1_alternate',
            'name': 'Session 1 Alternate Activity',
            'type': 'alternate',
            'activity_ordinal': 1,
            'nodes': [
                'alternate',
            ],
        },
        {
            'id': 'session_2_alternate',
            'name': 'Session 2 Alternate Activity',
            'type': 'alternate',
            'activity_ordinal': 2,
            'nodes': [
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
            'date_open': '2014-03-03',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-12-31',
            'date_open_relative_to': ['student', 1],  # user type, ordinal
            'date_open_relative_interval': 45,  # days after
            'nodes': [
                'prepareToRedirect(2)',
                'intro',
                'goodbye',
            ],
        },

    ],

    # Would be true if this subprogram used qualtrics links. It's not necessary
    # to explicitly set this as False; this is just here for documentation.
    #qualtrics_based: False,

    'stratifiers': {
        'student_condition': {'treatment': 1, 'control': 1},
    },

    
    'reminder_emails': [
        {
            'activity_ordinal': 1,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'Your first student session is coming up in 3 days',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have your first Student Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 1,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': 0,
            'reply_to': '',
            'from_address': '',
            'subject': 'Your first student session is today',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have your first Student Session today, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 2,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'Your second student session is coming up in 3 days',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have your second Student Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 2,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': 0,
            'reply_to': '',
            'from_address': '',
            'subject': 'Your second student session is today',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have your second Student Session today, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
    ]

}

teacher_config = {
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
            'name': 'Teacher Menu',
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
            'date_open': '2014-01-13',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-06-15',
            'date_open_relative_to': ['student', 1],  # user type, ordinal
            'date_open_relative_interval': 1,  # days after
            'nodes': [
                'markProgress(0)',
                'randomizeCondition()',
                'student_session',
                'intro',
                'professional_development',
                'teacher_experience',
                'toi',
                'markProgress(25)',
                'mistakes_feelings',
                'mistakes_promo',
                'math_anx',
                'work_orientation',
                'teacher_burnout',
                'demographics',
                'markProgress(50)',
                'conditionBranch(session_1)',
                'treatment',
                'activity',
                'markProgress(100)',
                'goToGoodbye(session_1)',
                'control',
                'markProgress(100)',
                'goodbye',
            ],
        },
        {
            'id': 'session_2',
            'name': 'Session 2',
            'type': 'activity',
            'activity_ordinal': 2,
            'date_open': '2014-01-13',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-06-15',
            'date_open_relative_to': ['teacher', 1],  # user type, ordinal
            'date_open_relative_interval': 1,  # days after
            'nodes': [
                'markProgress(0)',
                'activityFollowup',
                'feedbackBranch1(session_2)',
                'activityYes',
                'feedbackBranch2(session_2)',
                'activityNo',
                'treatment',
                'markProgress(50)',
                'activity',
                'markProgress(100)',
                'goodbye',
            ],
        },
        {
            'id': 'session_3',
            'name': 'Session 3',
            'type': 'activity',
            'activity_ordinal': 3,
            'date_open': '2014-01-13',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-06-15',
            'date_open_relative_to': ['teacher', 2],  # user type, ordinal
            'date_open_relative_interval': 1,  # days after
            'nodes': [
                'markProgress(0)',
                'activityFollowup',
                'feedbackBranch1(session_3)',
                'activityYes',
                'feedbackBranch2(session_3)',
                'activityNo',
                'treatment',
                'markProgress(50)',
                'activity',
                'markProgress(100)',
                'goodbye',
            ],
        },
        {
            'id': 'session_4',
            'name': 'Session 4',
            'type': 'activity',
            'activity_ordinal': 4,
            'date_open': '2014-01-13',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-06-15',
            'date_open_relative_to': ['teacher', 3],  # user type, ordinal
            'date_open_relative_interval': 1,  # days after
            'nodes': [
                'markProgress(0)',
                'activityFollowup',
                'feedbackBranch1(session_4)',
                'activityYes',
                'feedbackBranch2(session_4)',
                'activityNo',
                'treatment',
                'markProgress(50)',
                'activity',
                'markProgress(100)',
                'goodbye',
            ],
        },
        {
            'id': 'session_5',
            'name': 'Follow up',
            'type': 'activity',
            'activity_ordinal': 5,
            'date_open': '2014-01-13',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-06-15',
            'date_open_relative_to': ['teacher', 1],  # user type, ordinal
            'date_open_relative_interval': 21,  # days after
            'nodes': [
                'markProgress(0)',
                'conditionBranch(session_5)',
                'activityFollowup',
                'feedbackBranch1(session_5)',
                'activityYes',
                'feedbackBranch2(session_5)',
                'activityNo',
                'treatment',
                'toi',
                'mistakes_feelings',
                'mistakes_promo',
                'work_orientation',
                'teacher_burnout',
                'teacher_talk',
                'user_feedback',
                'markProgress(100)',
                'goToGoodbye(session_5)',
                'markProgress(100)',
                'goodbye',
            ],
        },
    ],
    
    # Would be true if this subprogram used qualtrics links. It's not necessary
    # to explicitly set this as False; this is just here for documentation.
    #qualtrics_based: False,

    'stratifiers': {
        'teacher_condition': {'treatment': 1, 'control': 1},
        # 'teacher_condition': {'treatment': 1},
    },
    
    'reminder_emails': [
        {
            'activity_ordinal': 1,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session coming up in 3 days',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 1,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': -0,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session scheduled for today',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session today, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 2,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session coming up in 3 days',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 2,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': -0,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session scheduled for today',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session today, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 3,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session coming up in 3 days',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 3,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': -0,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session scheduled for today',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session today, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 4,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session coming up in 3 days',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 4,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': -0,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session scheduled for today',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session today, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 5,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session coming up in 3 days',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 5,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': -0,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session scheduled for today',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session today, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 1,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a student session coming up in 3 days',
            'body': "Dear {{user.name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
    ]
}
