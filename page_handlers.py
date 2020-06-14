"""Serve html documents to users."""

from google.appengine.api import users as app_engine_users
from webapp2_extras.routes import DomainRoute
import datetime
import jinja2  # templating engine
import json
import logging
import markdown
import os
import time
import urllib
import webapp2

from core import PermissionDenied
from id_model import Classroom, Cohort, Program, IdError
from named_model import ShortLink
import config
import programs
import url_handlers
import util

debug = util.is_development()

# These pages are served without any awareness of user session or the
# datastore. They do NOT check for a datastore connection before running.
# They all use the HomePageHandler.
# These strings are included as parts of a regex for URL matching, so some
# globbing is supported.
public_home_pages = [
    '404',
    'about',
    'blog',
    'careers',
    'challenge',
    'contact',
    'copilot/faq',
    'copilot/stories-.*',
    # DON'T make all /engage subpages public, i.e. do not add '/engage.*' to
    # this list. It will break all short links that match, like guides
    # and documents.
    'engage',
    'engage/faq',
    'engage/teacher',
    'engage/administrator',
    'engage/stories-.*',
    'enrolling_colleges',
    'our-work',
    'participation',
    'PERTS',
    'press_kit',
    # 'programs',  # b/c it requires complex behavior, this has its own handler
    'resources',
    'research',
    'results',
    'security'
    'team',
    'terms',
    'network-test',
    'orientation/.*',
]


class ViewHandler(url_handlers.BaseHandler):
    """Superclass for page-generating handlers."""

    def dispatch(self):
        if self.datastore_connected():
            # Call the overridden dispatch(), which has the effect of running
            # the get() or post() etc. of the inheriting class.
            url_handlers.BaseHandler.dispatch(self)
        else:
            # Sometimes the datastore doesn't respond. I really don't know why.
            # Wait a bit and try again.
            attempts = int(self.request.get('connection_attempts', 0)) + 1
            if attempts <= 10:
                time.sleep(1)
                self.redirect(util.set_query_parameters(
                    self.request.url, connection_attempts=attempts))
            else:
                logging.error('Could not connect to datastore after 10 tries.')
                # Since this is a view, it's important to not display weird
                # devvy text to the user. The least harmful thing I can come
                # up with is showing them perts.net.
                jinja_environment = jinja2.Environment(
                    autoescape=True,
                    loader=jinja2.FileSystemLoader('templates'),
                )
                self.response.write(
                    jinja_environment.get_template('index.html').render())

    def do_wrapper(self, *args, **kwargs):
        try:
            output = self.do(*args, **kwargs)
        except Exception as error:
            logging.error("{}".format(error))
            if debug:
                import traceback
                self.response.write('<pre>{}</pre>'.format(
                    traceback.format_exc()))
            else:
                self.response.write("We are having technical difficulties.")
            return
        if output is not None:
            # do methods might not put out rendering info
            # todo: they really should always do that. make sure they do then
            # remove this check
            template_name = output[0]
            params = output[1]
            if len(output) >= 3:
                template_directory = output[2]
            else:
                template_directory = 'templates'
            jinja_environment = jinja2.Environment(
                autoescape=True,
                loader=jinja2.FileSystemLoader(template_directory),
                # # These change jinja's template syntax
                # variable_start_string='[[',
                # variable_end_string=']]',
                # block_start_string='[%',
                # block_end_string='%]'
            )
            # Jinja environment filters:
            jinja_environment.filters['tojson'] = json.dumps
            # default parameters that all views get
            user = self.get_current_user()
            normal_user = self.get_current_user(method='normal')
            params['user'] = user
            params['normal_user'] = normal_user
            params['config'] = config
            params['currently_impersonating'] = user != normal_user
            params['connected_to_google'] = app_engine_users.get_current_user()
            params['google_user'] = app_engine_users.get_current_user()
            params['google_admin'] = app_engine_users.is_current_user_admin()
            params['current_url'] = self.request.path + '?' + self.request.query_string
            params['request'] = util.get_request_dictionary(self.request)
            if debug:
                params['session'] = json.dumps(self.session)

            # Try to load the requested template. If it doesn't exist, replace
            # it with a 404.
            try:
                template = jinja_environment.get_template(template_name)
            except:
                self.error(404)
                jinja_environment = jinja2.Environment(
                    loader=jinja2.FileSystemLoader('templates'))
                template = jinja_environment.get_template('404.html')

            # Render the template with data and write it to the HTTP response.
            self.response.write(template.render(params))

    def http_not_found(self):
        """Return a 404.

        Example use:
        ```
        class FooHandler(ViewHandler):
            def do(self):
                return self.http_not_found()
        ```
        """
        # Trigger the actual HTTP 404 code
        self.error(404)
        # Describe a template to display, so we don't get the ugly browser
        # default.
        return '404.html', {}

    def access_restricted(self, disallowed_types):
        user = self.get_current_user()
        should_redirect = False
        if user.user_type == 'public':
            # empty string here means: encode forward slashes
            encoded_url = urllib.quote(self.request.url, '')
            self.redirect('/yellowstone_login?redirect=' + encoded_url)
            should_redirect = True
        elif user.user_type in disallowed_types:
            self.redirect('/404')
            should_redirect = True
        return should_redirect


