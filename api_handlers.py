"""URL Handlers are designed to be simple wrappers over our python API layer.
They generally convert a URL directly to an API function call.
"""

from google.appengine.ext import db
import json
import logging
import os                               # DetectProgramsHandler
import random                           # ForgotPasswordHandler
import re
import string                           # ForgotPasswordHandler
import traceback
import webapp2

from api import Api
from core import SecretValue
from id_model import Classroom, Pd, Program, ResetPasswordToken, User
from named_model import QualtricsLink, Timestamp
import config
import core
import mandrill
import url_handlers
import util

# make sure to turn this off in production!!
# it exposes exception messages
debug = util.is_development()


class ApiHandler(url_handlers.BaseHandler):
    """Superclass for all api-related urls."""

    def do_wrapper(self, *args, **kwargs):
        """Wrap all api calls in a try/catch so the server never breaks when
        the client hits an api URL."""
        try:
            self.write_json(self.do(*args, **kwargs))
        except Exception as error:
            trace = traceback.format_exc()
            # We don't want to tell the public about our exception messages.
            # Just provide the exception type to the client, but log the full
            # details on the server.
            logging.error("{}\n{}".format(error, trace))
            response = {
                'success': False,
                'message': error.__class__.__name__,
            }
            if debug:
                response['message'] = "{}: {}".format(error.__class__.__name__, error)
                response['trace'] = trace
            self.write_json(response)

    def write_json(self, obj):
        r = self.response
        r.headers['Content-Type'] = 'application/json; charset=utf-8'
        r.write(json.dumps(obj))


class ArchiveHandler(ApiHandler):
    """Sets entity.is_archived = True for given entity AND ALL ITS CHILDREN."""
    def do(self, action, id):
        undo = action == 'unarchive'
        success = self.api.archive(id, undo)
        return {'success': success}


class AssociateHandler(ApiHandler):
    """Action is either 'associate' or 'set_owner'."""
    def do(self, action, from_kind, from_id, to_kind, to_id):
        from_klass = core.kind_to_class(from_kind)
        to_klass = core.kind_to_class(to_kind)
        from_entity = from_klass.get_by_id(from_id)
        to_entity = to_klass.get_by_id(to_id)
        from_entity = self.api.associate(action, from_entity, to_entity)

        # We'll want to return this at the end.
        data = from_entity.to_dict()

        # Special case for activity management: when teachers associate with a
        # cohort or classroom for the first time, activity entities need to be
        # created for them.

        init_activities = (
            from_kind == 'user' and from_entity.user_type == 'teacher' and (
                (to_kind == 'cohort' and action == 'associate') or
                (to_kind == 'classroom' and action == 'set_owner')
            )
        )
        if init_activities:
            # To simulate a fresh call, refresh the user in the Api object.
            # This only applies when a user is associating *themselves* with a
            # cohort or classroom. Without this refresh, the new associations
            # created just above won't be there and permissions to associate
            # the new activities will be denied.
            if (self.api.user.id == from_id):
                self.api = Api(from_entity)

            # If the classroom or cohort being associated to is a testing
            # entity, then these activities should also be.
            kwargs = {'is_test': to_entity.is_test}
            program_id = to_entity.assc_program_list[0]
            if to_kind == 'cohort':
                kwargs['cohort_id'] = to_entity.id
                user_type = 'teacher'
            if to_kind == 'classroom':
                kwargs['cohort_id'] = to_entity.assc_cohort_list[0]
                kwargs['classroom_id'] = to_entity.id
                user_type = 'student'
            teacher_id = from_entity.id
            activities = self.api.init_activities(
                user_type, teacher_id, program_id, **kwargs)

            # If these activities are being created FOR the teacher by an admin
            # or researcher, we need to do extra work to make sure those
            # activities are owned by the teacher.
            if self.get_current_user() != from_entity:
                for a in activities:
                    self.api.associate('set_owner', from_entity, a)

            # Include the created activities with the modified entity so the
            # client gets them immediately. This allows client views to update
            # immediately if necessary.
            data['_teacher_activity_list'] = [a.to_dict() for a in activities]

        return {'success': True, 'data': data}


class BatchPutPdHandler(ApiHandler):
    def do(self):
        """Accepts several pd at once as JSON via POST.

        Args:
            pd_batch: List of dictionaries, each with a 'variable' and 'value'
                property.
            ...: All other properties expected of a pd (e.g. user, cohort,
                activity), which will get applied to all the elements of the
                pd_batch list to create a set of pd entities.
        Example:
            {
              "pd_batch": [
                {
                  "variable": "s2__toi_1",
                  "value": 1
                },
                {
                  "variable": "s2__toi_2",
                  "value": 1
                }
              ],
              "activity": "Activity_QD6FnPKYkRjrGfSr0wT7",
              "activity_ordinal": 2,
              "program": "Program_M4OQDVDcS0WjvAn8ujR5",
              "scope": "User_NISmPygw44gxopWrivjg",
              "is_test": false,
            }
        """
        params = util.get_request_dictionary(self.request)
        # We're good at re-trying pds when there's a transaction collision,
        # so demote this to a warning rather than an error, so we don't get
        # so many useless emails.
        try:
            pds = self.api.batch_put_pd(params)
        except db.TransactionFailedError:
            logging.warning("TransactionFailedError: {}".format(params))
            return {'success': False, 'message': "TransactionFailedError"}
        else:
            return {'success': True, 'data': [pd.to_dict() for pd in pds]}


