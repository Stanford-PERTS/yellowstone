"""Contains classes that have many instances and use gobally-unique,
machine-readable key names, which are also stored as their 'id' property."""


from google.appengine.api import mail               # needed for email
from google.appengine.ext import db
import copy                                         # passing lists by value
import datetime
import jinja2                                       # templating emails
import json
import logging                                      # error logging
import markdown
import random
import re
import string

from core import PermissionDenied
from simple_profiler import Profiler
import config
import core
import phrase
import programs
import util


class IdError(Exception):
    """Used when there is a problem looking something up by id."""
    pass


class IdModel(core.Model):
    """Ancestor for entities that use a machine-readable, globally unique id as
    their key name. Useful for classes that will have many instances which will
    need to be looked up by id."""

    # This id is the same id string that is stored in key_name. It is stored
    # redundantly here so that we can easily query on it (for some reason it
    # is difficult to query on key_name in GAE).
    # Example:
    # id_list = ['Program_mW4iQ4cOJsbcJMnen1', 'Program_80h41Q4cOJsb084t1zz']
    # MyEntityClass.all().filter('id =', id_list)
    id = db.StringProperty()
    deleted = db.BooleanProperty(default=False)
    is_archived = db.BooleanProperty(default=False)
    is_test = db.BooleanProperty(default=False)

    # How PERTS uses ids
    #
    # We adopt our own convention for what an id is and how it's written.  A
    # PERTS id is a globally-unique string that looks like
    # 'Program_mW4iQ4cOJsbcJM66nen1'. An id is always sufficient to look up an
    # entity directly. GAE works differently, and converting between the two is
    # handled in the function below. For more details, read on.
    #
    # GAE identifies entities with keys, which are objects made of two parts: a
    # human-readable key name and a kind, which is the class name. A key is
    # globally unique. We use GAE's key names as our PERTS ids. Because
    # our ids *include* the kind, we can construct the full key based only on
    # the id. The fact that our id strings need to be converted to GAE keys is
    # abstracted here.
    #
    # Addendum, 2014-04-27
    # After adopting the above convention, which works only for root entities
    # that do not exist in entity groups, we found it necessary to use entity
    # groups. This creates a problem for ids, because descendant keys must
    # include information about their parents, and thus cannot be constructed
    # from a simple PERTS id. For example, user-scope pds are stored as
    # descendants of a user, and that user's key is part of the pds' key. In
    # the GAE documentation, they give this example of the information
    # necessary to construct a descendant key:
    #
    # [Person:Dad, Person:Me]
    # (https://developers.google.com/appengine/docs/python/datastore/entities#Python_Ancestor_paths)
    #
    # Our solution to this is include ancestry information in our ids, like so:
    # Pd_fDjMV6BQB8reJH1EhBUQ.User_1mIX8gk0uhQxzuaeU6sD
    #
    # These chained ids are broken down and interpreted by the same function
    # that looks up simple root ids (IdModel.get_by_id), so this alteration
    # to the convention should be transparent.


    @classmethod
    def create(klass, **kwargs):
        if 'key_name' in kwargs:
            raise Exception("IdModel entities may not specify a key name.")
        id = klass.generate_id()
        return klass(key_name=id, id=id, **kwargs)

    @classmethod
    def generate_id(klass):
        """Make a pegasus-style id, e.g. 'Program_mW4iQ4cOJsbcJM66nen1'."""
        chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
        suffix = ''.join(random.choice(chars) for x in range(20))
        return klass.__name__ + "_" + suffix

    @classmethod
    def get_by_id(klass, key_name_or_list):
        """The main way to get entities with known ids.
        Raises IdError if the id is malformed or can't be found.
        You can only use this function on inheriting classes which have
        a specific kind."""

        # Sanitize input to a list of strings.
        if type(key_name_or_list) in [str, unicode]:
            key_names = [key_name_or_list]
        elif type(key_name_or_list) is list:
            key_names = key_name_or_list
        else:
            raise Exception("Invalid key_name / id: {}.".format(
                key_name_or_list))

        # Iterate through the list, generating a key for each id
        keys = []
        for kn in key_names:
            ancestry = kn.split('.')
            if len(ancestry) > 1:
                # This id specifies a parent, so we'll need to use it when we
                # generate the key.
                parent_id = '.'.join(ancestry[1:])
                parent_kind = core.get_kind(parent_id)
                parent_class = core.kind_to_class(parent_kind)
                parent_key = parent_class.get_by_id(parent_id).key()
            else:
                # No parent is specified, i.e. this is a root entity.
                parent_key = None

            # Given the target entities class (klass), its key name, and
            # (maybe) it's parent, we can generate the key and fetch the
            # entity.
            key = db.Key.from_path(klass.__name__, kn, parent=parent_key)
            keys.append(key)
        results = db.get(keys)

        # run custom startup code, if such behavior is defined
        for e in results:
            if hasattr(e, 'startup'):
                e.startup()

        # Wrangle results into expected structure.
        if len(results) is 0:
            raise IdError("No entity exists with id: {}.".format(
                key_name_or_list))
        if type(key_name_or_list) in [str, unicode]:
            return results[0]
        if type(key_name_or_list) is list:
            return results

    def __str__(self):
        """A string represenation of the entity. Goal is to be readable.

        Returns, e.g. <id_model.Pd Pd_oha4tp8a4tph1>.
        Native implementation does nothing useful.
        """
        return '<id_model.{} {}>'.format(self.__class__.__name__, self.id)

    def __repr__(self):
        """A unique representation of the entity. Goal is to be unambiguous.

        But our ids are unambiguous, so we can just forward to __str__.

        Native implemention returns a useless memory address, e.g.
            <id_model.Pd 0xa5e418cdd>
        The big benefit here is to be able to print debuggable lists of
        entities, without need to manipulate them first, e.g.
            print [entity.id for entity in entity_list]
        Now you can just write
            print entity_list
        """
        return self.__str__()

    # special methods to allow comparing entities, even if they're different
    # instances according to python
    # https://groups.google.com/forum/?fromgroups=#!topic/google-appengine-python/uYneYzhIEzY
    def __eq__(self, value):
        """Allows entity == entity to be True if keys match.

        Is NOT called by `foo is bar`."""
        if self.__class__ == value.__class__:
            return self.id == value.id
        else:
            return False

    # Because we defined the 'equals' method, eq, we must also be sure to
    # define the 'not equals' method, ne, otherwise you might get A == B is
    # True, and A != B is also True!
    def __ne__(self, value):
        """Allows entity != entity to be False if keys match."""
        if self.__class__ == value.__class__:
            # if they're the same class, compare their keys
            return self.id != value.id
        else:
            # if they're not the same class, then it's definitely True that
            # they're not equal.
            return True

    def __hash__(self):
        """Allows entity in entity_list to be True."""
        return hash(str(self.key()))