class BlogSubdomainRedirectHandler(webapp2.RequestHandler):
    """Redirects the subdomain blog.perts.net to www.perts.net/blog

    https://webapp-improved.appspot.com/guide/routing.html#domain-and-subdomain-routing
    """
    def get(self):
        self.redirect('https://www.perts.net/blog', code=301)


class AccountHandler(ViewHandler):
    def do(self):
        return "account.html", {}


class DashboardHandler(ViewHandler):
    """Shows many different views of data related to the user."""
    def do(self):
        if self.access_restricted(['student', 'public']):
            return

        program_info = {}

        programs = self.api.see('program', {'see': 'abbreviation'})
        for p in programs:
            s_config = Program.get_app_configuration(p.abbreviation, 'student')
            t_config = Program.get_app_configuration(p.abbreviation, 'teacher')
            program_config = Program.get_app_configuration(p.abbreviation)
            program_info[p.id] = {
                'student_outline': s_config['outline'] if s_config else None,
                'teacher_outline': t_config['outline'] if t_config else None,
                'normal_school_instructions': markdown.markdown(getattr(
                    program_config, 'normal_school_instructions', '')),
                'alias_school_instructions': markdown.markdown(getattr(
                    program_config, 'alias_school_instructions', '')),
            }

        return 'dashboard.html', {
            'program_info': program_info,
            'cohort_aggregation_data_template': Cohort.aggregation_data_template,
        }


class DocumentsHandler(ViewHandler):
    def do(self):
        return "documents.html", {}


class EntityHandler(ViewHandler):
    """For viewing entity json."""
    def do(self):
        return 'entity.html', {}


class FourOhFourHandler(ViewHandler):
    """Doesn't handle real 404 errors, just the url /404."""
    def do(self):
        return self.http_not_found()


class GenericHandler(ViewHandler):
    """Generic handler for simple pages that don't require a custom handler but
    DO require session management provided by BaseHandler."""
    def do(self, template_name):
        # Don't serve index.html separately from the HomeHandler, i.e. `/`
        # should point to index.html, but `/index` should NOT, because Google
        # will list it as redundant content.
        if template_name == 'index':
            return self.http_not_found()

        # Otherwise, serve up any link that matches either a template or a
        # short link. If neither exists, 404 their butts.
        template = template_name + ".html"
        if os.path.isfile('templates/' + template):
            return template, {}
        else:
            # Handle this path as a short link, defined on god panel.
            link = ShortLink.get(self.request.path)
            if link:
                # Server issues 302 to redirect.
                self.redirect(str(link.long_link))  # avoid unicode
                return
            else:
                # No short link on record: 404.
                return self.http_not_found()


class GodHandler(ViewHandler):
    """Who presumes to handle God?"""
    def do(self):
        if self.access_restricted(
            ['researcher', 'school_admin', 'teacher', 'student', 'public']):
            return

        # We want to avoid populating the same datastore twice. So attempt to
        # detect if the populate script has already been done.
        programs_exist = Program.all().count() > 0

        # Load the available short links.
        short_links = []
        for sl in ShortLink.all().filter('deleted =', False).run():
            short_links.append(sl.to_dict())
        return 'god.html', {
            'programs_exist': programs_exist,
            'short_links': short_links,
        }