class BatchPutUserHandler(ApiHandler):
    def do(self):
        """Put many users of different names but similar relationships.

        Args:
            user_names: List of dictionaries, each with a 'first_name' and
                'last_name' property.
            ...: All other properties expected of a user (e.g. user_type), which
                will get applied to all the elements of the user_names list.
        Example:
            {
              "user_names": [
                {
                  "first_name": "Deanna",
                  "last_name": "Troi"
                },
                {
                  "first_name": "Beverly",
                  "last_name": "Crusher"
                }
              ],
              "user_type": "student",
              "classroom": "Classroom_XYZ"
            }
        """

        params = util.get_request_dictionary(self.request)
        users = self.api.batch_put_user(params)
        return {'success': True, 'data': [user.to_dict() for user in users]}


class ChangePasswordHandler(ApiHandler):
    """For logged in users to change their password; requires them knowing
    they're existing password."""
    def do(self):
        new_password = self.request.get('new_password') or None
        auth_response = self.authenticate(
            auth_type='direct', username=self.request.get('username'),
            password=self.request.get('current_password'))
        if auth_response is False or auth_response is None:
            return {'success': True, 'data': 'invalid_credentials'}
        user = auth_response
        user.hashed_password = util.hash_password(new_password)
        user.put()

        # Alert the user that their password has been changed.
        mandrill.send(
            to_address=user.login_email,
            subject=config.change_password_subject,
            body=mandrill.render_markdown(config.change_password_body)
        )

        logging.info('api_handlers.ChangePasswordHandler')
        logging.info('sending an email to: {}'.format(user.login_email))

        return {'success': True, 'data': 'changed'}


class CheckClientTestHandler(ApiHandler):
    """Does server-side checks aren't normally allowed for public users."""
    def do(self):
        params = util.get_request_dictionary(self.request)
        cross_site_result = self.cross_site_test(**params['cross_site_test'])
        return {'success': True, 'data': {
            'cross_site_test': cross_site_result,
        }}

    def cross_site_test(self, code, user_id):
        """Checks whether Qualtrics has successfully recorded a pd."""
        user = User.get_by_id(user_id)
        logging.info("Test user: {}".format(user))
        if not user:
            return False

        pd_list = self.internal_api.get('pd', {'variable': 'cross_site_test'},
                                        ancestor=user)
        logging.info("Found pd: {}".format(pd_list))
        if len(pd_list) != 1:
            return False

        pd = pd_list[0]
        logging.info("Matching pd code. Looking for {}, found {}."
                     .format(code, pd.value))

        return pd.value == code


class CreateHandler(ApiHandler):
    def do(self, kind):
        params = util.get_request_dictionary(self.request)
        entity = self.api.create(kind, params)
        data = entity.to_dict()

        # Special case for activity management: when teachers create a
        # classroom for the first time, activity entities need to be created
        # for them.
        if kind == 'classroom':
            teacher_id = params['user']
            is_test = params['is_test'] if 'is_test' in params else False
            activities = self.api.init_activities(
                'student', teacher_id, params['program'],
                cohort_id=params['cohort'], classroom_id=entity.id,
                is_test=is_test)

            # If these activities are being created FOR the teacher by an admin
            # or researcher, we need to do extra work to make sure those
            # activities are owned by the teacher.
            if self.get_current_user().id != teacher_id:
                teacher = self.internal_api.get_from_path('user', teacher_id)
                for a in activities:
                    self.api.associate('set_owner', teacher, a)

            # Include the created activities with the new classroom so the
            # client gets them immediately. We've had problems with eventual
            # consistency here.
            data['_student_activity_list'] = [a.to_dict() for a in activities]

        return {'success': True, 'data': data}