class Activity(IdModel):
    activity_ordinal = db.IntegerProperty()  # counts from 1
    user_type = db.StringProperty()  # 'student' or 'teacher'
    teacher = db.StringProperty()
    status = db.StringProperty()  # see config.allowed_activity_states
    # Although technically all dates and times in App Engine are in UTC, we
    # accept these date strings from clients as they are given, i.e. in their
    # local timezone. Their browsers interpret these dates in that same
    # timezone.
    # That means if you schedule an activity for Jan 1, 2014, and you happen to
    # live in Australia, this property has the value of 2014-01-01 00:00:00 UTC
    # on the server, even though that's technically 12 hours different. The
    # browser, when receiving that date again, does NOT interpret it as UTC,
    # correctly resolving to Jan 1 in Australia again.
    scheduled_date = db.DateProperty()
    program_abbreviation = db.StringProperty()
    roster_complete = db.BooleanProperty(default=False)
    aggregation_data = util.DictionaryProperty(default={
        'total_students': 0,
        'certified_students': 0,
        'certified_study_eligible_dict': {
            'n': 0,
            'completed': 0,
            'makeup_eligible': 0,
            'makeup_ineligible': 0,
            'uncoded': 0
        },
    })
    aggregation_json = util.JsonProperty()

    assc_program_list = db.StringListProperty()  # actually one
    assc_cohort_list = db.StringListProperty()  # actually one
    assc_classroom_list = db.StringListProperty()  # actually one

    def name(self):
        # If this entity has been loaded via a projection query (/api/see), it
        # may not have all its expected properties. Handle this gracefully.
        if not self.program_abbreviation:
            return None
        config = Program.get_app_configuration(self.program_abbreviation,
                                               self.user_type)
        is_activity = lambda a: 'type' in a and a['type'] == 'activity'
        activities = filter(is_activity, config['outline'])
        return activities[self.activity_ordinal - 1]['name']

    def _get_date(self, open_or_closed):
        # If this entity has been loaded via a projection query (/api/see), it
        # may not have all its expected properties. Handle this gracefully.
        if not self.program_abbreviation:
            return None
        config = Program.get_app_configuration(self.program_abbreviation,
                                               self.user_type)
        # App Engine IntegerProperty values are return as python longs.
        # Make sure it's a true int so we can compare it as expected.
        my_ordinal = int(self.activity_ordinal)
        for t in config['outline']:
            if (
                'type' in t and
                t['type'] == 'activity' and
                # Sloppy coders may put strings in the config file. Make sure
                # that does't break comparisons by coercing to int.
                int(t['activity_ordinal']) is my_ordinal
            ):
                template = t
        return template['date_' + open_or_closed]

    def to_dict(self):
        """Overrides Model.to_dict() so that dynamically-retrieved info, like
        name, can be included in the dictionary representation."""
        d = core.Model.to_dict(self)
        d['name'] = self.name()
        d['date_open'] = self._get_date('open')
        d['date_closed'] = self._get_date('closed')
        return d

    def interpreted_status(self):
        today = datetime.date.today()
        three_days = datetime.timedelta(hours=3)

        if self.status == "completed" or self.status == "aborted":
            interpreted_status = self.status
        elif self.scheduled_date is None:
            interpreted_status = "unscheduled"
        elif today - self.scheduled_date > three_days:
            interpreted_status = "behind"
        else:
            interpreted_status = "scheduled"
        return interpreted_status

    def get_long_form_date_string(self):
        """Get scheduled data as a string, e.g. 'Monday, August 11th, 2014'"""
        if not self.scheduled_date:
            return ''
        suffix = util.ordinal_suffix(self.scheduled_date.day)
        # The hyphen tells it to drop leading zeroes in the date, e.g. '1'
        # rather than '01'. Then add in an appropriate suffix to the date,
        # e.g. '2nd'.
        return self.scheduled_date.strftime('%A, %B %-d{}, %Y').format(suffix)


class Classroom(IdModel):
    name = db.StringProperty()
    teacher_name = db.StringProperty()
    teacher_email = db.StringProperty()
    anomaly_notes = db.TextProperty()
    roster_complete = db.BooleanProperty(default=False)
    # Records the time the user marked the roster as complete.
    roster_completed_datetime = db.DateTimeProperty()

    assc_user_list = db.StringListProperty()  # the school_admin
    assc_cohort_list = db.StringListProperty()  # actually one
    assc_school_list = db.StringListProperty()  # actually one
    assc_program_list = db.StringListProperty()  # actually one


class Cohort(IdModel):
    name = db.StringProperty()
    code = db.StringProperty()
    status = db.StringProperty()  # active, completed, or deleted
    promised_students = db.IntegerProperty()
    # Controls how the identify page behaves for this cohort. Current allowed
    # values are:
    # * 'default' - students given the full first and last names plus a middle
    #   initial if they have one.
    # * 'alias' - students are only allowed in if their name matches an
    #   existing hard-coded alias. Some schools request this so they never have
    #   to share identifying information about students with us; we only ever
    #   see their alias.
    # * 'dissemination' - students identify themselves with the first three
    #   letters of their first name and first three letters of their last name.
    identification_type = db.StringProperty(default='default')
    anomaly_notes = db.TextProperty()
    aggregation_data_template = {
        'unscheduled': 0, 'scheduled': 0, 'behind': 0, 'completed': 0,
        'incomplete_rosters': 0,
        'total_students': 0,
        'certified_students': 0,
        'certified_study_eligible_dict': {
            'n': 0,
            'completed': 0,
            'makeup_eligible': 0,
            'makeup_ineligible': 0,
            'uncoded': 0
        },
    }
    aggregation_data = util.DictionaryProperty()
    aggregation_json = util.JsonProperty()

    assc_program_list = db.StringListProperty()
    assc_school_list = db.StringListProperty()

    @classmethod
    def generate_id(klass, code):
        """Cohorts are unique by code; incorporate it into the key name."""
        return 'Cohort_' + code.replace(' ', '-')

    @classmethod
    def create(klass, **kwargs):
        # This is true for all IdModel classes.
        if 'key_name' in kwargs:
            raise Exception("IdModel entities may not specify a key name.")

        # Providing a code on creation is optional, without it we generate one.
        if 'code' not in kwargs:
            # Generate random phrases and check their uniqueness until we have
            # a unique one.
            unique_code = None
            failsafe = 0
            while unique_code is None and failsafe < 10:
                code = phrase.generate_phrase()
                if not Cohort.exists(code):
                    unique_code = code
                failsafe += 1
            if unique_code is None:
                raise Exception("Failed to get unique code")
            kwargs['code'] = unique_code
        id = klass.generate_id(kwargs['code'])
        return klass(key_name=id, id=id, **kwargs)

    @classmethod
    def exists(klass, code):
        """Returns boolean: does a cohort with this code exist?"""
        id = klass.generate_id(code)
        return isinstance(klass.get_by_id(id), klass)

    def validate_put(self, kwargs):
        """Apply rules during an update or create of a Cohort.

        Args:
            kwargs: dict, either the properties being used to create a cohort
                or the properties being updated on an existing cohort.
        """
        if 'code' in kwargs:
            # The only legitimate time to specify a code is on creation, and
            # then it had better not exist already. This check is necessary
            # in addition to the logic in Cohort.create() because codes can
            # be specified manually as well as generated randomly.
            if Cohort.exists(kwargs['code']):
                raise Exception("Error: Cohort codes must be unique!")
            # You can tell when a code is specified on update (rather than
            # on create) because it doesn't match the existing entity property.
            if kwargs['code'] != self.code:
                raise Exception("Cohort codes are immutable.")
        return kwargs


