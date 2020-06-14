"""Map reduce job definitions."""

import datetime
import hashlib
import mapreduce

import id_model


class FakeSliceContext(object):
    """Imitates mapreduce.api.map_job.map_job_context.SliceContext just enough
    to run simple previews of a mapper."""
    def __init__(self, job_context):
        self.job_context = job_context


def get_fake_context(job_config):
    """Gives a context sufficient to run a preview of mapper functionality."""
    job_context = mapreduce.api.map_job.map_job_context.JobContext(job_config)
    return FakeSliceContext(job_context)


class DeidentifyMapper(mapreduce.api.map_job.mapper.Mapper):
    def __call__(self, context, user):
        """Hashes identifying data on users with certain relationships.

        The point is to permanently obscure data that could potentially
        identify participants, but still allow users to be linked across
        systems, so a salted hash is called for.

        Args:
            context: map_job_context.JobContext, contains (among other things),
                parameters provided to the input reader (the thing responsible
                for serving up datastore entities one by one to the mapper).
            user: id_model.User, the user to (possibly) be modified.
        """
        # Separation from db operation allows unit testing.
        user = self.do(context, user)
        # Yielding an operation, rather the saving to the db here, allows
        # the map reduce framework to batch them all together efficiently.
        yield mapreduce.operation.db.Put(user)

    def hash(self, subject, salt):
        if subject is None:
            subject = u''
        if type(subject) is not unicode or type(salt) is not unicode:
            raise Exception("Non-unicode string given.")
        subject += salt
        return hashlib.sha1(subject.encode('utf-8')).hexdigest()

    def do(self, context, user):
        """Test if user matches params, then hash sensitive properties."""
        # These params defined in the job config in deidentify().
        params = context.job_context.job_config.input_reader_params

        # The params contain the name of a relationship list attribute, and
        # values that may be found in the list. Here we grab the user's
        # relationship list.
        rltn_list = getattr(user, params['list_name'])

        # App Engine stores string lists as unicode, so make sure to coerce
        # the param to match. The hash function also expects unicode.
        list_values = [unicode(v) for v in params['list_values']]
        salt = unicode(params['salt'])

        # If we find any of the specified values in the users list of
        # relationships, this user has one of the specified relationships.
        shared_ids = set(rltn_list).intersection(set(list_values))
        has_relationship = len(shared_ids) > 0

        if (has_relationship and user.user_type == 'student' and
            not user.deidentified):
            # We want to hash names rather than erase them because
            # we want to be able to link these users to other, similarly hashed
            # data in other places.
            # Example:
            #     Last name: 'Cheadle'
            #     Salt: 'abcxyz'
            #     Full string to be hashed by sha-1: 'Cheadleabcxyz'
            # Note that it's safe to operate on these even if they're blank
            # (like middle_initial) b/c they're always at least empty strings.
            user.first_name = self.hash(user.first_name, salt)
            user.last_name = self.hash(user.last_name, salt)
            # Rather than cram a long hash into a field that's supposed to be
            # one character, we're just erasing it for now. That's sufficient
            # for the current use, ER14F, but may need to be changed in the
            # future.
            user.middle_initial = ''

            # We decided that dropping the day of the month sufficiently
            # de-identifies users, while keeping the ability to calcuate their
            # approximate age.
            if user.birth_date is not None:
                user.birth_date = datetime.date(
                    user.birth_date.year, user.birth_date.month, 1)

            # These properties are not of interest. Erase them to be on the
            # safe side.
            user.stripped_first_name = ''
            user.stripped_last_name = ''
            user.name = ''
            user.auth_id = ''
            user.login_email = None
            user.title = ''
            user.phone = ''
            user.notes = ''

            # Flag this user has having been deidentified, so we don't hash
            # the same data twice. Important for idempotence.
            user.deidentified = True

        return user


def deidentify(list_name, list_values, salt, submit_job=True):
    """Launch a map reduce job to deidentify users.

    Args:
        list_name: str, the relationship list, e.g. 'assc_cohort_list'
        value: str, the entity id to be found in the list, e.g. 'Cohort_XYZ'
        submit_job: bool, default True, if False does not launch job, only
            returns the configuration for the potential job.
    """
    job_config = mapreduce.api.map_job.JobConfig(
        job_name='deidentify',
        mapper=DeidentifyMapper,
        input_reader_cls=mapreduce.input_readers.DatastoreInputReader,
        input_reader_params={
            'entity_kind': 'id_model.User',
            'list_name': list_name,
            'list_values': list_values,
            'salt': salt,
        },
        queue_name='systematic-update')

    if submit_job:
        mapreduce.api.map_job.Job.submit(job_config)

    return job_config


# If this class structure (with the __call__) looks funny to you, read on:
# It's just a function-generator. When you instantiate the class, you get a
# callable object, which you can treat just like a function.
# Example:
# f = LowerCaseLoginMapper()
# f(context, entity)  # yields a db operation

# For unit testing, you can call the do method and get the changed entity,
# rather than an operation.
# Example:
# f = LowerCaseLoginMapper()
# changed_entity = f.do(context, original_entity)

class LowerCaseLoginMapper(mapreduce.api.map_job.mapper.Mapper):
    def __call__(self, context, user):
        """Changes users login-related properties so they are in lower case.

        Important b/c app engine is case sensitive, and this will allow us to
        sanitize user input and still find the matching user.

        Must be idempotent!

        Args:
            context: map_job_context.JobContext, contains (among other things),
                parameters provided to the input reader.
            user: id_model.User, the user who needs their logins fixed.
        """
        user = self.do(context, user)
        # Yielding an operation, rather the saving to the db here, allows
        # the map reduce framework to batch them all together efficiently.
        yield mapreduce.operation.db.Put(user)

    def do(self, context, user):
        """Separation from db operation allows unit testing."""
        if user.auth_id:
            user.auth_id = user.auth_id.lower()
        if user.login_email:
            user.login_email = user.login_email.lower()
        return user