class CreatePublicSchoolHandler(ApiHandler):
    """Allows public users to create schools in "free-for-all" programs."""
    def do(self):
        params = util.get_request_dictionary(self.request)

        # Check that the requested program allows public registration.
        program = self.internal_api.get_from_path('program', params['program'])
        program_config = Program.get_app_configuration(program.abbreviation)
        if not getattr(program_config, 'public_registration', False):
            user = self.get_current_user()
            logging.error("User {} attempted public registration on program "
                          "{}, but it isn't allowed."
                          .format(user, program.abbreviation))

        # Create a school admin based on the user's information.
        # They get the special auth_type 'public', preventing them from
        # appearing in sign-in queries or reset-password queries.
        # However, the user entity will still hold data and be associated with
        # the created schools.
        params['user']['user_type'] = 'school_admin'
        params['user']['auth_id'] = 'public_' + params['user']['login_email']
        school_admin = self.internal_api.create('user', params['user'])

        # If the school already exists, use the id to find the right cohort.
        if 'existing_school_id' in params:
            s_id = params['existing_school_id']
            cohort_list = self.internal_api.get('cohort',
                                               {'assc_school_list': s_id})
            if len(cohort_list) is not 1:
                raise Exception("Problem with public registration: found {} "
                                "cohorts for school {}"
                                .format(len(cohort_list), s_id))
            cohort = cohort_list[0]
            school = None
            classroom = None
            activities = None

        # Otherwise, create a school, cohort, and classroom based on the
        # provided data.
        else:
            school = self.internal_api.create('school', params['new_school'])
            cohort = self.internal_api.create('cohort', {
                'name': params['new_school']['name'],
                'school': school.id,
                'program': program.id,
                'promised_students': params['promised_students'],
            })
            classroom = self.internal_api.create('classroom', {
                'name': 'All Students',
                'program': program.id,
                'cohort': cohort.id,
                'user': school_admin.id,
            })
            activities = self.internal_api.init_activities(
                'student', school_admin.id, program.id, cohort_id=cohort.id,
                classroom_id=classroom.id)

        # Whether the cohort is new or exisiting, make the new user owner of it
        self.internal_api.associate('set_owner', school_admin, cohort)

        # Send an email to the user with all the information they need to
        # participate.
        mandrill.send(
            to_address=school_admin.login_email,
            subject=program_config.registration_email_subject,
            body=mandrill.render_markdown(
                program_config.registration_email_body),
            template_data={'email': school_admin.login_email,
                           'cohort_id': cohort.id}
        )

        logging.info('api_handlers.CreatePublicSchoolHandler')
        logging.info('sending an email to: {}'
                     .format(school_admin.login_email))

        return {'success': True, 'data': {
            'user': school_admin.to_dict(),
            'program': program.to_dict(),
            'school': school.to_dict() if school else None,
            'cohort': cohort.to_dict(),
            'classroom': classroom.to_dict() if classroom else None,
            'activities': ([a.to_dict() for a in activities]
                           if activities else None),
        }}


class CrossSiteGifHandler(url_handlers.BaseHandler):
    """Provides a way for PERTS javascript on other domains to access api.

    The general format is
    [normal api url]/cross_site.gif?[normal request parameters]

    Example:
    /api/put/pd/cross_site.gif?variable=s1__progress&?value=100&...
    /api/see/user/cross_site.gif?user_type=teacher  # not implemented

    Example as a qualtrics img tag:
    <img src="//www.perts.net/api/put/pd/cross_site.gif?variable=s1__progress&value=25">

    Because this is a publicly-accessible URL, we need to build safety checks
    into each different kind of call. If we wind up using this a lot, we should
    find a more general authentication solution. For now, it just does put/pd,
    nothing else.
    """
    def do_wrapper(self, api_path):
        # Try to handle the request data, or log an error. Normally, inheriting
        # from ApiHandler would take care of this, but this doesn't return JSON
        # so we have to duplicate some code.
        try:
            params = util.get_request_dictionary(self.request)
            logging.info(params)

            if api_path == 'put/pd':
                self.put_pd(params)
            else:
                raise Exception(
                    "This cross-site api has not been implemented: {}."
                    .format('/api/' + api_path))

        except Exception as error:
            trace = traceback.format_exc()
            logging.error("{}\n{}".format(error, trace))

        # No matter what happens, return the gif.
        self.response.headers['Content-Type'] = 'image/gif'
        # A 1x1 transparent pixel in a base64 encoded string. See
        # http://stackoverflow.com/questions/2933251/code-golf-1x1-black-pixel
        gif_data = 'R0lGODlhAQABAAAAACwAAAAAAQABAAACAkwBADs='.decode('base64')
        self.response.out.write(gif_data)

    def put_pd(self, params):
        """Do security checks on potentially malicious pd params, then put."""
        # Be careful b/c this data is coming from an external site.

        # Also strategize about what kind of errors to log/raise. It's very
        # common, for instance, for calls to come in with the right fields but
        # blank data b/c someone is testing qualtrics and we can safely ignore
        # that. But non-blank data that's malformed might signal there's
        # something wrong we need to solve.

        # This specific set of data is expected from opening any page in
        # Qualtrics without having gone through identify first. Do nothing.
        blank_testing_params = {'program': '', 'scope': '', 'variable': '',
                                'value': ''}
        is_preview = (
            params['program'] == '' and params['scope'] == '' and
            params['value'].isdigit() and 'activity_ordinal' not in params)

        if params == blank_testing_params or is_preview:
            logging.info("Interpreted call as Qualtrics testing. Ignoring.")
            return

        # In non-testing calls, Qualtrics should always attempt to send back
        # these parameters. If we don't have them, or if they're blank, then
        # the qualtrics javascript is wrong, and that's bad.
        expected_keys = set(['program', 'scope', 'variable', 'value',
                             'activity_ordinal'])
        keys_are_missing = set(params.keys()) != expected_keys
        values_are_blank = any([v == '' for v in params.values()])
        if keys_are_missing or values_are_blank:
            raise Exception("Parameters missing: {}".format(params))

        # If we have data, we expected it to make sense. Look stuff up and
        # check coherence.
        scope_results = self.internal_api.get_by_ids([params['scope']])
        if len(scope_results) is 0:
            raise Exception("Scope entity not found: {}."
                            .format(params['scope']))
        scope_entity = scope_results[0]

        if not isinstance(scope_entity, User):
            raise Exception(
                "CrossSiteGifHandler can only accept user-scope pds. "
                "Received scope entity: {}.".format(scope_entity))

        user = scope_entity
        if user.user_type == 'public':
            raise Exception("User type public cannot put pd cross site.")

        # Create an api for the validated user, and record the pd.
        api = Api(user)
        pd = api.create('pd', params)

        logging.info("Created pd {}".format(pd.to_dict()))