class Email(IdModel):
    """
    An email queue

    Design
    Emails have regular fields, to, from, subject, body.
    Will use jinja to attempt to attempt to interpolate values in the
    template_data dictionary into the body and subject.
    Also a send date and an sent boolean to support queuing.

    orginal author
    bmh October 2013
    """

    to_address = db.StringProperty(required=True)
    from_address = db.StringProperty(required=True)
    reply_to = db.StringProperty(default=config.from_yellowstone_email_address)
    subject = db.StringProperty(default="A message from PERTS")
    body = db.TextProperty()
    html = db.TextProperty()
    scheduled_date = db.DateProperty()
    was_sent = db.BooleanProperty(default=False)
    was_attempted = db.BooleanProperty(default=False)
    errors = db.TextProperty()

    @classmethod
    def create(klass, template_data={}, **kwargs):
        id = Email.generate_id()

        def render(s):
            return jinja2.Environment().from_string(s).render(**template_data)

        kwargs['subject'] = render(kwargs['subject'])
        kwargs['body'] = render(kwargs['body'])

        return Email(key_name=id, id=id, **kwargs)

    @classmethod
    def we_are_spamming(self, email):

        to = email.to_address

        # We can spam admins, like 
        # so we white list them in the config file
        if to in config.addresses_we_can_spam:
            return False

        # We can also spam admins living at a @perts.net
        # domain
        if to.endswith('perts.net'):
            return False

        since = datetime.datetime.utcnow() - \
                datetime.timedelta(
                    days = config.suggested_delay_between_emails
                )

        query = Email.all(
            ).filter(
            'was_sent = ', True ).filter(
            'scheduled_date >= ', since )

        spamming = query.count( limit = 1 ) > 0

        return spamming

    @classmethod
    def log_spamming(self, email):
        to = email.to_address
        logging.error( "We are spamming {}".format(to) )

    @classmethod
    def send(self, email):
        # check for spamming
        if self.we_are_spamming( email ): self.log_spamming( email )

        # Note that we are attempting to send
        # so that we don't keep attempting
        email.was_attempted = True
        email.put()

        # Debugging info
        logging.info(u"sending email: {}".format(email.to_dict()))
        logging.info(u"to: {}".format(email.to_address))
        logging.info(u"subject: {}".format(email.subject))
        logging.info(u"body:\n{}".format(email.body))

        # Make html version
        # if it has not been explicitly passed in
        if not email.html:
            email.html = (
                jinja2.Environment(loader=jinja2.FileSystemLoader('templates'))
                .get_template('email.html')
                .render({'email_body': markdown.markdown(email.body)})
            )

        # try to email
        mail.send_mail(email.from_address,
                       email.to_address,
                       email.subject,
                       email.body,
                       reply_to=email.reply_to,
                       html=email.html)

        email.was_sent = True
        logging.info("""Sent successfully!""")
        email.put()

    @classmethod
    def fetch_next_pending_email(self):
        to_send = Email.all().filter(
            'deleted =', False ).filter(
            'is_archived =', False ).filter(
            'scheduled_date <= ', datetime.datetime.utcnow() ).filter(
            'was_sent =', False ).filter(
            'was_attempted =', False )

        return to_send.get()

    @classmethod
    def send_pending_email(self):
        """ Send the next unsent email in the queue

        we only send one email at a time this allows us to raise errors
        for each email and avoid sending some crazy huge mass mail
        """

        email = self.fetch_next_pending_email()

        if email:
            self.send(email)
            return email.to_dict()
        else:
            return None


class LogEntry(IdModel):
    """Just an entity with a name and a text property. Intended to be an ulta-
    flexible log entry.

    This is a permanent and easily searchable log, as opposed to the native
    logging you access through the app engine control console, which only goes
    so far back in time and is full of less important stuff.
    """

    log_name = db.StringProperty()
    body = db.TextProperty()


class Pd(IdModel):
    program = db.StringProperty()
    activity_ordinal = db.IntegerProperty()
    scope = db.StringProperty()  # cohort, classroom, or user id
    scope_kind = db.StringProperty()  # 'cohort', 'classroom', or 'user'
    public = db.BooleanProperty(default=False)
    variable = db.StringProperty()
    value = db.TextProperty()  # must be text b/c string is limited to 500 char
    # The value of all of these should be strings, except for the parent,
    # which must be an entity.
    required_indexes = set(['program', 'scope', 'variable', 'value'])

    @property
    def cohort(self):
        raise Exception("The cohort property of pd entities has been deprecated.")

    @property
    def classroom(self):
        raise Exception("The classroom property of pd entities has been deprecated.")

    @property
    def activity(self):
        raise Exception("The activity property of pd entities has been deprecated.")

    @property
    def user(self):
        raise Exception("The user property of pd entities has been deprecated.")

    @classmethod
    def generate_id(klass, parent):
        """Because pds exist as descendants of other entities, a simple
        id-as-key-name is insufficient. We must store information about its
        ancestry as well. Example:
        Pd_8ZsiSLjxfXo4hOJ8ExKG.User_1mIX8gk0uhQxzuaeU6sD
        """
        simple_id = super(klass, klass).generate_id()
        return simple_id + '.' + parent.id

    @classmethod
    @db.transactional
    def create(klass, requesting_user, **kwargs):
        """Pd uses a custom create method because it must
        1) check if user is authorized to write to this program, cohort
        2) delete entries with the same indexes.
        """
        # Make sure we have all the data we need.
        if not set(kwargs).issuperset(klass.required_indexes):
            # If some are missing, calculate which ones for quicker debugging.
            raise Exception(
                "Required indexes are missing! {}".format(
                    klass.required_indexes.difference(set(kwargs))))

        # Check permissions. Researchers can write data if they own program,
        # everyone else if associated with the parent. This is so a spammer
        # could not mess up lots of data.
        requesting_user.can_put_pd(kwargs['program'], kwargs['scope'])

        # The 'value' may be passed as a non-string (e.g. json-interpreted
        # list in the case of program progress). Coerce it.
        if type(kwargs['value']) not in [str, unicode]:
            try:
                s = json.dumps(kwargs['value'])
            except:
                s = str(kwargs['value'])
            kwargs['value'] = s

        # The pd may need to be marked public, if it has been whitelisted.
        if kwargs['variable'] in config.pd_whitelist:
            kwargs['public'] = True

        # Pds are written to entity groups based on their scope id.
        # Most pds have a User entity as their parent. The parent entity must
        # be looked up.
        kwargs['scope_kind'] = core.get_kind(kwargs['scope'])
        parent_class = core.kind_to_class(kwargs['scope_kind'])
        parent = parent_class.get_by_id(kwargs['scope'])

        if parent is None:
            raise Exception("Cannot find scope (parent) entity for pd: {}"
                            .format(kwargs['scope']))

        # Instantiate, getting an id with the scope entity as an ancestor.
        id = klass.generate_id(parent)
        entity = klass(key_name=id, id=id, parent=parent, **kwargs)

        try:
            entity = Pd.delete_previous_versions(entity, parent)
        except Exception as e:
            logging.error(
                "Unable to delete previous pd. New pd: {}. Exception: {}."
                .format(entity, e))

        # Save the new entity.
        entity.put()

        return entity

    @classmethod
    def delete_previous_versions(klass, new_pd, parent):
        """Looks up older, similar pds and marks them deleted.

        The one exception is progress pds. New progress pds whose value is
        lower than previous ones are themselves marked deleted, and
        existing (higher) ones are left alone. This records a full history of
        the user's actions while preventing the visible progress value from
        descreasing.
        """
        overwrite_keywords = ['program', 'scope', 'variable']
        filters = [(k + ' =', getattr(new_pd, k)) for k in overwrite_keywords]
        query = Pd.all().filter('deleted =', False)
        for filter_tuple in filters:
            query.filter(*filter_tuple)
        # We use an ancestory query to guarantee strong consistency.
        # There should only be one non-deleted pd of a given variable name
        # in a given scope and program.
        query.ancestor(parent)
        if query.count() > 1:
            logging.error(
                "Duplicate progress pds. Program {}, scope {}, variable {}."
                .format(new_pd.program, new_pd.scope, new_pd.variable))

        # I know that 100 is arbitrary. But fetch() requires a number. I can
        # imagine a world crazy enough were there are 11 duplicate pds, but not
        # 101.
        existing_pd_list = query.fetch(100)
        # If the world is that crazy, raise an exception.
        if len(existing_pd_list) is 100:
            raise Exception(
                "WAY too many duplicate pds. Was trying to write {}."
                .format(new_pd.to_dict()))

        delete_existing = True

        if new_pd.is_progress() and len(existing_pd_list) > 0:
            existing_progress_values = [int(pd.value)
                                        for pd in existing_pd_list]
            if int(new_pd.value) < max(existing_progress_values):
                new_pd.deleted = True
                delete_existing = False

        if len(existing_pd_list) > 0 and delete_existing:
            for pd in existing_pd_list:
                pd.deleted = True
            db.put(existing_pd_list)

        return new_pd

    @classmethod
    def get_filters(self):
        return [('public =', True)]

    def is_progress(self):
        return bool(re.match(r's\d__progress', self.variable))