class HelpHandler(ViewHandler):
    def do(self):
        user = self.get_current_user()
        # This page contains the cross-site test, and so needs to create a
        # test user in the context of some program. Provide the id of the
        # test program for this purpose.
        programs = self.internal_api.get('program', {'abbreviation': 'TP1'})
        if len(programs) is 1:
            test_program = programs[0]
        else:
            raise Exception("Problem loading TP1 on help page.")
        return 'help.html', {
            'user': user,
            'test_program': test_program,
        }


class TransitionMindsetsHelpHandler(ViewHandler):
    """Special help page for National Pilot Dissemination use.

    If the Eileen Horng's contact info and the dissemination are ancient
    history, please delete this handler, the url in the map below, and the
    corresponding html template.
    """
    def do(self):
        user = self.get_current_user()
        # This page contains the cross-site test, and so needs to create a
        # test user in the context of some program. Provide the id of the
        # test program for this purpose.
        programs = self.internal_api.get('program', {'abbreviation': 'TP1'})
        if len(programs) is 1:
            test_program = programs[0]
        else:
            raise Exception("Problem loading TP1 on help page.")
        return 'transition_mindsets_help.html', {
            'user': user,
            'test_program': test_program,
            'show_footer': False
        }


class HomeHandler(ViewHandler):
    """The pegasus "home" page."""

    def dispatch(self):
        """Overrides ViewHandler.dispatch and the connection check."""
        url_handlers.BaseHandler.dispatch(self)

    def get(self):
        """Overrides BaseHandler.get and session management for max speed."""
        template = 'index.html'
        jinja_environment = jinja2.Environment(
            autoescape=True,
            loader=jinja2.FileSystemLoader('templates'))
        params = {
            'current_year': datetime.date.today().year,
        }
        html_str = jinja_environment.get_template(template).render(**params)
        self.response.write(html_str)


class ProgramsHandler(ViewHandler):
    """Similar to HomePageHandler, but with extra redirection rules."""

    # List of programs displayed on the programs page, with tags for selecting
    # subsets based on the query string.
    available_programs = [
        # We're going to start enrolling for 2018 in March.
        {
            'abbr': 'cg',
            'tags': ('college'),
            'name': "Growth Mindset for College Students",
        },
        {
            'abbr': 'cb',
            'tags': ('college'),
            'name': "Social-Belonging for College Students",
        },
        {
            'abbr': 'elevate',
            'tags': ('highschool'),
            'name': "Copilot-Elevate",
        },
        {
            'abbr': 'ep',
            'tags': ('highschool'),
            'name': "The Engagement Project",
        },
        {
            'abbr': 'hg',
            'tags': ('highschool'),
            'name': "Growth Mindset for 9th Graders",
        },
    ]

    def dispatch(self):
        """Overrides ViewHandler.dispatch and the connection check."""
        url_handlers.BaseHandler.dispatch(self)

    def get(self, filter_text=None):
        """Display list of programs or redirect to appropriate choice.

        Overrides BaseHandler.get and session management for max speed.

        The page should:

        1. Display all available programs, unless
        2. The parameter `filter` is in the query string in which case
           a. the value `college` limits the list of programs to those
              appropriate for college students
           b. the value `highschool` limits the list of programs to those
              appropriate for high school students.
        3. If for any reason (including filter values) the list of programs
           would have a length of one, the page should redirect via a 302
           directly to that program's orientation page.
        """
        if not filter_text:
            programs = self.available_programs
        else:
            programs = [p for p in self.available_programs
                        if filter_text in p['tags']]

        college_programs = [p for p in programs if 'college' in p['tags']]
        highschool_programs = [p for p in programs if 'highschool' in p['tags']]

        if len(programs) == 1:
            abbr = programs[0]['abbr']
            self.redirect('/orientation/{}'.format(abbr), 302)
        else:
            jinja_environment = jinja2.Environment(
                autoescape=True,
                loader=jinja2.FileSystemLoader('templates'))
            template = jinja_environment.get_template('programs.html')
            html_str = template.render({
                'template_name': 'programs',
                'programs': programs,
                'college_programs': college_programs,
                'highschool_programs': highschool_programs,
            })
            self.response.write(html_str)