class CertifyStudentsMapper(mapreduce.api.map_job.mapper.Mapper):
    def __call__(self, context, user):
        """Makes all students certified.

        Must be idempotent!

        Args:
            context: map_job_context.JobContext, contains (among other things),
                parameters provided to the input reader.
            user: id_model.User, the user who may need to be certified.
        """
        user = self.do(context, user)
        # Yielding an operation, rather the saving to the db here, allows
        # the map reduce framework to batch them all together efficiently.
        yield mapreduce.operation.db.Put(user)

    def do(self, context, user):
        """Separation from db operation allows unit testing."""
        if user.user_type == 'student':
            user.certified = True
        return user


class AggregationJsonMapper(mapreduce.api.map_job.mapper.Mapper):
    def __call__(self, context, entity):
        """Make the aggregation_json property match aggregation_data.

        Written for one-time use, upon introduction of the aggregation_json
        property, to take care of legacy data.

        Must be idempotent!

        Args:
            context: map_job_context.JobContext, contains (among other things),
                parameters provided to the input reader.
            entity: core.User, core.Activity, or core.Cohort which needs their
                data fixed.
        """
        entity = self.do(context, entity)
        # Yielding an operation, rather the saving to the db here, allows
        # the map reduce framework to batch them all together efficiently.
        yield mapreduce.operation.db.Put(entity)

    def do(self, context, entity):
        """Separation from db operation allows unit testing."""
        entity.aggregation_json = entity.aggregation_data
        return entity


def modify_kind(kind, mapper, submit_job=True):
    """Generic map reduce launcher. Start a job on a kind with a mapper.

    Args:
        kind: str, PERTS-style kind string, e.g. 'user' or 'classroom'.
        mapper: mapreduce.api.map_job.mapper.Mapper with do() method, defines
            an update operation on each entity of the kind.
        submit_job: bool, default True, if False does not launch job, only
            returns the configuration for the potential job.
    """
    kind_map = {
        'user': 'id_model.User',
        'activity': 'id_model.Activity',
        'cohort': 'id_model.Cohort',
    }
    job_config = mapreduce.api.map_job.JobConfig(
        # How the job will be listed on the control panel at /mapreduce.
        job_name='modify_' + kind,
        # The "function" that will process each entity.
        mapper=mapper,
        # The way data will be read into the mapper. This one just iterates
        # over every entity of a given kind, providing the entity to the
        # mapper.
        input_reader_cls=mapreduce.input_readers.DatastoreInputReader,
        input_reader_params={'entity_kind': kind_map[kind]},
        # There are no output writers or reduce steps since this job is so
        # simple.
        # The only thing left is to point to the config for the task queue this
        # job will use.
        queue_name='systematic-update')

    if submit_job:
        mapreduce.api.map_job.Job.submit(job_config)

    return job_config


class ModifyPdMapper(mapreduce.api.map_job.mapper.Mapper):
    def __call__(self, context, pd):
        """Modifies pd entities according to specifications.

        Used to re-associated pds when moving users. For example, if moving a
        student to a new classroom, their pds will need their classroom
        property altered.

        Must be idempotent!

        Args:
            context: map_job_context.JobContext, contains (among other things),
                parameters provided to the input reader (the thing responsible
                for serving up datastore entities one by one to the mapper).
            pd: id_model.Pd, the pd which needs to be modified.
        """
        # Separation from db operation allows unit testing.
        pd = self.do(context, pd)
        # Yielding an operation, rather the saving to the db here, allows
        # the map reduce framework to batch them all together efficiently.
        yield mapreduce.operation.db.Put(pd)

    def do(self, context, pd):
        """Test if pd matches params, then modify specified properties."""
        matches = True
        # These params defined in the job config in modify_pd().
        params = context.job_context.job_config.input_reader_params

        # We want to allow two kinds of matching params: primitives and lists
        # of primitives. If a primitive, the pd's property must match it
        # exactly. If a list, the pd's property must be in the list. This
        # allows expressions like, "all the pds in this program and from one of
        # these several users," which would be represented by
        # {'program': 'Program_XYZ', 'user': ['User_ABC', 'User_DEF']}
        for k, v in params['to_match'].items():
            if type(v) in [str, unicode, int, bool]:
                if getattr(pd, k) != v:
                    matches = False
            elif type(v) is list:
                if getattr(pd, k) not in v:
                    matches = False
            else:
                raise Exception("Invalid to_match type: {}".format({k: v}))

        if matches:
            for k, v in params['to_change'].items():
                setattr(pd, k, v)

        return pd


def modify_pd(to_match, to_change, submit_job=True):
    """Launch a map reduce job to modify pd entities.

    Args:
        submit_job: bool, default True, if False does not launch job, only
            returns the configuration for the potential job.
    """
    job_config = mapreduce.api.map_job.JobConfig(
        job_name='modify_pd',
        mapper=ModifyPdMapper,
        input_reader_cls=mapreduce.input_readers.DatastoreInputReader,
        input_reader_params={
            'entity_kind': 'id_model.Pd',
            'to_match': to_match,
            'to_change': to_change,
        },
        queue_name='systematic-update')

    if submit_job:
        mapreduce.api.map_job.Job.submit(job_config)

    return job_config