class Program(IdModel):
    name = db.StringProperty()
    abbreviation = db.StringProperty()

    # Loading programs (and other entities) through api.Api.get also tries to
    # the startup method, if it can be found. This is a convenient way to run
    # code when an entity is instantiated.
    # def startup(self):
    #     pass

    @classmethod
    def get_app_configuration(self, program_abbreviation, user_type=None):
        """Get a configuration dictionary for a subprogram."""
        # programs is a python module which has been imported containing
        # configuration for all the various program apps
        if hasattr(programs, program_abbreviation):
            app = getattr(programs, program_abbreviation)

            if user_type is None:
                return app.config

            # app is a program-specific python module (in this case, a
            # directory)
            # app.config is also a python module, in this case, a file named
            # config.py. We're returning a user_type-specific dictionary
            # defined in the file.
            var_name = '{}_config'.format(user_type)
            if hasattr(app.config, var_name):
                return getattr(app.config, var_name)
            else:
                return None
        else:
            raise Exception("No config data for program {}."
                            .format(program_abbreviation))

    @classmethod
    def get_activity_configuration(self, program_abbreviation, user_type, activity_ordinal):
        subprogram_config = Program.get_app_configuration(program_abbreviation,
                                                          user_type)
        activity_module = None
        for m in subprogram_config['outline']:
            if (m.get('type', None) == 'activity' and
                m['activity_ordinal'] == activity_ordinal):
                activity_module = m
        if activity_module is None:
            raise Exception('Config for activity not found.')

        return activity_module

    @classmethod
    def list_all(self):
        """Return a list of the current programs."""
        query = Program.all()
        query.filter('deleted =', False)
        query.filter('is_test', False)
        return query.fetch(100)

    def to_dict(self):
        """Overrides Model.to_dict() so that dynamically-retrieved info,
        can be included in the dictionary representation."""
        d = core.Model.to_dict(self)

        # If this entity has been loaded via a projection query (/api/see), it
        # may not have all its expected properties. Handle this gracefully.
        if self.abbreviation:
            program_config = Program.get_app_configuration(self.abbreviation)
            d['public_registration'] = getattr(
                program_config, 'public_registration', False)
        return d

    def get_reminders(self, user_type):
        """Get reminers from the program configuration file."""
        configuration = Program.get_app_configuration(
            self.abbreviation, user_type)

        reminders = []
        if configuration and 'reminder_emails' in configuration:
            reminders = configuration['reminder_emails']

        return reminders

    def activity_templates(self, user_type):
        """Get basic information about activities in the program app from
        its configuration file to serve as templates for activity entities."""
        logging.info('activity templates(usertype={})'.format(user_type))

        config = Program.get_app_configuration(
            self.abbreviation, user_type)
        templates = []
        for module in config['outline']:
            if 'type' in module and module['type'] == 'activity':
                templates.append(module)
        return templates


class Reminder(IdModel):
    """
    Email Reminders to teachers

    This class is responisble for composing new reminders based
    on reminders defined in programs.  It must add these emails
    to the queue and keep track of those reminders which have
    already been sent.
    """

    # Tracks which dates emails have already been sent on
    pst_date = db.StringProperty()

    @classmethod
    def get_pst_date( self, date_string = None, offset = 0 ):
        """Get date in PST, today's date by default."""
        date = \
            datetime.datetime.strptime( date_string, "%Y-%m-%d" ).date() \
            if date_string \
            else \
                (datetime.datetime.utcnow() + \
                datetime.timedelta(hours=-8)).date()
        offset = datetime.timedelta(days=offset)
        return date + offset

    @classmethod
    def render_reminder(self, reminder, user, activity, classroom):
        """Render subject, and body based on attributes of the user
        add addresses, to, from, and reply_to."""

        # rendering function
        # Passes in user, classroom, and activity; uses jinja to keep things
        # standardized.
        render = lambda s: jinja2.Environment().from_string(s).render(
            user=user,
            activity=activity,
            classroom=classroom,
        )

        # useful terms
        matching_status = reminder['send_if_activity'] == activity.status

        # render templates
        reminder['greeting'] = render(reminder['greeting'])
        reminder['body'] = render(reminder['body'])
        reminder['closing'] = render(reminder['closing'])
        reminder['subject'] = render(reminder['subject'])

        # address
        reminder['to_address'] = user.login_email
        reminder['reply_to'] = reminder['reply_to']
        reminder['from_address'] = reminder['from_address']

        # Schedule
        if activity.scheduled_date and matching_status:
            reminder['send_date'] = str(self.get_pst_date(
                date_string=activity.scheduled_date.isoformat(),
                offset=reminder['relative_date_to_send']
            ))

        # Debugging
        if not activity.scheduled_date:
            reminder['warning'] = 'Activity is unscheduled'

        return reminder

    @classmethod
    def render_reminders(self, program, user_type, user, activities):
        # load reminders
        reminders = program.get_reminders(user_type)

        # filter activities
        activities = [
            a for a in activities
            if a.assc_program_list[0] == program.id
            and a.user_type == user_type
        ]

        if len(activities) is 0:
            return []

        classroom_ids = [a.assc_classroom_list[0] for a in activities]
        classroom_dict = {c.id: c for c in Classroom.get_by_id(classroom_ids)}

        # render
        # note:
        #    using deepcopy otherwise pass by reference will lead to
        #    overwritting.
        reminders = [
            self.render_reminder(copy.deepcopy(r), user, a, classroom_dict[a.assc_classroom_list[0]])
            for a in activities
            for r in reminders
            if r['activity_ordinal'] == a.activity_ordinal
        ]

        return reminders

    @classmethod
    def preview_reminders(self, program, user_type, user, activities):
        """Render reminders, add environmental information to aid debugging."""
        emails = self.render_reminders(program, user_type, user, activities)
        return {
            'emails': emails,
            'environment': {
                'user': user.to_dict(),
                'activities': [a.to_dict() for a in activities],
            },
            'instructions': "Reminders are rendered from user and activity "
                            "objects"
        }

    @classmethod
    def to_string(self, reminder_dict):
        return \
            "subject: {}\n\n".format( reminder_dict['subject'] ) + \
            "{}\n\n\n\n".format( reminder_dict['body'] )

    @classmethod
    def merge_multiple_emails(self, emails):
        """Merge multiple emails into a single email.

        For example if a teacher has 3 emails scheduled today
        we should only send them one email."""

        n = len(emails)

        if n == 0:
            # If there are no messages
            return None

        prototype = emails[0]
        merged = {
            'to_address': prototype['to_address'],
            'from_address': prototype['from_address'],
            'send_date': prototype['send_date'],
            'send_if_activity': prototype['send_if_activity'],
            'relative_date_to_send': prototype['relative_date_to_send'],
            'reply_to': prototype['reply_to'],
            'subject': prototype['subject'],
            # no body here, on purpose
        }

        if n == 1:
            # If there is only one email, return as is.
            merged['body'] = (prototype['greeting'] + prototype['body'] +
                              prototype['closing'])

        elif n > 1:
            # Merge multiple messages, creating a bulleted list, e.g.
            # * Math 101 has their first session today
            # * Geography 101 has their first session today
            # Note the double line break, which allows markdown to interpet
            # the lines as a <ul> separate from any previous <p>.
            body_bullets = ''.join(['* {}\n'.format(e['body']) for e in emails])
            merged['body'] = (prototype['greeting'] + ":\n\n" + body_bullets +
                              prototype['closing'])
            merged['subject'] = ("You have {} reminders from PERTS.").format(n)

        return merged


class ResetPasswordToken(IdModel):
    """Acts as a one-time-pass for a user to reset their password.

    The "token" is just the id of a ResetPasswordToken entity.
    """

    user = db.StringProperty()  # id string

    def token(self):
        return self.id