class HomePageHandler(ViewHandler):
    """Very simple handler for static, public-facing pages."""

    def dispatch(self):
        """Overrides ViewHandler.dispatch and the connection check."""
        url_handlers.BaseHandler.dispatch(self)

    def get(self, template_name):
        """Overrides BaseHandler.get and session management for max speed."""
        params = {}

        # Needed for shortcut to register with neptune.
        if util.is_localhost():
            params['neptune_domain'] = 'localhost:8080'
            params['neptune_protocol'] = 'http'
            params['triton_domain'] = 'localhost:10080'
            params['triton_protocol'] = 'http'
        else:
            params['neptune_domain'] = os.environ['NEPTUNE_DOMAIN']
            params['neptune_protocol'] = 'https'
            params['triton_domain'] = os.environ['TRITON_DOMAIN']
            params['triton_protocol'] = 'https'

        # Provide the current template name to jinja so it can highlight the
        # active navbar link.
        params['template_name'] = template_name

        template = template_name + '.html'
        if not os.path.isfile('templates/' + template):
            template, params = self.http_not_found()
        jinja_environment = jinja2.Environment(
            autoescape=True,
            loader=jinja2.FileSystemLoader('templates'))
        html_str = jinja_environment.get_template(template).render(params)
        self.response.write(html_str)


class IdentifyHandler(ViewHandler):
    """Where participants enter. Different from authentication."""
    def do(self):
        user = self.get_current_user()
        page_action = self.request.get('page_action')
        if page_action == 'go_to_program':
            session_ordinal = self.request.get('session_ordinal')
            cohort_id = self.request.get('cohort')
            classroom_id = self.request.get('classroom')
            classroom = self.internal_api.get_from_path('classroom', classroom_id)
            program_id = classroom.assc_program_list[0]
            program = self.internal_api.get_from_path('program', program_id)
            request_params = {'cohort': cohort_id, 'classroom': classroom_id,
                              'session_ordinal': session_ordinal}
            # redirect the user to this activity within the program app
            url = '/p/{}/student?{}'.format(program.abbreviation,
                                            urllib.urlencode(request_params))
            self.redirect(url)
            return
        elif user.user_type != 'public':
            # Users arriving here are students who want to sign in. Don't let
            # existing sessions get in the way. Boot the current user.
            self.redirect('/logout?redirect=/go')
            return
        return 'identify.html', {}


class ImpersonateHandler(ViewHandler):
    def do(self):
        # Don't restrict any access except public; a legitimate user may be
        # impersonating a teacher or student and coming to this page in order
        # to STOP impersonating, and we need to let them do so.
        if self.access_restricted(['public']):
            return

        user = self.get_current_user()  # may be impersonated user
        normal_user = self.get_current_user(method='normal')

        # The impersonation page provides links relevant to the impersonated
        # user. Look up details so we can construct those links.
        cohort_ids = [id for id in user.assc_cohort_list]
        cohorts = self.api.get('cohort', {'id': cohort_ids})

        program_ids = list(set([c.assc_program_list[0] for c in cohorts]))
        programs = self.api.get('program', {'id': program_ids})
        program_dict = {p.id: p for p in programs}

        # Structure the information as a list of dictionaries, each dict with
        # the right URL and link description stuff.
        program_link_info = []
        for cohort in cohorts:
            info = {}
            program = program_dict[cohort.assc_program_list[0]]
            # both teachers and school_admins use the teacher program
            if user.user_type == 'student':
                # Assumes students are only in one classroom, so break if
                # that's not true.
                if len(user.assc_classroom_list) is not 1:
                    raise Exception(
                        "Problem with student's classroom associations: {}."
                        .format(user.id))
                info['user_type'] = 'student'
                info['link'] = '/p/{}/{}?classroom={}&cohort={}'.format(
                    program.abbreviation, info['user_type'],
                    user.assc_classroom_list[0], cohort.id)
            else:
                info['user_type'] = 'teacher'
                info['link'] = '/p/{}/{}?cohort={}'.format(
                    program.abbreviation, info['user_type'], cohort.id)
            info['program_name'] = program.name
            program_link_info.append(info)

        # With the necessary information wrangled, figure out what the page is
        # supposed to do: redirect, impersonate, etc.
        redirect_url = None
        page_action = self.request.get('page_action')
        if page_action == 'impersonate':
            target_id = self.request.get('target')
            target = self.internal_api.get_from_path('user', target_id)
            try:
                self.impersonate(target)
                redirect_url = str(self.request.get('redirect')) or '/impersonate'
            except PermissionDenied:
                redirect_url = '/impersonate?permission_denied=true'
        elif page_action == 'stop_impersonating':
            # clear the impersonated user
            self.stop_impersonating()
            redirect_url = '/impersonate'

        if redirect_url:
            self.redirect(redirect_url)
            return

        return 'impersonate.html', {'program_link_info': program_link_info}