class DeleteHandler(ApiHandler):
    """Sets entity.deleted = True for given entity AND ALL ITS CHILDREN."""
    def do(self, kind, id):
        success = self.api.delete(kind, id)
        return {'success': success}


class DeleteEverythingHandler(ApiHandler):
    """Delete absolutely everything. Only allowed while in development."""
    def do(self):
        self.api.delete_everything()
        del self.session['user']
        del self.session['impersonated_user']
        return {'success': True}


class DetectProgramsHandler(ApiHandler):
    """Sychronize program subdirectories with program entities."""
    def do(self):
        new_programs = []
        deleted_programs = []
        current_programs = []
        current_abbreviations = []
        user = self.get_current_user()

        if user.user_type != 'god':
            raise core.PermissionDenied()

        # Check what program directories exist
        path = os.path.join(os.getcwd(), 'programs')
        new_abbreviations = util.get_immediate_subdirectories(path)

        # Check what program entities exist
        current_programs = Program.all().filter('deleted =', False).fetch(11)
        if len(current_programs) > 10:
            raise Exception("Too many programs. Limit is 10.")

        # Check them against each other.
        for p in current_programs:
            if p.abbreviation in new_abbreviations:
                current_abbreviations.append(p.abbreviation)
                new_abbreviations.remove(p.abbreviation)
            else:
                p.deleted = True
                deleted_programs.append(p)
        db.put(deleted_programs)

        # Anything remaining in the list is new.
        for a in new_abbreviations:
            program_config = Program.get_app_configuration(a)
            p = Program.create(abbreviation=a, name=program_config.name)
            current_programs.append(p)
            new_programs.append(p)
        db.put(new_programs)

        return {'success': True, 'data': {
            'deleted_programs': [p.to_dict() for p in deleted_programs],
            'new_programs': [p.to_dict() for p in new_programs],
            'current_programs': [p.to_dict() for p in current_programs],
        }}


class ForgotPasswordHandler(ApiHandler):
    """For public users to send themselves reset-password emails."""
    def do(self):
        # ensure this email address belongs to a known user
        email = self.request.get('email').lower()

        # Look up users by auth_id because that's how they log in;
        # there are other kinds of auth type ('google', 'public') that we
        # wouldn't want returned.
        result = self.internal_api.get('user', {'auth_id': 'direct_' + email})

        if len(result) is 1 and result[0].is_test is False:
            # then this email address is valid; proceed with send
            user = result[0]

            # deactivate any existing reset tokens
            self.api.clear_reset_password_tokens(user.id)

            # create a new token for them
            new_token = ResetPasswordToken.create(user=user.id)
            new_token.put()

            # and email them about it
            link = '/reset_password/' + new_token.token()
            mandrill.send(
                to_address=email,
                subject=config.forgot_password_subject,
                body=mandrill.render_markdown(
                    config.forgot_password_body.format(link)),
            )

            logging.info('ForgotPasswordHandler sending an email to: {}'
                         .format(email))

            return {'success': True, 'data': 'sent'}
        else:
            logging.info('ForgotPasswordHandler invalid email: {}'
                         .format(email))
            return {'success': True, 'data': 'not_sent'}


class GenerateTestPdHandler(ApiHandler):
    def do(self):
        num_entities = int(self.request.get('num_entities'))
        for x in range(num_entities):
            user = self.get_current_user()
            rand = ''.join(random.choice(string.digits) for x in range(10))
            kwargs = {
                'program': 'test_program',
                'activity_ordinal': 1,
                'activity': 'test_activity',
                'cohort': 'test_cohort',
                'classroom': 'test_classroom',
                'user': user.id,
                'scope': 'user',
                'variable': rand,
                'value': rand,
            }
            Pd.create(user, **kwargs)
        return {'success': True}


class GetHandler(ApiHandler):
    def do(self, kind):
        params = util.get_request_dictionary(self.request)
        ancestor = None
        # If an ancestor is specified, look it up by id and pass it in.
        if 'ancestor' in params:
            ancestor_kind = core.get_kind(params['ancestor'])
            ancestor_klass = core.kind_to_class(ancestor_kind)
            ancestor = ancestor_klass.get_by_id(params['ancestor'])
            del params['ancestor']
        results = self.api.get(kind, params, ancestor=ancestor)
        return {'success': True, 'data': [e.to_dict() for e in results]}


class GetByIdsHandler(ApiHandler):
    def do(self):
        ids = util.get_request_dictionary(self.request)['ids']
        results = self.api.get_by_ids(ids)
        return {'success': True, 'data': [e.to_dict() for e in results]}