class School(IdModel):
    name = db.StringProperty()
    timezone = db.StringProperty()
    grade_levels = db.StringProperty()
    city = db.StringProperty()
    state = db.StringProperty()
    country = db.StringProperty()
    district = db.StringProperty()
    inquiry_name = db.StringProperty()
    inquiry_phone = db.StringProperty()
    inquiry_notes = db.TextProperty()


class Stratifier(IdModel):
    """Keeps a history of how users with various attributes have been assigned
    conditions/groups.

    Group: 'experimental' or 'control' or 'cheesecake'
    Proportions: {group: proportion}, e.g. {'experimental': 2, 'control': 3}
    History: {group: # of assignments} e.g. {'experimental': 53, 'control': 52}
    Histories: {profile_id: history} see next, and util.hash_dict()
    User profile: {attribute name: value} e.g. {'race': 'white', 'age': 14}
    Profile id: a json-string-version of a user profile
    """

    # The following group of properties together serve as an index for stratifiers
    name = db.StringProperty()
    program = db.StringProperty()
    proportions_json = db.StringProperty()

    # in-memory cache of entities to avoid unecessary reads
    _history_entities = None

    @classmethod
    def create(klass, **kwargs):
        # Handle proportions in a special way because they are stored as an
        # indexible json string.
        p = kwargs['proportions']
        del kwargs['proportions']
        s = super(klass, klass).create(**kwargs)
        s.proportions(p)
        return s

    def proportions(self, new_proportions=None):
        """Setter/getter for Stratifier groups and intended proportions."""
        # N.B. The stratifier derives the potential group assignments from
        # whatever you set as keys in this proportions dictionary. If you
        # change the groups here, that will change where users are assigned.
        if new_proportions is not None:
            # sanity check
            for group, proportion in new_proportions.items():
                if type(proportion) is not int:
                    raise Exception("Bad proportion: {}.".format(proportion))
            self.proportions_json = util.hash_dict(new_proportions)
        return json.loads(self.proportions_json)

    def groups(self):
        return set(self.proportions().keys())

    def histories(self, profile_id=None):
        """Fetch histories and return a dictionary indexed by profile_id."""
        if self._history_entities is None:
            # fetch, if necessary
            q = StratifierHistory.all().filter('deleted =', False)
            q.filter('stratifier =', self.id)
            self._history_entities = {sh.profile_id: sh for sh in q.run()}
        if profile_id is not None:
            # get. someone asked for a specific history, give it to them
            return self._history_entities[profile_id]
        else:
            # get all. no arguments given, return everything
            return self._history_entities

    def insert_history(self, new_history):
        """Makes sure the history list is loaded and stores the new one."""
        self.histories()
        self._history_entities[new_history.profile_id] = new_history

    def stratify(self, user_profile):
        """Takes a dictionary of a users' targeted attributes and their values,
        returns a group name to which they've been assigned.

        Write frequency info: writes once to the history entity matching the
        user profile. Does not write to the Stratifier itself."""
        # look up the history
        profile_id = util.hash_dict(user_profile)
        if profile_id not in self.histories():
            # never-before-seen attributes and attribute values will just
            # result in a new profile_id and new history entity
            sh = StratifierHistory.create(self, profile_id)
            self.insert_history(sh)
        history = self.histories(profile_id=profile_id)
        # inform the history about a possible change in groups
        history.groups(new_groups=self.groups())
        # stratify
        candidate_groups = self.get_candidate_groups(history)
        assigned_group = random.choice(list(candidate_groups))
        # update
        history.assign(assigned_group)
        history.put()  # the write
        return assigned_group

    def get_candidate_groups(self, history):
        """Returns a set of groups which are valid for assignment based on
        a certain profile's history."""
        ideal_total = sum(self.proportions().values())
        # Return all groups if nothing has been assigned
        if history.total_assigned() is 0:
            return self.groups()
        # Find proportion assigned to each group
        current_ratios = {g: c / float(history.total_assigned())
                          for g, c in history.items()}
        ideal_ratios = {g: p / float(ideal_total)
                        for g, p in self.proportions().items()}
        # Add any group where the current assigned ratio is less than ideal
        underrepresented = set()
        # IMPORTANT: loop through the groups in the ideal ratios, not the
        # current history, because the two may disagree on what groups exist.
        for group, ideal_ratio in ideal_ratios.items():
            if ideal_ratio >= current_ratios[group]:
                underrepresented.add(group)
        return underrepresented


class StratifierHistory(IdModel):
    """Each user profile has its history stored in a separate entity to reduce
    the number of writes to a single entity required as students go through
    PERTS programs. It functions essentially as a dictionary of groups to
    assignment counts."""
    stratifier = db.StringProperty()
    profile_id = db.StringProperty()
    _history = util.DictionaryProperty()

    @classmethod
    def create(klass, stratifier, profile_id):
        history = {g: 0 for g in stratifier.groups()}
        return super(klass, klass).create(
            profile_id=profile_id, stratifier=stratifier.id, _history=history)

    def groups(self, new_groups=None):
        """Get, and possibly add new, groups."""
        if new_groups is not None:
            new_groups = new_groups - self.groups()  # set operations :-)
            if len(new_groups) > 0:
                # The groups have changed, create new entries in the history.
                # Old groups stick around, but the stratifier won't use them.
                for g in new_groups:
                    self._history[g] = 0
        return set(self._history.keys())

    def total_assigned(self):
        return sum(self._history.values())

    def items(self):
        return self._history.items()

    def assign(self, group):
        self._history[group] += 1