class LoginHandler(ViewHandler):
    """Combination login and registration page. Google authentication will do
    either one, depending on whether your user already exists."""
    def do(self, program_abbreviation):
        user = self.get_current_user()

        # initialize variables
        registration_requested = self.request.get('registration_requested')
        redirect = str(self.request.get('redirect'))
        login_url = '/yellowstone_login'
        success_message = None
        error_message = None
        program_id = None
        program_name = None
        show_registration = False
        show_google_login = True

        # if a program was specified, look it up and adjust future redirects
        if program_abbreviation:
            program_abbreviation = program_abbreviation.upper()
            login_url += '/' + program_abbreviation
            # User has arrived via a program-specific link. Look up the program
            # to get its id (for association) and name (for a welcome message).
            results = self.internal_api.see(
                'program', {'abbreviation': program_abbreviation})
            if len(results) is 1:
                # If this is a public-registration program, then deny access.
                program_conf = Program.get_app_configuration(
                    program_abbreviation)
                if getattr(program_conf, 'public_registration', False):
                    return self.http_not_found()
                # Otherwise we can continue...
                program = results[0]
                program_id = program.id
                program_name = program.name
                show_registration = True
            elif len(results) is 0:
                # There's no program with this abbreviation.
                return self.http_not_found()

        # Set up how the user will COME BACK from google login, which will be
        # used if they click the google login button.
        google_redirect = '{}?registration_requested=google'.format(login_url)
        if redirect:
            google_redirect += '&redirect={}'.format(redirect)
        if program_id:
            google_redirect += '&program={}'.format(program_id)
        google_login_url = app_engine_users.create_login_url(google_redirect)

        if registration_requested:
            # They're signed in with google or facebok, allow registration IF
            # they've arrive with a program id. If they're a new user AND
            # there's no program id, display a failure message.
            auth_response = self.authenticate(auth_type=registration_requested)
            if auth_response is None:
                error_message = "Error during sign in. Please try again."
                redirect = None
            elif auth_response is False and program_id is None:
                error_message = ("Unable to register.<br>Please use the "
                                 "registration link provided by your school.")
                redirect = None
            else:
                # OK to register and/or sign in; register() does both
                user, user_is_new = self.register(program_id,
                                                  registration_requested)
                if user is False:
                    error_message = ("You already have a PERTS account with "
                                     "that email address.")
                    redirect = None
                else:
                    if (user.user_type in ['teacher', 'school_admin'] and
                        not user.registration_complete):
                        # Special case: force certain users to take additional
                        # registration steps. The registration_email_sent flag
                        # displays a confirmation that a registration email was
                        # sent.
                        redirect = '/registration_survey?'
                        if user_is_new:
                            redirect += 'registration_email_sent=true&'
                        if program_id:
                            redirect += 'program={}&'.format(program_id)

        # Any users who have successfully registered or logged in via the code
        # above and are still here should be sent on (this is normal for google
        # users, who are returning from a google login page).
        # Also, any signed in user with a home page arriving at login should be
        # redirected to their home page.
        if (user is not False and user.user_type != 'public' and
            user.user_type in config.user_home_page):
            if not redirect:
                redirect = config.user_home_page[user.user_type]
            # else leave redirect set per the URL
            self.redirect(redirect)
            return

        # If user has just finished a password reset, show them a message.
        if self.request.get('password_reset_successful') == 'true':
            success_message = "Your password has been reset."
            show_google_login = False

        return 'login.html', {
            'show_registration': show_registration,
            'program_id': program_id,
            'program_name': program_name,
            'google_login_url': google_login_url,
            'error_message': error_message,
            'success_message': success_message,
            'show_google_login': show_google_login,
        }


