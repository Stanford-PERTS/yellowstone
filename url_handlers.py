"""Defines BaseHandler, ancestor of all request handlers.

See page_, api_, and cron_handlers.py.

Handles user authentication, identification, and registration. Also sets up
user sessions.
"""

from google.appengine.api import users as app_engine_users
# for password hashing
# why this library? http://stackoverflow.com/questions/7027196/how-can-i-use-bcrypt-scrypt-on-appengine-for-python
# comparison of alogorithms: http://pythonhosted.org/passlib/new_app_quickstart.html#detailed-comparison-of-choices
from passlib.hash import sha256_crypt
from webapp2_extras import sessions
import hashlib
import json
import webapp2

from api import Api
from connection import DatastoreConnection
from core import PermissionDenied, CredentialsMissing, SecretValue
from id_model import Program, User
import config
import logging
import mandrill
import util


class BaseHandler(webapp2.RequestHandler):
    """Ancestor of all web handlers. Handles sessions and third-party
    authentication."""

    # It is critical to reset these on each request *within a function*, and
    # not just in the class definition. Not all of a given python file is run
    # with every page request. See
    # https://developers.google.com/appengine/docs/python/#imports_are_cached
    # get_current_user() does this work for us
    _user = None
    _impersonated_user = None

    def get(self, *args, **kwargs):
        """Handles ALL requests. Figures out the user and then delegates to
        more purpose-specific methods."""
        # Some poorly-behaved libraries screw with the default logging level,
        # killing our 'info' and 'warning' logs. Make sure it's set correctly
        # for our code.
        util.allow_all_logging()

        # Mark the start time of the request. You can add events to this
        # profiler in any request handler like this:
        # util.profiler.add_event("this is my event")
        util.profiler.clear()
        util.profiler.add_event('START')

        # create and sign in as a god user under certain conditions
        self.immaculately_conceive()
        # Running this ensures that cached users (e.g. self._user) are
        # correctly synched with the session ids.
        self.clean_up_users('user')
        self.clean_up_users('impersonated_user')
        # Deal with impersonation options
        if self.request.get('escape_impersonation') in config.true_strings:
            # Allow calls to escape impersonation, i.e. treat the call as if
            # the true user (not the impersonated user) was making it.
            # Should have no effect when no impersonation is happening.
            self._impersonated_user = None
            self.api = Api(self.get_current_user(method='normal'))
        elif self.request.get('impersonate'):
            # If allowed, impersonate the provided user for just this call
            target_user = User.get_by_id(self.request.get('impersonate'))
            normal_user = self.get_current_user(method='normal')
            if normal_user.can_impersonate(target_user):
                self._impersonated_user = target_user
                self.api = Api(target_user)
            else:
                logging.info('Impersonation denied. '
                             '{} is not allowed to impersonate {}.'
                             .format(normal_user.id, target_user.id))
        if not hasattr(self, 'api'):
            # Instantiate an api class that knows about the current user and
            # their permissions. Will default to the permissions of the
            # impersonated user if there is one, or the public user if no one
            # is signed in.
            self.api = Api(self.get_current_user())
        # Also create an internal API that has god-like powers, only to be used
        # by interal platform code, never exposed through URLs.
        self.internal_api = Api(User.create(user_type='god'))
        # We are in the "grandparent" function; do_wrapper() is the "parent",
        # defined in either ApiHandler or ViewHandler; in turn, the "child"
        # function do() will be called.
        self.do_wrapper(*args, **kwargs)

    def post(self, *args, **kwargs):
        """Looks for JSON in the request body; forwards to GET."""
        # Angularjs likes to send content types like text/plain and
        # application/json. Neither will work; webob hard-codes form-based
        # content types, see
        # https://github.com/Pylons/webob/blob/master/webob/request.py#L781
        correct_header = 'application/x-www-form-urlencoded'
        content_type_valid = True
        try:
            content_type = self.request.headers['Content-Type']
        except:
            content_type_valid = False
        else:
            if correct_header not in content_type:
                content_type_valid = False
        if not content_type_valid:
            raise Exception('POSTs must have the header "Content-Type: '
                            'application/x-www-form-urlencoded". Got {}'
                            .format(content_type))

        # Process JSON data.
        try:  # Client may not send valid JSON.
            # "Manually" interpret the request payload; webob doesn't know how.
            json_payload = json.loads(self.request.body)
        except ValueError:
            # This might be a more traditional foo=bar&baz=quz type payload,
            # so leave it alone; webob can interpret it correctly without help.
            pass
        else:
            if type(json_payload) is not dict:
                raise Exception(
                    'POST data must be JSON objects (i.e. dictionaries).')
            # The request object doesn't know how to interpret the JSON in the
            # request body, and so self.request.POST will be full of junk.
            # Luckily, it interprets the POST variables lazily, so we can avoid
            # the junk by clearing the body now.
            self.request.body = ''
            # Now force-feed the POST variables which we have manually
            # interpreted into the request so that future code can just call
            # self.request.get().
            for k, v in json_payload.items():
                self.request.POST[k] = v

        # And finally, now that everything has been massaged, we can continue
        # on to the GET handler.
        self.get(*args, **kwargs)

    def naked_domain_redirect(self):
        """Redirect naked domain URLs to www, production only.

        We use DNS to redirect http://perts.net to http://www.perts.net, but
        I haven't found a way to make https://perts.net do the same thing. This
        checks for a naked production domain and redirects to www, which will
        work even for https.
        """
        if self.request.host == 'perts.net':
            url = 'https://www.perts.net{}'.format(self.request.path_qs)
            self.redirect(url, permanent=True)
            return True
        else:
            return False

    def authenticate(self, auth_type=None, username=None, password=None):
        """Takes various kinds of credentials (username/password, google
        account) and logs you in as a PERTS user.

        Will return one of these three:
        User object:    the user has been successfully authenticated
        False:          credentials invalid, either because a password is wrong
                        or no account exists for those credentials
        None:           looked for credentials but didn't find any of the
                        appropriate kind
        """
        if auth_type is None:
            # determine auth_type if it wasn't provided
            if username is not None and password is not None:
                auth_type = 'direct'
            elif app_engine_users.get_current_user():
                auth_type = 'google'
            else:
                # Auth_type might still be None, which simply means that
                # someone has arrived at login but we don't have any data on
                # them yet. Don't bother with the rest of the function.
                return None

        # fetch matching users
        if auth_type == 'direct':
            if username is None or password is None:
                # no credentials present
                return None

            auth_id = 'direct_' + username.lower()
            user_query_lowercase = User.all().filter('deleted =', False)
            user_query_lowercase.filter('is_test =', False)
            user_query_lowercase.filter('auth_id =', auth_id)
            user_results = user_query_lowercase.fetch(2)

        elif auth_type in ['google']:
            try:
                user_kwargs = self.get_third_party_auth(auth_type)
            except CredentialsMissing:
                return None
            auth_id = user_kwargs['auth_id']
            user_query = User.all().filter('deleted =', False)
            user_query.filter('auth_id =', auth_id)
            # Fetch 2 b/c that's sufficient to detect multiple matching users.
            user_results = user_query.fetch(2)

        # interpret the results of the query
        num_matches = len(user_results)
        if num_matches is 0:
            # no users with that username, invalid log in
            return False
        elif num_matches > 1:
            logging.error("More than one user matches auth info: {}"
                          .format(auth_id))
            # Sort the users by modified time, so we take the most recently
            # modified one.
            user_results = sorted(
                user_results, key=lambda u: u.modified, reverse=True)
        # else num_matches is 1, the default case, and we can assume there was
        # one matching user
        user = user_results[0]

        # For direct authentication, PERTS is in charge of
        # checking their credentials, so validate the password.
        if auth_type == 'direct':
            # A user-specific salt AND how many "log rounds" (go read about key
            # stretching) should be used is stored IN the user's hashed
            # password; that's why it's an argument here.
            # http://pythonhosted.org/passlib/
            if not sha256_crypt.verify(password, user.hashed_password):
                # invalid password for this username
                return False

        # We've decided our response; if the user has successfully
        # authenticated, then log them in to the session.
        if isinstance(user, User):
            # all's well, log them in and return the matching user
            self.session['user'] = user.id
        return user

    def clean_up_users(self, session_key):
        """Brings the three representations of users into alignment: the entity
        in the datastore, the id in the session, and the cached object saved as
        a property of the request handler."""
        id = self.session.get(session_key)
        attr = '_' + session_key
        cached_user = getattr(self, attr)
        if not id:
            # clear the cached user b/c the session is empty
            setattr(self, attr, None)
        elif not cached_user or id != cached_user.id:
            # the cached user is invalid, try to restore from the session...
            datastore_user = User.get_by_id(id)
            if datastore_user:
                # found the user defined by the session; cache them
                setattr(self, attr, datastore_user)
            else:
                # could NOT find the user; clear everything
                del self.session[session_key]
                setattr(self, attr, None)
        # Make sure the session keys always exist, even if they are empty.
        if session_key not in self.session:
            self.session[session_key] = None

    def datastore_connected(self):
        """Test if we can reach the datastore."""
        c = DatastoreConnection.get_by_key_name('connection')
        if c:
            logging.info("Confirmed datastore connection: {}.".format(c))
            return True
        elif app_engine_users.is_current_user_admin():
            DatastoreConnection.initialize_connection()
            return True
        else:
            logging.warning("No datastore connection: {}.".format(c))
            self.response.headers['Content-Type'] = 'application/json; ' \
                                                    'charset=utf-8'

            self.response.write(json.dumps({
                'success': False,
                'message': "Intermittent error. Please try again.",
                'dev_message': (
                    "This error occurs when pegasus cannot find a "
                    "particular entity, the unique DatastoreConnection "
                    "entity. It occurs intermittently under normal "
                    "operations for unknown reasons. However, it may occur if "
                    "no one has yet created the entity in question in the "
                    "first place. If you think this may be the case, visit "
                    "/initialize_connection as an app admin."),
            }))
            return False

    def dispatch(self):
        """Initialize and manage sessions."""
        if self.naked_domain_redirect():
            return
        # Get a session store for this request.
        self.session_store = sessions.get_store(request=self.request)
        try:
            # Dispatch the request.
            webapp2.RequestHandler.dispatch(self)
        finally:
            # Save all sessions.
            self.session_store.save_sessions(self.response)

    def get_current_user(self, method=None):
        """Get the currently logged in PERTS user with the following priority:
            1. Impersonated user
            2. Normal user
            3. Public user
        The method argument can override this behavior. If overriding and the
        requested type of user is not present, will return the public user.
        """
        public_user = User(user_type='public')

        # Check that the session matches the cached user entites.
        self.clean_up_users('user')
        self.clean_up_users('impersonated_user')

        # return what was asked
        if method == 'normal':
            return self._user or public_user
        elif method == 'impersonated':
            return self._impersonated_user or public_user
        else:
            return self._impersonated_user or self._user or public_user

    def get_third_party_auth(self, auth_type):
        """Wrangle and return authentication data from third parties.

        Args:
            auth_type: str, only accepts 'google'
        Returns:
            dictionary of user information, which will always contain
                the key 'auth_id'.
        """
        if auth_type == 'google':
            gae_user = app_engine_users.get_current_user()
            if not gae_user:
                raise CredentialsMissing("No google login found.")
            user_kwargs = {
                'auth_id': 'google_' + gae_user.user_id(),
                'login_email': gae_user.email(),
                # 'name': gae_user.nickname(),
            }
        else:
            raise Exception("Invalid auth_type: {}.".format(auth_type))
        return user_kwargs

    def identify(self, classroom, first_name, last_name, middle_initial='',
                 force_create=False):
        """Takes a student's identifying information and attempts to match
        them with other known students.

        If none can be found, a new student user is created. If only last name
        and birth date match existing users, partial matches are sent back for
        verification. Identified students are logged in. If an existing student
        logs in with a classroom id that is new for them, it is simply added to
        their list of associated classrooms.

        The force_create parameter is used for user's response to the partial
        match result. If they declare none of those partial matches to be
        themselves, we force the creation of a new user.

        23 April 2014 - ajb
        Changing the identify process to *only* create a new user when
        the force_create variable is specified to be true. Instead of
        creating a new user when no other users are found, set the
        response['new_user'] to true a

        """
        logging.info(
            u'BaseHandler.identify(classroom={}, first_name={}, last_name={}, '
            'middle_initial={}, force_create={})'
            .format(classroom, first_name, last_name, middle_initial,
                    force_create)
        )

        response = {'exact_match': '',
                    'partial_matches': [],
                    'new_user': False}

        # Flow varies based on the identification type of this cohort.
        cohort = self.internal_api.get_from_path(
            'cohort', classroom.assc_cohort_list[0])
        logging.info("Following rules for identification type {}."
                     .format(cohort.identification_type))

        # When using aliases, the alias must exactly match one of our hard-
        # coded values.
        if cohort.identification_type == 'alias':
            logging.info("{} uses alias identification.".format(cohort.id))
            alias = (util.clean_string(first_name),
                     util.clean_string(last_name))
            if alias not in config.allowed_student_aliases:
                logging.info("Invalid alias: {}.".format(alias))
                return response
        # In dissemination mode, hash first and last name so we never store
        # identifiable data.
        elif cohort.identification_type == 'dissemination':
            logging.info("{} uses dissemination identification. Hashing names."
                         .format(cohort.id))

            salt_secret = SecretValue.get_by_key_name('dissemination_salt')
            if salt_secret is None:
                raise Exception(
                    "No salt set. To set one, POST to /api/secret_values/"
                    "dissemination_salt with body "
                    "'{\"value\": \"??? salt goes here ???\"}.")

            def hash_name(name):
                name += salt_secret.value
                return hashlib.sha1(name.encode('utf-8')).hexdigest()

            first_name = hash_name(first_name)
            last_name = hash_name(last_name)

        if force_create:
            # Check for the student one more time, since we've given them the
            # opportunity to double-check and edit their name.
            exact_matches = self._identify_exact_matches(
                classroom.id, first_name, last_name, middle_initial)
            if len(exact_matches) is 1:
                user = exact_matches[0]
            else:
                user = self._create_student(classroom, first_name, last_name,
                                            middle_initial)
            response['exact_match'] = user.id
            self._log_in_student(classroom, user)
            return response

        exact_matches = self._identify_exact_matches(
            classroom.id, first_name, last_name, middle_initial)

        num_exact = len(exact_matches)
        if num_exact > 1:
            # This is a problem; we have multiple identical users.
            # Return the newest version of this user, b/c it's likely that
            # one which will be in their session and have the most up-to-
            # date data.
            newest_to_oldest = sorted(
                exact_matches, key=lambda e: e.created, reverse=True)
            user = newest_to_oldest[0]
            logging.error(u'Multiple identical students: {} {} {}.'.format(
                user.stripped_first_name, user.middle_initial,
                user.stripped_last_name))
            # Still allow the user to sign in, however:
            response['exact_match'] = user.id
        elif num_exact is 1:
            # Great, a unique match.
            user = exact_matches[0]
            logging.info('Exact match found: {}'.format(user.id))
            response['exact_match'] = user.id
        else:

            logging.info('No exact matches found.')

            if cohort.identification_type == 'alias':
                # When using aliases, we don't bother with partial matches or
                # double checking names. Just create the user (we've already
                # checked that the alias is valid).
                return self.identify(classroom, first_name, last_name,
                                     middle_initial, force_create=True)

            elif cohort.identification_type == 'dissemination':
                # In this mode, we don't collect enough information to do a
                # partial match, so we also jump straight to the double-check.
                logging.info("No matches found. Starting new user double "
                             "check process.")
                response['new_user'] = True

            elif cohort.identification_type == 'default':
                # We'll have to loosen our requirements.
                partial_matches = self._identify_partial_matches(
                    classroom.id, last_name)

                num_partial = len(partial_matches)
                if num_partial > 0:
                    # Only partial matches exist; we'll have to ask the user
                    # about them. Include some details on those matches so the
                    # user can pick between them intelligently.
                    logging.info('Partial matches found: {}'.format(
                        [u.id for u in partial_matches]))
                    response['partial_matches'] = []
                    for u in partial_matches:
                        response['partial_matches'].append({
                            'id': u.id,
                            'first_name': u.first_name,
                            'last_name': u.last_name,
                            'middle_initial': u.middle_initial,
                        })
                else:  # i.e., if num_partial == 0:
                    # No matching users found at all! Create one.
                    logging.info("No matches found. Starting new user double "
                                 "check process.")
                    response['new_user'] = True

        if response['exact_match'] != '':
            # Then we can expect a user has been found. Log them in.
            self._log_in_student(classroom, user)

        return response

    def immaculately_conceive(self):
        """Create and sign in to PERTS as a god user if no other user is signed
        in and you are logged in to google as an app admin."""
        user_id = self.session.get('user')
        if not user_id and app_engine_users.is_current_user_admin():
            google_user = app_engine_users.get_current_user()
            god = User.all().filter('login_email =', google_user.email()).get()
            if not god:
                god = User.create(user_type='god', name=google_user.nickname(),
                                  login_email=google_user.email(),
                                  auth_id='google_' + google_user.user_id())
                god.put()
            self.session['user'] = god.id

    def impersonate(self, target):
        """Set a special user id in the session so get_current_user() returns
        that user. Makes the website look like the impersonate user would see
        it, while the original user remains logged in. Raises
        PermissionDenied."""
        normal_user = self.get_current_user(method='normal')
        if normal_user.can_impersonate(target):
            # set the impersonated user
            self.session['impersonated_user'] = target.id
        else:
            raise PermissionDenied(
                "Not allowed to impersonate {}".format(target.id))

    def register(self, program_id, auth_type, username=None, password=None, cohort_id=None):
        """Logs in users and registers them if they're new.

        Raises exceptions when the system appears to be broken (e.g. redundant
        users).

        Returns tuple(
            user - mixed, False when given non-sensical data by users (e.g.
                registering an existing email under a new auth type) or
                matching user entity,
            user_is_new - bool, True if user was newly registered
        )

        """
        user_is_new = False

        if auth_type not in config.allowed_auth_types:
            raise Exception("Bad auth_type: {}.".format(auth_type))
        if auth_type == 'direct':
            if None in [username, password]:
                raise Exception("Credentials incomplete.")
            creation_kwargs = {
                'login_email': username,
                'auth_id': 'direct_' + username,
                'plaintext_password': password,  # it WILL be hashed later
            }

        # These are the third party identity providers we currently know
        # how to handle. See util_handlers.BaseHandler.get_third_party_auth().
        elif auth_type in ['google']:
            # may raise CredentialsMissing
            creation_kwargs = self.get_third_party_auth(auth_type)

        # Check that the user hasn't already registered in two ways.

        # 1) If the email matches but the auth type is different, we reject
        #    the request to register so the UI can warn the user.
        email_match_params = {'login_email': creation_kwargs['login_email']}
        email_matches = self.internal_api.get('user', email_match_params)
        for user in email_matches:
            if user.auth_type() != auth_type:
                user = False
                return (user, user_is_new)

        # 2) If the auth_id matches, they tried to register when they should
        #    have logged in. Just log them in.
        auth_match_params = {'auth_id': creation_kwargs['auth_id']}
        auth_matches = self.internal_api.get('user', auth_match_params)
        if len(auth_matches) == 1:
            # they already have an account
            user = auth_matches[0]

        # This user hasn't already registered. Register them.
        elif len(auth_matches) == 0:
            user_is_new = True

            # Having collected the user's information, build a user object.
            creation_kwargs['user_type'] = 'teacher'
            # Include the program id as an initial relationship (see
            # config.optional_associations).
            creation_kwargs['program'] = program_id
            user = self.api.create('user', creation_kwargs)

            # Refresh the api with the user's new privileges.
            self.api = Api(user)
            # Send them an email to confirm that they have registered.
            # The email text is hard coded in the program app.
            program = self.api.get_from_path('program', program_id)
            program_conf = Program.get_app_configuration(program.abbreviation)
            mandrill.send(
                to_address=creation_kwargs['login_email'],
                subject=program_conf.registration_email_subject,
                body=mandrill.render_markdown(
                    program_conf.registration_email_body),
                template_data={'email': creation_kwargs['login_email'],
                               'cohort_id': cohort_id}
            )

            logging.info('url_handlers.BaseHandler.register()')
            logging.info('sending an email to: {}'
                         .format(creation_kwargs['login_email']))

        # There's a big problem.
        else:
            logging.error("Two matching users! {}".format(auth_match_params))
            # Sort the users by modified time, so we take the most recently
            # modified one.
            auth_matches = sorted(
                auth_matches, key=lambda u: u.modified, reverse=True)
            user = auth_matches[0]

        # Sign in the user.
        self.session['user'] = user.id

        return (user, user_is_new)

    def stop_impersonating(self):
        self.session['impersonated_user'] = None

    def _base_identify_query(self, classroom_id):
        """The various ways we look for students have these similarities."""
        query = User.all().filter('deleted =', False)
        query.filter('is_test =', False)
        query.filter('user_type =', 'student')
        query.filter('assc_classroom_list =', classroom_id)
        return query

    def _create_student(self, classroom, first_name, last_name,
                        middle_initial):

        new_student = self.api.create('user', {
            'first_name': first_name,
            'last_name': last_name,
            'middle_initial': middle_initial,
            'user_type': 'student',
            'classroom': classroom.id,
            'certified': True,
        })

        return new_student

    def _identify_exact_matches(self, classroom_id, first_name,
                                last_name, middle_initial):
        """Search for exact matches to identify students.

        "Exact" means match on first name, last name, birthday, and school.
        """
        stripped_first_name = util.clean_string(first_name)
        stripped_last_name = util.clean_string(last_name)
        if middle_initial is not None:
            middle_initial = util.clean_string(middle_initial).upper()

        # <issue #208>
        #   <remove later>
        # For the time being, it also means either regular or stripped versions
        # of names. In the future, we will only process stripped names.
        normal_q = self._base_identify_query(classroom_id)
        normal_q.filter('first_name =', first_name)
        normal_q.filter('last_name =', last_name)
        normal_q.filter('middle_initial =', middle_initial)
        #   </remove later>
        # </issue #208>

        # Query based on stripped names because we expect students to type
        # their name differently from session to session. Stripping attempts
        # to make their name uniform and still unique. See util.clean_string().
        stripped_q = self._base_identify_query(classroom_id)
        stripped_q.filter('stripped_first_name =', stripped_first_name)
        stripped_q.filter('stripped_last_name =', stripped_last_name)
        stripped_q.filter('middle_initial =', middle_initial)

        # <issue #208>
        #   <remove later>
        combined_results = normal_q.fetch(5) + stripped_q.fetch(5)
        unique_results = list(set(combined_results))
        return unique_results
        #   </remove later>
        #   <replace with>
        # return stripped_q.fetch(5)
        #   </replace with>
        # </issue #208>

    def _identify_partial_matches(self, classroom_id, last_name):
        """Search for partial matches to identify students.

        "Partial" means we don't use first name.
        """
        stripped_last_name = util.clean_string(last_name)

        # <issue #208>
        #   <remove later>
        # For the time being, it also means either regular or stripped versions
        # of names. In the future, we will only process stripped names.
        normal_q = self._base_identify_query(classroom_id)
        normal_q.filter('last_name =', last_name)
        #   </remove later>
        # </issue #208>

        # Query based on stripped names because we expect students to type
        # their name differently from session to session. Stripping attempts
        # to make their name uniform and still unique. See util.clean_string().
        stripped_q = self._base_identify_query(classroom_id)
        stripped_q.filter('stripped_last_name =', stripped_last_name)

        # <issue #208>
        #   <remove later>
        combined_results = normal_q.fetch(5) + stripped_q.fetch(5)
        unique_results = list(set(combined_results))
        return unique_results
        #   </remove later>
        #   <replace with>
        # return stripped_q.fetch(5)
        #   </replace with>
        # </issue #208>

    def _log_in_student(self, classroom, user):
        """Students always log in in the context of a classroom."""
        # Nota bene: if this is a newly created user, they will still
        # have registration_complete as false, and so we can intelligently
        # redirect them to a page handling consent, race, gender, etc.
        self.session['user'] = user.id
        # If this user isn't already associated with this
        # classroom, do it now
        # todo: remove other existing classrooms associations?
        if classroom.id not in user.assc_classroom_list:
            user = self.api.associate('associate', user, classroom)

    @webapp2.cached_property
    def session(self):
        """Allows set/get of session data within handler methods.
        To set a value: self.session['foo'] = 'bar'
        To get a value: foo = self.session.get('foo')"""
        # Returns a session based on a cookie. Other options are 'datastore'
        # and 'memcache', which may be useful if we continue to have bugs
        # related to dropped sessions. Setting the name is critical, because it
        # allows use to delete the cookie during logout.
        # http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html
        return self.session_store.get_session(name='perts_login',
                                              backend='securecookie')