class GetQualtricsLinkHandler(ApiHandler):
    """Pull a unique URL from our collection of QualtricsLink entities."""
    def do(self, program_id, user_type, activity_ordinal):
        # URL args come in as srings, we need this to be an int.
        activity_ordinal = int(activity_ordinal)

        # We need to find the default link for this program.
        # First look up the program.
        program = self.internal_api.get_from_path('program', program_id)
        # Then the module for the relevant session.
        module = Program.get_activity_configuration(
            program.abbreviation, user_type, activity_ordinal)

        default_link = module.get('qualtrics_default_link', None)
        if default_link is None:
            raise Exception('No default link set in config.')

        link = QualtricsLink.get_link(
            program, int(activity_ordinal), default_link)
        return {'success': True, 'data': link}


class IdentifyHandler(ApiHandler):
    """For identifying students who are participating."""
    def do(self):
        # Make sure only public users make this call.
        user = self.get_current_user()
        if user.user_type != 'public':
            # Warn the javascript on the page that
            # there's a problem so it can redirect.
            return {'success': True, 'data': 'logout_required'}

        params = util.get_request_dictionary(self.request)

        # If there's a javascript stand-in for the calendar, there will be an
        # extraneous parameter that's just for display; remove it.
        if 'display_birth_date' in params:
            del params['display_birth_date']

        # The client supplies the classroom id, but we want the entity.
        classroom = Classroom.get_by_id(params['classroom'])
        params['classroom'] = classroom

        # user may not be there, so check separately
        user_id = self.request.get('user')
        if user_id:
            # the user has selected this among partial matches as themselves
            # check the id; if it's valid, log them in
            User.get_by_id(user_id)  # an invalid id will raise errors
            self.session['user'] = user_id
            data = {'exact_match': user_id,
                    'partial_matches': [],
                    'new_user': False}
        else:
            # the user has provided identifying info, attempt to look them up
            # see url_handlers.BaseHandler.identify() for structure of the
            # data returned
            data = self.identify(**params)
        return {'success': True, 'data': data}


class ImportQualtricsLinksHandler(ApiHandler):
    def do(self, program_abbreviation, session_ordinal, filename):
        program = self.internal_api.get(
            'program', {'abbreviation': program_abbreviation})[0]

        links = self.api.import_links(
            program, int(session_ordinal), filename)

        return {
            'success': True,
            'links': links,
        }


class IsLoggedInHandler(ApiHandler):
    """Tells the browser if the user is currently logged in."""
    def do(self):
        return {
            'success': True,
            'data': self.get_current_user().user_type != 'public',
        }


class LoggingHandler(ApiHandler):
    def do(self, severity):
        # Provide a secret back door so compute engine instances can easily
        # register errors with our app.
        secret = 'FrreHPFA0xSp2yutktBx'
        # Otherwise restrict logging to signed-in users.
        user = self.get_current_user()

        if user.user_type != 'public' or self.request.get('_secret') == secret:
            logger = getattr(logging, severity)
            # Make an entry about the user who sent the log.
            logger('/api/log user: {} {} {}'.format(
                user.user_type, user.id, user.login_email))
            # Make entries out of any extra request data sent in.
            for arg in self.request.arguments():
                # ignore the secret parameter
                if arg == '_secret':
                    continue
                # process lists intelligently
                if arg[-2:] == '[]':
                    value = self.request.get_all(arg)
                # basic key-value
                else:
                    value = self.request.get(arg)
                # value might be unicode, so the string into which we
                # interpolate must be unicode.
                logger(u'/api/log {}: {}'.format(arg, value))

            # Allow cross-domain reporting of errors, e.g. from Qualtrics.
            # Chris tried this via app.yaml, but it didn't work, presumably
            # since this isn't a static resource.
            self.response.headers['Access-Control-Allow-Origin'] = '*'
        return {'success': True}


class LoginHandler(ApiHandler):
    """Users are sent to this page if they can't be automatically logged in via
    /api/authenticate. Provides choices for two kinds of authentication:
    google, and username/password."""
    def do(self):
        auth_type = self.request.get('auth_type')
        username = self.request.get('username') or None  # for direct auth
        password = self.request.get('password') or None  # for direct auth

        if auth_type not in config.allowed_auth_types:
            raise Exception("Bad auth_type: {}.".format(auth_type))
        auth_response = self.authenticate(auth_type, username=username,
                                          password=password)
        # interpret the results of authentication
        if isinstance(auth_response, User):
            # simple case, user was returned, send them on their way
            data = 'signed_in'
        elif auth_response is False:
            # all the credentials were present, but they weren't valid
            # does this email exist for some OTHER auth type?
            matches = self.internal_api.get('user', {'login_email': username})
            if len(matches) is 1:
                # The is the user object we think the human user is trying to
                # log in with.
                intended_user = matches[0]
                if auth_type == intended_user.auth_type():
                    # The user is using the right auth type, and their email
                    # checks out; the password is just wrong.
                    data = 'invalid_credentials'
                else:
                    # The user exists, but with a different auth type than what
                    # they're using. Advise them to try something else.
                    data = 'wrong_auth_type ' + intended_user.auth_type()
            else:
                data = 'invalid_credentials'
        elif auth_response is None:
            # some credentials are missing
            if auth_type == 'google':
                raise Exception("No google account found.")
            elif auth_type == 'direct':
                raise Exception("Missing username and password.")
        return {'success': True, 'data': data}