class User(IdModel):
    """Users have a user_type, representing many different roles. Users also
    do most of the work in storing relationships."""
    login_email = db.EmailProperty()
    first_name = db.StringProperty()
    last_name = db.StringProperty()
    middle_initial = db.StringProperty(default="")  # Always in upper case.
    stripped_first_name = db.StringProperty()
    stripped_last_name = db.StringProperty()
    name = db.StringProperty()
    birth_date = db.DateProperty()
    # id of the matching auth user, not the same as the PERTS user's id
    # it may be a google user's id (google.appengine.api.users),
    # it may also be the email they registered with directly.
    # it is prefixed with the TYPE of authentication this user logs in with
    # e.g. a typical google auth_id is 'google_51987249561530', while a typical
    # username/password auth_id is ''. Students do not
    # have auth_ids because they do not go through authentication.
    auth_id = db.StringProperty()
    # if the user used direct registration (username + password)
    hashed_password = db.StringProperty()
    # has user completed registration fields?
    registration_complete = db.BooleanProperty(default=False)
    # see config.allowed_user_types
    user_type = db.StringProperty(default='public')
    # allows distinction between school coordinators and school supervisors
    # potentially also storing info like "principal" or "superintendent"
    title = db.StringProperty()
    phone = db.StringProperty()
    # Arbitrary text researchers can store about users. Generally stores things
    # like when they were lasted contacted by a team member.
    notes = db.TextProperty()
    # For student users only.
    # Teachers must certify new students on the roster page for verification.
    certified = db.BooleanProperty(default=False)
    # For student users only. Reasons for non-participation. Marked by teacher
    # in roster. Keyed by session ordinal. Assumes there is only one program
    # per student.
    status_codes = util.DictionaryProperty()
    # One specific status code, "Merge: Wrong Name" i.e. "MWN" require that
    # administrators specify *which* other student this should be merged with.
    # Keyed by session ordinal.
    merge_ids = util.DictionaryProperty()
    # Stores most-recently-aggregated public pd. Used for dashboard reporting.
    # Has structure:
    # {
    #   1: {
    #     'progress': int
    #   },
    #   ...
    # }
    aggregation_data_template = {'progress': None}
    aggregation_data = util.DictionaryProperty()
    aggregation_json = util.JsonProperty()

    # Used by our deidentification mapreduce job to make the process idempotent
    deidentified = db.BooleanProperty(default=False)

    # relationships stored as lists of id strings
    assc_program_list = db.StringListProperty()
    owned_program_list = db.StringListProperty()  # researchers only
    assc_school_list = db.StringListProperty()
    assc_cohort_list = db.StringListProperty()
    owned_cohort_list = db.StringListProperty()  # school admins only
    assc_classroom_list = db.StringListProperty()
    owned_classroom_list = db.StringListProperty()  # teachers only
    owned_activity_list = db.StringListProperty()  # teachers
    assc_activity_list = db.StringListProperty()  # students
    owned_stratifier_list = db.StringListProperty()  # researchers

    @classmethod
    def create(klass, **kwargs):
        kw = kwargs
        # Everyone must have a user type, and it must be valid.
        if kw['user_type'] not in config.allowed_user_types:
            raise Exception("Invalid user_type: {}.".format(kw['user_type']))
        # Athenticated users (non-students) must have auth_ids, and non-google
        # users must have passwords. Take some care that they come in the right
        # form.
        # Also, because app engine is case sensitive, and we can't predict what
        # case users will use when entering their email, force username to
        # to lower case. See issue #208.
        if 'auth_id' in kw:
            kw['auth_id'] = str(kw['auth_id']).lower()  # no unicode allowed
        if 'login_email' in kw:
            kw['login_email'] = kw['login_email'].lower()
        if 'plaintext_password' in kw:
            kw['hashed_password'] = util.hash_password(kw['plaintext_password'])
            del kw['plaintext_password']   # make sure this isn't stored
        # We store simplified versions of student names separately to increase
        # our chances of matching them when they enter.
        if kw['user_type'] == 'student':
            if 'first_name' in kw:
                kw['stripped_first_name'] = util.clean_string(kw['first_name'])
            if 'last_name' in kw:
                kw['stripped_last_name'] = util.clean_string(kw['last_name'])
            kw['middle_initial'] = util.clean_string(
                kw.get('middle_initial', '')[:1]).upper()

        return super(klass, klass).create(**kw)

    def to_dict(self):
        """Overrides Model.to_dict() so that dynamically-retrieved info can be
        included in the dictionary representation."""
        self._clean_code_dictionaries()
        d = core.Model.to_dict(self)
        d['auth_type'] = self.auth_type()
        return d

    def get_status_code(self, activity_ordinal):
        """Returns participation status code for specified activity or None."""
        self._clean_code_dictionaries()
        return self.status_codes.get(activity_ordinal, None)

    def set_status_code(self, activity_ordinal, value):
        """Set participation status code for specified activity."""
        self._clean_code_dictionaries()
        if value not in config.status_codes:
            raise Exception("Invalid status code: {}.".format(value))
        self.status_codes[activity_ordinal] = value
        return value

    def _clean_code_dictionaries(self):
        """Translate between legacy string-keyed dictionaries and current
        integer-keyed dictionaries.

        @todo (chris): at the next program/user changeover, remove this code.
        """
        self.status_codes = {int(k): v for k, v in self.status_codes.items()}
        self.merge_ids = {int(k): v for k, v in self.merge_ids.items()}

    def auth_type(self):
        return self.auth_id.split('_')[0] if self.auth_id else None

    # ownership should be updated via associate, not update
    def validate_put(self,kwargs):
        owned = filter(lambda x:'owned' in x, kwargs.keys())
        associated = filter(lambda x:'assc' in x, kwargs.keys())
        if len(owned + associated):
            raise PermissionDenied("Assocations must be updated via associate or set owner")

        if ('login_email' in kwargs and
            self.login_email != kwargs['login_email'].lower()):
            # For direct users, email is mutable, but lives in two fields, and
            # so needs to be redundantly maintained. For other users, it is
            # immutable.
            if self.auth_type() == 'direct':
                # the new email can't be the same as any other email
                query = User.all().filter('login_email =', kwargs['login_email'])
                query.filter('deleted = ', False)
                if query.count() > 0:
                    raise PermissionDenied("Email already exists.")
                kwargs['auth_id'] = 'direct_' + kwargs['login_email']
            else:
                raise PermissionDenied("Google users cannot change their emails.")

        # For students we store cleaned-up versions of their names for easier
        # matching. If the name is updated, update cleaned version too.
        if 'first_name' in kwargs and self.user_type == 'student':
            kwargs['stripped_first_name'] = util.clean_string(kwargs['first_name'])
        if 'last_name' in kwargs and self.user_type == 'student':
            kwargs['stripped_last_name'] = util.clean_string(kwargs['last_name'])
        # Not only clean the middle initial to make sure it contains only
        # letters (not other weird characters), but also always save it in
        # upper case. If it's an empty string, save it as None.
        if 'middle_initial' in kwargs:
            kwargs['middle_initial'] = util.clean_string(
                kwargs['middle_initial'][:1]).upper()

        return kwargs

    def can_create(self, kind):
        """ Boolean: can this user create this type of object? """
        if self.user_type == "god":
            return True
        if kind in config.user_type_can_create[self.user_type]:
            return True
        return False

    #   this checks if can put user type in general
    #   while can put checks if a specific entity can be put
    def can_put_user_type(self, user_type):
        logging.info('User.can_put_user_type(user_type={})'.format(user_type))
        return user_type in config.can_put_user_type[self.user_type]

    def can_put_pd(self, program_id, scope_id):
        """Raises an exception if user can't put this pd.

        Scope is the id of the parent entity for this pd.
        """
        logging.info('User.can_put_pd(program_id={}, scope_id={})'
                     .format(program_id, scope_id))
        if self.user_type == 'god': pass
        elif self.user_type == 'researcher':
            if program_id not in self.owned_program_list:
                raise PermissionDenied("Researcher must own program to write pds.")
        else:
            kind = core.get_kind(scope_id)
            if kind == 'user' and self.id != scope_id:
                raise PermissionDenied("You must BE the user to write pd to the user.")
            elif (kind == 'classroom' and
                  scope_id not in self.assc_classroom_list and
                  scope_id not in self.owned_classroom_list):
                raise PermissionDenied("Must be in a classroom to write to it.")
            elif (kind == 'cohort' and
                  scope_id not in self.assc_cohort_list and
                  scope_id not in self.owned_cohort_list):
                raise PermissionDenied("Must be in cohort to write to it.")
        return True

    def get_permission_filters(self, kind, verb):
        """One of three functions that encode our permissions structure.
        * kind is a lowercase version of a class name, e.g. 'program'
        * verb describes type of access, e.g. 'see', 'get', or 'put'
        Returns a list of tuples which are used to filter queries, masking
        what people aren't allowed to see."""
        # WARNING: UNDERSTAND THE FOLLOWING BEFORE MODIFYING THIS FUNCTION
        # this function returns LIMITS on what people can see, so returning
        # an empty list is PERMISSIVE as it PLACES NO LIMIT on what can be seen

        logging.info('get_permission_filters(kind={}, verb={})'
                     .format(kind, verb))

        # God is omnipotent
        if self.user_type == 'god':
            return []

        if verb == 'see':
            if kind == 'program':
                if self.user_type == 'public':
                    raise PermissionDenied()
                elif self.user_type in ['student', 'teacher']:
                    #raise PermissionDenied()
                    # actually, it's pretty common for a user to want to look
                    # up just the name of a program (mostly to display it on
                    # the interface)
                    return [('id IN', self.assc_program_list)]
                elif self.user_type == 'school_admin':
                    return [('id IN', self.assc_program_list)]
                elif self.user_type == 'researcher':
                    return [('id IN', self.owned_program_list)]
            if kind == 'school':
                # you can see what you're associated with
                return [('id IN', self.assc_school_list)]
            if kind == 'cohort':
                # everyone is allowed to see cohorts
                return []
            if kind == 'classroom':
                # everyone is allowed to see classrooms
                return []
            if kind == 'activity':
                if self.user_type == 'school_admin':
                    # Can see things in their cohorts
                    return [('assc_cohort_list IN', self.owned_cohort_list)]
                if self.user_type == 'teacher':
                    # Can see activities they own
                    return [('id IN', self.owned_activity_list)]
            if kind == 'user':
                #   users can always access themselves
                user_ids = [self.id]
                #   there is no way to use OR statements in GQL
                #   http://stackoverflow.com/questions/930966/app-engine-datastore-does-not-support-operator-or
                if self.user_type == "researcher":
                    users = User.all().filter( "assc_program_list IN ", self.owned_program_list )
                    user_ids.extend([ u.id for u in users ])
                    users = User.all().filter( "owned_program_list IN ", self.owned_program_list )
                    user_ids.extend([ u.id for u in users ])
                    #   also show orphan (programless)

                if self.user_type == "school_admin":
                    users = User.all().filter( "assc_cohort_list IN ", self.owned_cohort_list )
                    user_ids.extend([ u.id for u in users ])
                    users = User.all().filter( "owned_cohort_list IN ", self.owned_cohort_list )
                    user_ids.extend([ u.id for u in users ])
                if self.user_type == "teacher":
                    users = User.all().filter( "assc_classroom_list IN ", self.owned_classroom_list )
                    user_ids.extend([ u.id for u in users ])
                    users = User.all().filter( "owned_classroom_list IN ", self.owned_classroom_list )
                    user_ids.extend([ u.id for u in users ])
                # you can see what you're associated with
                return [('id IN', user_ids)]
            if kind == 'stratifier':
                # no harm in letting people list stratifiers
                return []
        elif verb == 'get':
            if kind == 'program':
                visible = list(set(self.owned_program_list) |
                               set(self.assc_program_list))
                return [('id IN', visible)]
            if kind == 'school':
                if self.user_type in ['researcher', 'school_admin', 'teacher']:
                    return [('id IN', self.assc_school_list)]
            if kind == 'cohort':
                visible = list(set(self.owned_cohort_list) |
                               set(self.assc_cohort_list))
                return [('id IN', visible)]
            if kind == 'user':
                #   users can always access themselves
                user_ids = [self.id]
                #   there is no way to use OR statements in GQL
                #   http://stackoverflow.com/questions/930966/app-engine-datastore-does-not-support-operator-or
                if self.user_type == "researcher":
                    users = User.all().filter( "assc_program_list IN ", self.owned_program_list )
                    user_ids.extend([ u.id for u in users ])
                    users = User.all().filter( "owned_program_list IN ", self.owned_program_list )
                    user_ids.extend([ u.id for u in users ])
                    #   also show orphan (programless)

                if self.user_type == "school_admin":
                    users = User.all().filter( "assc_cohort_list IN ", self.owned_cohort_list )
                    user_ids.extend([ u.id for u in users ])
                    users = User.all().filter( "owned_cohort_list IN ", self.owned_cohort_list )
                    user_ids.extend([ u.id for u in users ])
                if self.user_type == "teacher":
                    users = User.all().filter( "assc_classroom_list IN ", self.owned_classroom_list )
                    user_ids.extend([ u.id for u in users ])
                    users = User.all().filter( "owned_classroom_list IN ", self.owned_classroom_list )
                    user_ids.extend([ u.id for u in users ])
                # you can see what you're associated with
                return [('id IN', user_ids)]

            if kind == 'classroom':
                if self.user_type == 'researcher':
                    return [('assc_program_list IN', self.owned_program_list)]
                elif self.user_type == 'school_admin':
                    return [('assc_cohort_list IN', self.owned_cohort_list)]
                elif self.user_type == 'teacher':
                    return [('id IN', self.owned_classroom_list)]
                elif self.user_type == 'student':
                    return [('id IN', self.assc_classroom_list)]
            if kind == 'activity':
                if self.user_type == 'student':
                    # students must share a classroom with activities in order
                    # to get them.
                    return [('assc_classroom_list IN', self.assc_classroom_list)]
                elif self.user_type == 'teacher':
                    visible = list(set(self.owned_activity_list) |
                                   set(self.assc_activity_list))
                    return [('id IN', visible)]
                elif self.user_type == 'school_admin':
                    visible_cohorts= list(set(self.owned_cohort_list) |
                                            set(self.assc_cohort_list))
                    return [('assc_cohort_list IN', visible_cohorts)]
                elif self.user_type == 'researcher':
                    visible_programs = list(set(self.owned_program_list) |
                                            set(self.assc_program_list))
                    return [('assc_program_list IN', visible_programs)]
            if kind == 'pd':
                #   all see whitelisted pd for associated programs
                #   other pd pulled via custom, secure process
                filters = Pd.get_filters()
                visible_programs = list(set(self.assc_program_list) |
                                        set(self.owned_program_list))
                program_filter = ('program IN', visible_programs)
                filters.append(program_filter)
                return filters
            if kind == 'stratifier':
                return [('id IN', self.owned_stratifier_list)]
            if kind == 'stratifier_history':
                # you can get a history if you own the corresponding
                # stratifier
                return [('stratifier IN', self.owned_stratifier_list)]
            if kind == 'log_entry':
                # Only gods can view log entries b/c they potentially contain
                # sensitive information.
                raise PermissionDenied(
                    "You do not have permission to view log entries.")

        raise PermissionDenied("Permission filters not written yet for {}.".format(kind))

    def can_associate(self, action, from_entity, to_entity):
        """One of three functions that encode our permissions structure.
        * action is 'associate' or 'set_owner'
        Returns a boolean defining whether or not you are allowed to make a
        given association."""
        # todo: this function is currently only considering the thing
        # associated TO, which often isn't the entity that's actually
        # changed... and really there three players in this game:
        # - the user making the request (that's what self is here)
        # - the from_entity, often the one carrying the association list, and
        #   may be the same as self
        # - the to_entity
        # this whole thing needs to be reconceptualized to consider ALL THREE
        # players (when necessary)
        # todo: this method has queries in it! ick! Also, these queries
        # aren't filtering out deleted users, which will bite us eventually.

        # If you can associate, you can unassociate. If you can set owner, you
        # can disown.
        if action == 'unassociate':
            action = 'associate'
        if action == 'disown':
            action = 'set_owner'

        if self.user_type == 'god':
            return True
        from_kind = core.get_kind(from_entity)
        to_kind = core.get_kind(to_entity)
        if to_kind == 'user':
            # Classrooms are associated to their teachers during creation.
            if action == 'associate' and from_kind == 'classroom':
                if len(from_entity.assc_user_list) is 0:
                    return True
        elif to_kind == 'program':
            if action == 'set_owner' and from_kind == 'user':
                # special case: if we can't find any users who own you already,
                # then the next person gets dibs
                owner_q = User.all().filter('owned_program_list =', to_entity.id)
                if owner_q.count() is 0:
                    return True
            if action == 'associate' and from_kind == 'user':
                return True
            if action == 'associate' and from_kind == 'activity':
                if self.user_type in ['teacher', 'school_admin']:
                    # teachers and school admins can associate activities they
                    # own to programs they are already associated to.
                    return (from_entity.id in self.owned_activity_list and
                            to_entity.id in self.assc_program_list)
            if action == 'associate' and from_kind == 'classroom':
                if self.user_type in ['teacher','school_admin']:
                    # teachers can associate classrooms they own to programs
                    # they are already associated to.
                    return (from_entity.id in self.owned_classroom_list and
                            to_entity.id in self.assc_program_list)
            # normal case: you're allowed to make associations to this thing
            # only if you own this thing
            return to_entity.id in self.owned_program_list
        elif to_kind == 'activity':
            if action == 'set_owner' and from_kind == 'user':
                # if you own these activities and you want to share them with
                # someone, that's fine
                if to_entity.id in self.owned_activity_list:
                    return True
                else:
                    # special case: if we can't find any users who own you already,
                    # then the next person gets dibs
                    owner_q = User.all().filter('owned_activity_list =', to_entity.id)
                    if owner_q.count() is 0:
                        return True
        elif to_kind == 'cohort':
            if action == 'set_owner' and from_kind == 'user':
                # special case: if we can't find any users who own you already,
                # then the next person gets dibs
                owner_q = User.all().filter('owned_cohort_list =', to_entity.id)
                if owner_q.count() is 0:
                    return True
            elif action == 'associate' and from_kind == 'user':
                # we need to let people enter new cohorts
                return True
            elif action == 'associate' and from_kind == 'classroom':
                # you're allowed to do this if you're associated with the
                # cohort
                if to_entity.id in self.assc_cohort_list:
                    return True
            elif action == 'associate' and from_kind == 'activity':
                if self.user_type == 'teacher' or self.user_type == 'student':
                    # teachers can associate activities they own
                    # to cohorts they are already associated to.
                    return (from_entity.id in self.owned_activity_list and
                            to_entity.id in self.assc_cohort_list)
            # normal case: you're allowed to make associations to this thing
            # only if you own this thing
            return to_entity.id in self.owned_cohort_list
        elif to_kind == 'classroom':
            if action == 'associate' and from_kind == 'user':
                # students can be freely associated with classrooms, even by
                # the public user, which is an  important part of identification
                if from_entity.user_type == 'student':
                    return True
            elif action == 'associate' and from_kind == 'activity':
                # special case where student created an activity
                # because it was not already instantiated via scheduling
                # and now needs to associate it to their classroom
                logging.info('Associating activity and classroom')
                logging.info(
                    'User owns activity {}'
                    .format(from_entity.id in self.owned_activity_list))
                logging.info(
                    'User owns classroom {}'
                    .format( to_entity.id in self.assc_classroom_list))
                if from_entity.id in self.owned_activity_list and to_entity.id in self.assc_classroom_list:
                    return True

            elif action == 'set_owner':
                # special case: if we can't find any users who own you already,
                # then the next person gets dibs
                owner_q = User.all().filter(
                    'owned_classroom_list =', to_entity.id)
                if owner_q.count() is 0:
                    return True
            # normal case: you're allowed to make associations to this thing
            # if you own this thing
            return to_entity.id in self.owned_classroom_list
        elif to_kind == 'school':
            if action == 'associate':
                if from_kind in ['classroom', 'cohort']:
                    # you can associate something to a school if you own that
                    # something
                    attr = 'owned_{}_list'.format(from_kind)
                    return from_entity.id in getattr(self, attr)
                if from_kind == 'user':
                    # you can associate yourself to a school
                    if from_entity == self:
                        return True
                    # researchers can associate teachers, school_admins, and
                    # students to schools if the researcher is associated with
                    # the school
                    if (self.user_type == 'researcher' and
                        from_entity.user_type in ['teacher', 'school_admin', 'student']):
                        return to_entity.id in self.assc_school_list
                    # school_admins can associate teachers and students to
                    # schools if they are associated with the school
                    if (self.user_type == 'school_admin' and
                        from_entity.user_type in ['teacher', 'student']):
                        return to_entity.id in self.assc_school_list
                    # otherwise, (for newly created users) your first choice of
                    # school is free
                    if (from_entity.user_type == 'student' and
                        len(from_entity.assc_school_list) is 0):
                        return True
        elif to_kind == 'stratifier':
            if action == 'set_owner':
                # special case: if we can't find any users who own you already,
                # then the next person gets dibs
                owner_q = User.all().filter(
                    'owned_stratifier_list =', to_entity.id)
                if owner_q.count() is 0:
                    return True
        raise Exception("Association rules not written yet. {}, {}, {}".format(action, from_entity, to_entity))

    def has_permission(self, action=None, entity=None):
        """One of three functions that encode our permissions structure.
        * action is 'put', 'delete', or 'archive'
        Returns a boolean defining whether or not you can perform the given
        action on the given entity."""

        logging.info('has_permission(action={}, entity={})'
                     .format(action, entity))

        kind = core.get_kind(entity) if entity else None
        if self.user_type == 'god':
            return True
        if action in ['delete', 'archive']:
            kind_allowed = kind in config.user_type_can_delete[self.user_type]
            if isinstance(entity, School):
                return False  # gods only
            elif self.user_type == 'researcher' and kind_allowed:
                # researchers can delete things that are in their program(s)
                # and ONLY in their program(s)
                if kind == 'program':
                    return entity.id in self.owned_program_list
                else:
                    return all([(id in self.owned_program_list)
                                for id in entity.assc_program_list])
            elif self.user_type == 'school_admin' and kind_allowed:
                # school_admins can delete things that are in their cohort(s)
                # and ONLY in their cohort(s)
                if kind == 'cohort':
                    return entity.id in self.owned_cohort_list
                else:
                    return all([(id in self.owned_cohort_list)
                                for id in entity.assc_cohort_list])
            elif self.user_type == 'teacher' and kind_allowed:
                # teachers can delete things that are in their classroom(s)
                # and ONLY in their classroom(s)
                if kind == 'classroom':
                    return entity.id in self.owned_classroom_list
                else:
                    return all([(id in self.owned_classroom_list)
                                for id in entity.assc_classroom_list])
        elif action == 'put':
            if kind == 'user':
                # you can update yourself
                if entity == self:
                    return True
                elif self.user_type == 'researcher':
                    # researchers can update any user in their programs
                    in_common = set(self.owned_program_list).intersection(
                        set(entity.assc_program_list))
                    return len(in_common) > 0
                elif self.user_type == 'school_admin':
                    # school admins can update any user in their cohorts
                    in_common = set(self.owned_cohort_list).intersection(
                        set(entity.assc_cohort_list))
                    return len(in_common) > 0
            elif kind == 'pd':
                # special permission function
                return self.can_put_pd(entity.program, entity.scope)
            elif kind == 'activity':
                # researchers can put any activity
                if self.user_type == 'researcher':
                    return True
                # school admins can put activities within cohorts they own
                if self.user_type == 'school_admin':
                    p = entity.assc_cohort_list[0]
                    return p in self.owned_cohort_list
                # or you can update what you own.
                return entity.id in self.owned_activity_list
            elif kind == 'classroom':
                if self.user_type == 'school_admin':
                    # school admins can put classrooms within cohorts they own
                    if self.user_type == 'school_admin':
                        p = entity.assc_cohort_list[0]
                        return p in self.owned_cohort_list
            elif kind == 'school':
                if self.user_type in ['researcher', 'school_admin']:
                    # Technically this makes it possible for school admins
                    # to write to schools they aren't associated with, but
                    # I don't think it's worth the effort to single out that
                    # case. CAM 2015-02-17.
                    return True
            else:
                # or you can update what you own.
                attr = 'owned_{}_list'.format(core.get_kind(entity))
                return entity.id in getattr(self, attr)
        raise Exception("User.has_permission() rules not written yet.")

    def can_impersonate(self, target):
        logging.info('can_impersonate(target={})'.format(target.id))

        if self.user_type == 'god':
            return True
        if self.user_type == 'public':
            return False
        # Users can impersonate user types below them.
        user_type_ok = (config.allowed_user_types.index(self.user_type) >
                        config.allowed_user_types.index(target.user_type))
        # They cannot impersonate someone associated with a program they are
        # NOT associated with. This prevents improper access through
        # impersonation.
        valid_programs = set(self.owned_program_list) | set(self.assc_program_list)
        target_programs = set(target.owned_program_list) | set(target.assc_program_list)
        # If ALL of the target's programs are associated with the
        # user then forbidden_programs should be the empty set.
        forbidden_programs = target_programs - valid_programs
        return user_type_ok and len(forbidden_programs) is 0