class LogoutHandler(ViewHandler):
    """Clears the user's session, closes connections to google."""
    def do(self):
        # The name of the login cookie is defined in
        # url_handlers.BaseHandler.session()
        self.response.delete_cookie('perts_login')
        # This cookie is created when logging in with a google account in
        # production.
        self.response.delete_cookie('SACSID')
        # This cookie is created when logging in with a google account with
        # the app engine sdk (on localhost).
        self.response.delete_cookie('dev_appserver_login')
        self._user = None
        self._impersonated_user = None
        # ultimately the user will wind up here
        redirect = self.request.get('redirect') or '/'
        self.redirect(redirect)


class ProgramAppHandler(ViewHandler):
    """Handles page requests for program apps."""
    def do(self, program_abbreviation, template_name):
        if self.access_restricted(['public']):
            return

        abbr = program_abbreviation.upper()
        program_list = self.internal_api.get('program', {'abbreviation': abbr})
        if len(program_list) is not 1:
            logging.error("Bad program link: {}.".format(self.request.path))
            return self.http_not_found()
        program = program_list[0]

        # We'll display a warning to the user if this is not true.
        valid_url = True

        # The cohort is also a critical part of the app, otherwise we can't
        # record data.
        cohort = None
        cohort_id = self.request.get('cohort')
        # Validate the id. It should exist and match the program.
        if cohort_id == '':
            valid_url = False
        else:
            cohort = self.api.get_from_path('cohort', cohort_id)
            if cohort is None:
                valid_url = False
            else:
                if program.id not in cohort.assc_program_list:
                    valid_url = False

        # The classroom is critical IF the user is a student.
        classroom = None
        classroom_id = self.request.get('classroom')
        if template_name == 'student' and cohort is not None:
            # Validate.
            if classroom_id == '':
                valid_url = False
            else:
                classroom = self.api.get_from_path('classroom', classroom_id)
                if classroom is None:
                    valid_url = False
                else:
                    if cohort.id not in classroom.assc_cohort_list:
                        valid_url = False

        if not valid_url:
            return self.http_not_found()

        # get program app config
        app_config = Program.get_app_configuration(abbr, template_name)

        template_path = 'programs/{}/{}.html'.format(
            program_abbreviation, template_name)
        params = {
            'show_main_nav': False,
            'show_footer': False,
            'template_name': template_name,
            'program': program,
            'cohort': cohort,
            'classroom': classroom,
            'config_json': json.dumps(app_config),
            'server_date_time': str(datetime.datetime.now()),
        }
        template_directory = ''  # i.e. from the root of the app

        return template_path, params, template_directory


class ProgramStaticHandler(ViewHandler):
    """Handles page requests for static program documents."""
    def do(self, program_abbreviation, template_name):

        abbr = program_abbreviation.upper()
        program_list = self.internal_api.get('program', {'abbreviation': abbr})
        if len(program_list) is not 1:
            logging.error("Bad program link: {}.".format(self.request.path))
            return self.http_not_found()

        program = program_list[0]
        program_config = Program.get_app_configuration(abbr)

        if getattr(program_config, 'public_registration', False):
            # Allow public users to look up cohorts, because this program is
            # public-access.
            temp_api = self.internal_api
        elif self.access_restricted(['public']):
            # Programs which use public registration don't require sign-in to
            # view documents. If this is not a public registration program and
            # the user is not signed in, redirect them to login.
            return
        else:
            temp_api = self.api

        # Some documents require the cohort id to display the cohort code.
        cohort_id = self.request.get('cohort')
        # Validate the id. It should exist and match the program.
        try:
            cohort = temp_api.get_from_path('cohort', cohort_id)
        except:
            cohort = None

        template_path = 'programs/{}/{}.html'.format(
            program_abbreviation, template_name)
        params = {
            'cohort': cohort,
            'template_name': template_name,
            'program': program,
        }
        template_directory = ''  # i.e. from the root of the app

        return template_path, params, template_directory