class PreviewReminders(ApiHandler):
    """ see core@reminders for details. """
    def do(self, abbreviation, user_type):
        r = self.api.get('program', {'abbreviation': abbreviation})
        if len(r) is not 1:
            raise Exception("Program {} not found.".format(abbreviation))
        program = r[0]
        data = self.api.preview_reminders(program, user_type)
        return {'success': True, 'data': data}


class ProgramOutlineHandler(ApiHandler):
    def do(self, program_id):
        data = self.api.program_outline(program_id)
        return {'success': True, 'data': data}


class PublicCohortHandler(ApiHandler):
    """White list certain facts about cohorts as accessible to the public.

    This solves the problem of public users (not-yet-signed-in students)
    needing to know if they're signing up via aliases or normally, while not
    allowing potentially sensitive information (e.g. cohort anomaly notes) to
    be exposed.
    """
    def do(self):
        params = util.get_request_dictionary(self.request)

        result = self.internal_api.get('cohort', {'code': params['code']})

        data = []
        for cohort in result:
            safe_cohort_data = {
                'id': cohort.id,
                'name': cohort.name,
                'code': cohort.code,
                'identification_type': cohort.identification_type,
            }
            data.append(safe_cohort_data)

        return {'success': True, 'data': data}


class RecordClientTestHandler(ApiHandler):
    """Record the results of javascript unit tests.

    Logs an error if there are failed tests.
    """
    def do(self):
        params = util.get_request_dictionary(self.request)
        if len(params['failed_tests']) is 0:
            logging.info(params)
        else:
            # There were failed tests, log an error (and generate an email).
            logging.error(params)
        # Don't freak out the user, either way.
        return {'success': True}


class RegisterHandler(ApiHandler):
    """Called for direct auth_type users. Third-party auth_type users (i.e.
    google accounts) are handled in page_handlers.LoginHandler.
    """
    def do(self):
        auth_type = self.request.get('auth_type')
        username = self.request.get('username') or None
        password = self.request.get('password') or None
        program_id = self.request.get('program')
        if not program_id:
            raise Exception("Must have a program id to register.")
        user, user_is_new = self.register(
            program_id, auth_type, username, password)
        if user is False:
            data = 'wrong_auth_type'
        else:
            data = {'user': user.to_dict(), 'user_is_new': user_is_new}
        return {'success': True, 'data': data}


class ResetPasswordHandler(ApiHandler):
    """Uses the tokens in reset password email links to change passwords."""
    def do(self):
        token = self.request.get('token')
        new_password = self.request.get('new_password')

        # Check the token
        user = self.api.check_reset_password_token(token)

        if user is None:
            return {'success': True, 'data': 'invalid_token'}

        # Change the user's password.
        user.hashed_password = util.hash_password(new_password)
        user.put()

        # Clear existing tokens.
        self.api.clear_reset_password_tokens(user.id)

        # Alert the user that their password has been changed.
        mandrill.send(
            to_address=user.login_email,
            subject=config.change_password_subject,
            body=config.change_password_body,
        )

        logging.info('api_handlers.ResetPasswordHandler')
        logging.info('sending an email to: {}'.format(user.login_email))

        return {'success': True, 'data': 'changed'}


class SearchHandler(ApiHandler):
    """See core@indexer for details."""
    def do(self, query):
        start = self.request.get('start')
        end = self.request.get('end')

        if start and end:
            data = self.api.search(query, int(start), int(end))
        else:
            data = self.api.search(query)

        return {'success': True, 'data': data}


class SecretValueHandler(ApiHandler):
    """For securely storing secret values.

    This handler was adapted from the mindsetkit, which uses a much more normal
    HTTP api than Yellowstone does. This has to work around the fact that
    Yellowstone 1) combines GET and POST and 2) doesn't define a DELETE method
    normally.

    To use, always send with the content type header 'x-www-form-urlencoded',
    but compose the body in JSON, except for the DELETE call, which must have
    no body.
    """

    def do(self, id):
        if self.request.method == 'GET':
            self.write_json(self.GET(id))
        elif self.request.method == 'POST':
            self.write_json(self.POST(id))

    def GET(self, id):
        if (not self.api.user.user_type == 'god'):
            raise Exception("Permission denied.")
        exists = SecretValue.get_by_key_name(id) is not None
        return {'key exists': exists,
                'message': "SecretValues can't be read via api urls."}

    def POST(self, id):
        if (not self.api.user.user_type == 'god'):
            raise Exception("Permission denied.")
        value = util.get_request_dictionary(self.request).get('value', None)
        if value is None:
            raise Exception("Must POST with a value.")
        sv = SecretValue.get_or_insert(id)
        sv.value = value
        sv.put()
        return {'success': True, 'data': id}

    def delete(self, id):
        # Since we're not running through the user-related boilerplate in
        # BaseHandler.get(), do just enough of it here to identify the user
        # as a god.
        self.clean_up_users('user')
        self.clean_up_users('impersonated_user')
        user = self.get_current_user()
        if (not user.user_type == 'god'):
            raise Exception("Permission denied.")
        sv = SecretValue.get_by_key_name(id)
        if sv is not None:
            db.delete(sv)
        self.write_json({'success': True, 'data': id})


class SeeHandler(ApiHandler):
    def do(self, kind):
        data = self.api.see(kind, util.get_request_dictionary(self.request))
        return {'success': True, 'data': [e.to_dict() for e in data]}


class SeeByIdsHandler(ApiHandler):
    def do(self):
        ids = util.get_request_dictionary(self.request)['ids']
        results = self.api.see_by_ids(ids)
        return {'success': True, 'data': [e.to_dict() for e in results]}


class SendContactEmailHandler(ApiHandler):
    def post(self):
        body = json.loads(self.request.body)

        if 'organization' in body:
            organization = body['organization']
        else:
            organization = 'N/A'

        message = u"""
Message from {} <{}>:

Organization: {}

Message:

{}

____

-- Sent via Contact Form --
""".format(body['name'], body['email'], organization, body['message'])

        # Send a message to the PERTS staff via @contact.
        mandrill.send(
            to_address='',
            subject='Inquiry from PERTS.net',
            body=mandrill.render_markdown(message),
        )

        logging.info('api_handlers.SendContactEmailHandler')
        logging.info('sending an email to: ')

        return {'success': True, 'data': ''}


class ShowReminders(ApiHandler):
    """ see api@send_reminders for details. """
    def do(self):
        date = self.request.get('date')
        data = self.api.show_reminders(date)
        return {'success': True, 'data': data}


class StratifyHandler(ApiHandler):
    """Assign the user with the provided profile to a group."""
    def do(self):
        group = self.api.stratify(**util.get_request_dictionary(self.request))
        return {'success': True, 'data': group}


class SystematicUpdateHandler(ApiHandler):
    """A way to gradually update a large set of entities in the datastore.

    Fetches sets of entities by their created time, and runs arbitrary code on
    them. Keeps track of its place with a named Timestamp entity.

    Todo:
    - figure out if this is a good place, organizationally, to put this code
    - use andrew's strip_names() function in the update method
    - actually test it with very pessimistic conditions
        - arbitrary timeouts
        - inconsistent reads
    - chat w/ Ben re: interaction of preview and start_time
    """
    def do(self, update_name):
        """The update name defines what kind of update to run. This will be
        used to:
        - Create a timestamp to track progress.
        - Query for entities based on configuration in
          config.systematic_update_settings, which must be defined.
        - Execute method of this class by the same name on each entity returned
          from the query. It must be defined. The method should take an entity
          and return and return either None (if the entity should not be
          updated) or a modified entity.

        Accepts parameters in request string:
        fetch_size (int) - how many entities to process at once
        start_time (str) - what "created" time to start searching for entities;
                           this overrides the normal "systematic" behavior
        preview (bool) - report on results without actually updating
        """
        from google.appengine.ext import db
        from datetime import datetime

        params = util.get_request_dictionary(self.request)

        # Check request string and apply defaults where necessary
        if 'fetch_size' in params:
            fetch_size = params['fetch_size']
        else:
            fetch_size = 100
        if 'start_time' in params:
            start_time = params['start_time']
        else:
            # Look up / create a timestamp to track progress
            ts = Timestamp.get_or_insert(update_name)
            start_time = ts.timestamp
        if 'preview' in params:
            preview = params['preview']
        else:
            preivew = False

        conf = config.systematic_update_settings[update_name]

        # Query for entities
        klass = core.kind_to_class(conf['kind'])
        query = klass.all()
        query.filter('created >', start_time)
        query.order('created')
        entity_list = query.fetch(fetch_size)

        before_snapshot = [e.to_dict() for e in entity_list]

        # Look up related method
        method = getattr(self, update_name)
        if not util.is_function(method):
            raise Exception("Invalid update name: method isn't callable.")

        # Execute the method on each entity
        modified_entities = []
        for entity in entity_list:
            # Check if this systematic update has been performed before
            if update_name in entity.systematic_updates:
                raise Exception(
                    "{} has already been performed on entity {}."
                    .format(update_name, entity.id))
            else:
                entity.systematic_updates.append(update_name)
            updated_entity = method(entity)
            if updated_entity is not None:
                modified_entities.append(updated_entity)

        # The entity variable is still set to the last one of the list;
        # use it to save our spot for next time.
        end_time = entity.created

        after_snapshot = [e.to_dict() for e in modified_entities]

        if not preview:
            db.put(modified_entities)

        if 'start_time' not in params:
            # Save progress
            ts.timestamp = end_time
            ts.put()

        return {'success': True, 'data': {
            'entities_queried': len(entity_list),
            'entities_modified': len(modified_entities),
            'start_time': start_time,
            'end_time': end_time,
            'entities before update': before_snapshot,
            'entities after update': after_snapshot,
        }}

    def lowercase_login(self, user_entity):
        """Method to execute on each user in the datastore.

        Returns None if user doesn't need updating. Otherwise returns modified
        user.
        """
        if user.user_type == 'student':
            # @todo: use andrew's strip_names() function here, when it
            # becomes available
            # user.first_name = strip_names(user.first_name)
            # user.last_name = strip_names(user.last_name)
            pass
        else:
            user.auth_id = user.auth_id.lower()
            user.login_email = user.login_email.lower()

        return user