class ProgramPublicRegistrationHandler(ViewHandler):
    """Page where anyone can sign up for a program."""
    def do(self, program_abbreviation):
        # No access is restricted.

        abbr = program_abbreviation.upper()
        program_list = self.internal_api.get('program', {'abbreviation': abbr})
        if len(program_list) is not 1:
            logging.error("Bad public registration link: {}."
                          .format(self.request.path))
            return self.http_not_found()

        program = program_list[0]

        program_config = Program.get_app_configuration(program.abbreviation)

        # Not all programs are public access. Check before continuing.
        if not getattr(program_config, 'public_registration', False):
            return self.http_not_found()

        # Registration requires the user to select a school. Provide them a
        # list of existing schools to pick from.
        cohorts = self.internal_api.get(
            'cohort', {'assc_program_list': program.id})
        school_ids = [c.assc_school_list[0] for c in cohorts]
        schools = self.internal_api.get_by_ids(school_ids)

        template_path = '/programs/{}/public_registration.html'.format(abbr)
        params = {
            'program': program.to_dict(),
            'program_config': program_config,
            'school_list': [s.to_dict() for s in schools],
        }
        template_directory = ''  # i.e. from the root of the app
        return template_path, params, template_directory


class QualtricsSessionCompleteHandler(ViewHandler):
    """Publicly accessible "you're done" page that also saves progress 100.

    Takes 3 request parameters:
    * program - str, the program abbreviation (NOT id)
    * user - str, the user id
    * activity_ordinal - int, e.g. 1 for session 1, etc.
    """
    def do(self):
        # No call to self.access_restricted; publicly available page.

        params = util.get_request_dictionary(self.request)

        # Ignore certain calls that typically come from Qualtrics when people
        # are testing.
        is_preview = (params['program'] and params['user'] == '' and
                      params['activity_ordinal'] is None)
        if is_preview:
            logging.info("Interpreted as Qualtrics testing. Ignoring.")
            return 'qualtrics_session_complete.html', {'show_footer': False}

        if 'program' in params:
            params['program'] = params['program'].upper()

        try:
            program = self.check_params(params)
        except IdError:
            logging.error("User does not exist: {}.".format(params['user']))
            return self.http_not_found()
        except Exception as e:
            logging.error(e)
            return self.http_not_found()

        # Save a progress pd, value 100. Aggregation will make sure they get a
        # COM code.
        o = int(params['activity_ordinal'])
        self.internal_api.create('pd', {
            'program': program.id,
            'activity_ordinal': o,
            'scope': params['user'],
            'scope_kind': 'user',
            'variable': 's{}__progress'.format(o),
            'value': 100,
        })

        return 'qualtrics_session_complete.html', {'show_footer': False}

    def check_params(self, params):
        """Raises exceptions if there are problems with request data."""

        # Make sure all parameters are present.
        required = ['program', 'user', 'activity_ordinal']
        missing = set(required) - set(params.keys())
        if missing:
            raise Exception("Missing required parameters: {}.".format(missing))

        program_list = self.internal_api.get(
            'program', {'abbreviation': params['program']})
        if len(program_list) is not 1:
            raise Exception("Invalid program: {}.".format(params['program']))
        else:
            program = program_list[0]

        # User must exist and be associated with provided program.
        user = self.internal_api.get_from_path('user', params['user'])
        if user.assc_program_list[0] != program.id:
            raise Exception("Invalid program for user: {} {}."
                            .format(params['program'], params['user']))

        # Activity ordinal must be among the available program sessions.
        o = int(params['activity_ordinal'])
        student_program_outline = Program.get_app_configuration(
            program.abbreviation, 'student')['outline']
        modules_match = [module.get('activity_ordinal', None) is o
                         for module in student_program_outline]
        if not any(modules_match):
            raise Exception("Invalid activity_ordinal: {}.".format(o))

        return program


class RegistrationSurveyHandler(ViewHandler):
    """Once a teacher (or higher) has registered through one method or another,
    we need some basic information from them."""
    def do(self):
        if self.access_restricted(['student', 'public']): return

        user = self.get_current_user()

        # If they've already done it, don't make them do it again.
        if user.registration_complete:
            self.response.write("You've already completed registration.")
            return

        # Display a notice to users immediately after registering that they
        # have been sent an email. This notice is triggered by a request
        # variable b/c users may arrive at this survey again later and it
        # wouldn't make sense to show this to them at that later time.
        registration_email_sent = self.request.get(
            'registration_email_sent') == 'true'

        program_id = self.request.get('program')
        if not program_id:
            # If they didn't enter with a program id, try to look it up.
            if len(user.assc_program_list) > 0:
                program_id = user.assc_program_list[0]
            # If we still can't figure it out, the url is invalid.
            else:
                return self.http_not_found()
        program = self.internal_api.get_from_path('program', program_id)

        return 'registration_survey.html', {
            'cohorts': self.api.see('cohort', {}),
            'program_id': program_id,
            'program': program,
            'registration_email_sent': registration_email_sent,
        }


class ResetPasswordHandler(ViewHandler):
    """A page with one purpose: users put new passwords into a field and
    submit them. No log in, no fanciness."""
    def do(self, token):
        # Check the token right away, so users don't find out it's bad AFTER
        # they fill out the form.
        user = self.api.check_reset_password_token(token)
        return 'reset_password.html', {
            'token': token,
            'token_valid': user is not None,
        }


class TestHandler(ViewHandler):
    def do(self):
        user = self.get_current_user()
        if user.user_type not in ['researcher', 'god']:
            self.response.write('You are not allowed to view this page.')
            return
        #   pass in CP1 for automated testing, unless it does not exist
        try:
            program = self.api.get('program', {'abbreviation': 'CP2'})[0]
        except:
            program = {'id': 0}
        return 'test.html', {
            'program': program,
        }


def PdfHandler(pdf_filename):
    pdf_path = 'static_readable/'

    class Handler(url_handlers.BaseHandler):
        def get(self):
            logging.info("Referer: {}"
                         .format(self.request.headers.get('Referer', None)))
            self.response.headers.update({
                'Content-Type': 'application/pdf',
                'Content-Disposition': ('filename={}'
                                        .format(pdf_filename)),
            })
            with open(pdf_path + pdf_filename, 'r') as fh:
                self.response.body = fh.read()

    return Handler


webapp2_config = {
    'webapp2_extras.sessions': {
        # cam. I think this is related to cookie security. See
        # http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html
        'secret_key': '8YcOZYHVrVCYIx972K3MGhe9RKlR7DOiPX2K8bB8',
        # @todo: seem like obvious choices, read more and implement generally
        # https://webapp-improved.appspot.com/api/webapp2_extras/sessions.html
        # 'cookie_args': {
        #     'secure': True,
        #     'httponly': True,
        # }
    },
}

app = webapp2.WSGIApplication([
    # Redirects the subdomain blog.perts.net to www.perts.net/blog
    # https://webapp-improved.appspot.com/guide/routing.html#domain-and-subdomain-routing
    DomainRoute('blog.perts.net', [
        webapp2.Route('/', handler=BlogSubdomainRedirectHandler)
    ]),
    ('/', HomeHandler),
    ('/programs/?', ProgramsHandler),
    ('/programs/(college|highschool)/?', ProgramsHandler),
    ('/({})/?'.format('|'.join(public_home_pages)), HomePageHandler),
    ('/404/?', FourOhFourHandler),
    ('/account/?', AccountHandler),
    ('/help', HelpHandler),
    ('/transition_mindsets/help', TransitionMindsetsHelpHandler),
    ('/d/?', DashboardHandler),
    ('/documents/?', DocumentsHandler),
    ('/done', QualtricsSessionCompleteHandler),
    ('/entity/?', EntityHandler),           # for viewing entity json
    # The old Yellowstone participant portal.
    # Currently redirected, see redirector.py.
    # ('/go/?', IdentifyHandler),
    ('/god/?', GodHandler),
    ('/impersonate/?', ImpersonateHandler),
    # redirected to neptune
    # ('/login/?(.*)', LoginHandler),
    # ('/logout/?', LogoutHandler),
    ('/yellowstone_login/?(.*)', LoginHandler),
    ('/yellowstone_logout/?', LogoutHandler),
    ('/p/(.*)/(student|teacher)/?', ProgramAppHandler),
    ('/p/(.*)/public_registration/?', ProgramPublicRegistrationHandler),
    ('/p/(.*)/(.*)', ProgramStaticHandler),
    ('/registration_survey/?', RegistrationSurveyHandler),
    ('/reset_password/(.*)', ResetPasswordHandler),
    ('/test/?', TestHandler),
    ('/privacy/?', PdfHandler('privacy_policy_v1-3.pdf')),
    ('/terms-of-use/?', PdfHandler('terms_of_use_v1-0.pdf')),
    ('/sse-survey-pdf/?', PdfHandler('sse-survey-pdf.pdf')),
    # GenericHandler line *must* go last.
    # All other handlers above this line.
    ('/(.*)', GenericHandler),
], config=webapp2_config, debug=debug)