class UnassociateHandler(ApiHandler):
    """Action is either 'unassociate' or 'disown'."""
    def do(self, action, from_kind, from_id, to_kind, to_id):
        from_klass = core.kind_to_class(from_kind)
        to_klass = core.kind_to_class(to_kind)
        from_entity = from_klass.get_by_id(from_id)
        to_entity = to_klass.get_by_id(to_id)
        logging.info("handler action {}".format(action))
        from_entity = self.api.unassociate(action, from_entity, to_entity)
        return {'success': True, 'data': from_entity.to_dict()}


class UpdateHandler(ApiHandler):
    """Data updates work like updating a dictionary, entities keys are assigned
    new values.

    PERTS supports two types of data updates:
    * One entity, the normal case.
    * An entity and all of its children recursively, the rare case. This was
      developed to allow us to switch teachers to a different cohort if they
      accidentally joined the wrong one to begin with. see: #185. This type
      has special arguments:
      - recurse_children (bool): initiates recusive update
      - preview (bool): don't update, just show WOULD be changed.
    """
    def do(self, kind, id=None):
        params = util.get_request_dictionary(self.request)
        if 'recurse_children' in params and params['recurse_children'] is True:
            # This flag just serves to forks the update request to
            # recursive_update(); toss it b/c it's not data, really.
            del params['recurse_children']

            # This flag causes recursive_update() to do nothing except return
            # the entity ids it WOULD change.
            if 'preview' in params:
                preview = params['preview'] is True
                del params['preview']
            else:
                preview = False

            entities_changed = self.api.recursive_update(
                kind, id, params, preview=preview)
            data = [e.to_dict() for e in entities_changed]
        else:
            entity = self.api.update(kind, id, params)
            data = entity.to_dict()
        return {'success': True, 'data': data}


class UpdateByIdHandler(ApiHandler):
    def do(self, id):
        kind = core.get_kind(id)
        params = util.get_request_dictionary(self.request)
        entity = self.api.update(kind, id, params)
        return {'success': True, 'data': entity.to_dict()}


webapp2_config = {
    'webapp2_extras.sessions': {
        # cam. I think this is related to cookie security. See
        # http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html
        'secret_key': '8YcOZYHVrVCYIx972K3MGhe9RKlR7DOiPX2K8bB8',
    },
}


app = webapp2.WSGIApplication([
    ('/api/(.*)/cross_site.gif', CrossSiteGifHandler),
    ('/api/(archive|unarchive)/(.*)', ArchiveHandler),
    ('/api/(associate|set_owner)/(.*?)/(.*?)/(.*?)/(.*)', AssociateHandler),
    ('/api/(unassociate|disown)/(.*?)/(.*?)/(.*?)/(.*)', UnassociateHandler),
    ('/api/batch_put_pd', BatchPutPdHandler),
    ('/api/batch_put_user', BatchPutUserHandler),
    ('/api/change_password/?', ChangePasswordHandler),
    ('/api/check_client_test/?', CheckClientTestHandler),
    ('/api/create_public_school/?', CreatePublicSchoolHandler),
    ('/api/delete/(.*?)/(.*)', DeleteHandler),
    ('/api/delete_everything', DeleteEverythingHandler),
    ('/api/detect_programs', DetectProgramsHandler),
    ('/api/forgot_password/?', ForgotPasswordHandler),
    ('/api/generate_test_pd/?', GenerateTestPdHandler),
    ('/api/get/(.*)', GetHandler),
    ('/api/get_by_ids/?', GetByIdsHandler),
    ('/api/get_qualtrics_link/(.*?)/(.*?)/(.*)', GetQualtricsLinkHandler),
    ('/api/identify/?', IdentifyHandler),
    ('/api/import_qualtrics_links/(.*?)/(.*?)/(.*)', ImportQualtricsLinksHandler),
    ('/api/is_logged_in/?', IsLoggedInHandler),
    ('/api/log/(.*)', LoggingHandler),
    ('/api/login/?', LoginHandler),
    ('/api/preview_reminders/([^\/]*)/([^\/]*)/?', PreviewReminders),
    ('/api/program_outline/(.*)', ProgramOutlineHandler),
    ('/api/public_cohort_details', PublicCohortHandler),
    ('/api/put/(.*?)/(.*)', UpdateHandler),
    ('/api/put/([^/]*)/?', CreateHandler),
    ('/api/put_by_id/(.*)', UpdateByIdHandler),
    ('/api/record_client_test/?', RecordClientTestHandler),
    ('/api/register/?', RegisterHandler),
    ('/api/reset_password/?', ResetPasswordHandler),
    ('/api/search/(.*)/?', SearchHandler),
    webapp2.Route(r'/api/secret_values/<id>', handler=SecretValueHandler),
    ('/api/see/(.*)', SeeHandler),
    ('/api/see_by_ids/?', SeeByIdsHandler),
    ('/api/send_contact_email/?', SendContactEmailHandler),
    ('/api/show_reminders/?', ShowReminders),
    ('/api/stratify/?', StratifyHandler),
    # disabled until the systematic updater is ready
    # ('/api/systematic_update/(.*)', SystematicUpdateHandler),
], config=webapp2_config, debug=debug)
