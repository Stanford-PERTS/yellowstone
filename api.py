"""API Layer

All code considered outside the core platform (like URLs, program apps, etc.)
must interact with the platform via these function calls. All interaction with
the Datastore also happens through these functions. This is where permissions
are enforced. Expect calls to raise exceptions if things go wrong.
"""


from google.appengine.ext import db
import cloudstorage as gcs
import csv
import datetime  # for checking reset password tokens
import google.appengine.api.app_identity as app_identity  # import links
import logging
import markdown

from core import PermissionDenied
from cron import Cron
from id_model import (Activity, LogEntry, Pd, Program, Reminder,
                      ResetPasswordToken, Stratifier, StratifierHistory, User,
                      IdError, IdModel)
from named_model import Indexer, QualtricsLink
import config
import core
import util


class Api:
    """The set of functions through which the outside world interacts with
    pegasus.

    Designed to be instantiated in the context of a user. Who the user is
    and what relationships they have determine how permissions are enforced.
    """

    def __init__(self, user):
        """Create an interface to pegasus.

        Args:
            user: core.User, who is making the api request
        """
        self.user = user

    @classmethod
    def post_process(klass, results, unsafe_filters):
        """Assumes IN filters with list values, e.g. ('id IN', ['X', 'Y'])."""
        logging.info('Api.post_process() handled unsafe filters:')
        logging.info('{}'.format(unsafe_filters))
        all_matching_sets = []
        for filter_tuple in unsafe_filters:
            p = filter_tuple[0].split(' ')[0]
            values = filter_tuple[1]
            matches = set([e for e in results if getattr(e, p) in values])
            all_matching_sets.append(matches)
        return set.intersection(*all_matching_sets)

    @classmethod
    def limit_subqueries(klass, filters):
        # GAE limits us to 30 subqueries! This is a BIG problem, because
        # stacking 'property IN list' filters MULTIPLIES the number of
        # subqueries (since IN is shorthand for a bunch of = comparisions). My
        # temporary solution is to detect unwieldy queries and do some post-
        # processing in python.
        # https://groups.google.com/forum/#!topic/google-appengine-python/ZlqZHwfznbQ
        subqueries = 1
        safe_filters = []
        unsafe_filters = []
        in_filters = []
        for filter_tuple in filters:
            if filter_tuple[0][-2:] == 'IN':
                subqueries *= len(filter_tuple[1])
                in_filters.append(filter_tuple)
            else:
                safe_filters.append(filter_tuple)
        if subqueries > 30:
            # mark in_filters as unsafe one by one, starting with the largest,
            # until subqueries is small enough
            s = subqueries
            for f in sorted(in_filters, key=lambda f: len(f[1]), reverse=True):
                if s < 30:
                    safe_filters.append(f)
                else:
                    unsafe_filters.append(f)
                s /= len(f[1])
        else:
            safe_filters += in_filters
        if len(unsafe_filters) > 0:
            logging.info('Api.limit_subqueries() marked filters as unsafe '
                         'because they would generate too many subqueries:')
            logging.info('{}'.format(unsafe_filters))
        return (safe_filters, unsafe_filters)

    def associate(self, action, from_entity, to_entity, put=True):
        logging.info('Api.associate(action={}, from_entity={}, to_entity={}, put={})'.format(action, from_entity.id, to_entity.id, put) )

        # create the requested association
        from_kind = core.get_kind(from_entity)
        to_kind = core.get_kind(to_entity)
        if not self.user.can_associate(action, from_entity, to_entity):
            raise PermissionDenied("association failure!")
        if action == 'set_owner':
            property_name = 'owned_' + to_kind + '_list'
        elif action == 'associate':
            property_name = 'assc_' + to_kind + '_list'
        relationship_list = getattr(from_entity, property_name)
        if to_entity.id not in relationship_list:
            relationship_list.append(to_entity.id)
        setattr(from_entity, property_name, relationship_list)

        # recurse through cascading relationships

        start_cascade = (action in ['associate', 'set_owner']
                         and from_kind == 'user'
                         and to_kind in config.user_association_cascade)
        if start_cascade:
            for k in config.user_association_cascade[to_kind]:
                # figure out the target entity
                attr = 'assc_{}_list'.format(k)
                # target_id = getattr(to_entity, attr)[0]
                target_list = getattr(to_entity, attr)
                if len(target_list) > 0:
                    target_id = target_list[0]
                    target_entity = core.Model.get_from_path(k, target_id)
                    # only associate if the user isn't ALREADY associated
                    if target_id not in getattr(from_entity, attr):
                        from_entity = self.associate(
                            'associate', from_entity, target_entity, put=False)
                # else: we can't cascade because this entity's associations
                # aren't complete. This happens when they are first created,
                # and we don't have to worry about it.

        if not put:
            # avoid multiple db.puts when creating entities
            return from_entity
        else:
            from_entity.put()

        return from_entity

    @db.transactional
    def batch_put_pd(self, params):
        """Put many pds to a single entity group within a transaction.

        See api_handlers.BatchPutPdHandler for structure of params.
        """
        pds = []
        # Go through the pd_batch to create a pd entity for each one
        for pd_info in params['pd_batch']:
            # Copy the other properties, which all apply to each pd
            pd_params = params.copy()
            del pd_params['pd_batch']
            # Mix the variable and value properties of this pd into the params
            pd_params.update(pd_info)
            pds.append(self.create('pd', pd_params))
        return pds

    def batch_put_user(self, params):
        """Put many users.

        See api_handlers.BatchPutUserHandler for structure of params.
        """
        users = []

        # If you look at api_handlers.BatchPutUserHandler you can see the
        # structure of the params dictionary. It's got all the normal
        # parameters to create a user, but instead of the user's first name
        # and last name, it has a list of such names, representing many users
        # to create.
        # Remove the list to convert the batch parameters to creation
        # parameters for a single user (which are now missing name arguments,
        # obviously). We'll fill in names one by one as we create users.
        user_names = params['user_names']  # dicts w/ 'first_name', 'last_name'
        del params['user_names']

        # Make one user through the normal api as a template, which will raise
        # any relevant configuration or permissions exceptions. After this
        # single create() call, we'll skip all that fancy logic in favor of
        # speed.
        template_user_params = params.copy()
        template_user_params.update(user_names.pop())
        template_user = self.create('user', template_user_params)

        # Make all the other users in memory, copying relationships from the
        # template. First we'll need to determine which are the relationship-
        # containing properties.
        relationship_property_names = [p for p in dir(User)
                                       if p.split('_')[0] in ['assc', 'owned']]
        for user_info in user_names:
            loop_params = params.copy()
            loop_params.update(user_info)
            loop_user = User.create(**loop_params)  # doesn't put()
            for prop in dir(loop_user):
                if prop in relationship_property_names:
                    template_value = getattr(template_user, prop)
                    setattr(loop_user, prop, template_value)
            users.append(loop_user)

        # Save all the users in a single db operation.
        db.put(users)

        # Put the template user in the list so they're all there.
        users.append(template_user)

        return users

    def check_reset_password_token(self, token_string):
        """Validate a token supplied by a user.

        Returns the matching user entity if the token is valid.
        Return None if the token doesn't exist or has expired.

        """
        token_entity = ResetPasswordToken.get_by_id(token_string)

        if token_entity is None:
            # This token doesn't exist. The provided token string is invalid.
            return None

        # Check that it hasn't expired and isn't deleted
        one_hour = datetime.timedelta(hours=1)
        expired = datetime.datetime.now() - token_entity.created > one_hour
        if expired or token_entity.deleted:
            # Token is invalid.
            return None

        return User.get_by_id(token_entity.user)

    def clear_reset_password_tokens(self, user_id):
        """Delete all tokens for a given user."""
        q = ResetPasswordToken.all()
        q.filter('deleted =', False)
        q.filter('user =', user_id)
        tokens = q.fetch(100)
        for t in tokens:
            t.deleted = True
        db.put(tokens)

    def create(self, kind, kwargs):
        logging.info('Api.create(kind={}, kwargs={})'.format(kind, kwargs))
        logging.info("Api.create is in transction: {}"
                     .format(db.is_in_transaction()))

        # check permissions

        # can this user create this type of object?
        if not self.user.can_create(kind):
            raise PermissionDenied("User type {} cannot create {}".format(
                self.user.user_type, kind))
        # if creating a user, can this user create this TYPE of user
        if kind == 'user':
            if not self.user.can_put_user_type(kwargs['user_type']):
                raise PermissionDenied(
                    "{} cannot create users of type {}."
                    .format(self.user.user_type, kwargs['user_type']))

        # create the object

        klass = core.kind_to_class(kind)
        # some updates require additional validity checks
        if kind in config.custom_create:
            # These put and associate themselves; the user is sent in so custom
            # code can check permissions.
            entity = klass.create(self.user, **kwargs)
            return entity
        else:
            # non-custom creates require more work
            entity = klass.create(**kwargs)

        if kind in config.kinds_requiring_put_validation:
            entity.validate_put(kwargs)

        # create initial relationships with the creating user

        action = config.creator_relationships.get(kind, None)
        if action is not None:
            if self.user.user_type == 'public':
                raise Exception(
                    "We should never be associating with the public user.")
            # associate, but don't put the created entity yet, there's more
            # work to do
            self.user = self.associate(action, self.user, entity, put=False)
            self.user.put()  # do put the changes to the creator

        # create required relationships between the created entity and existing
        # non-user entities

        # different types of users have different required relationships
        k = kind if kind != 'user' else entity.user_type
        for kind_to_associate in config.required_associations.get(k, []):
            target_klass = core.kind_to_class(kind_to_associate)
            # the id of the entity to associate must have been passed in
            target = target_klass.get_by_id(kwargs[kind_to_associate])
            entity = self.associate('associate', entity, target, put=False)
        if k in config.optional_associations:
            for kind_to_associate in config.optional_associations[k]:
                # they're optional, so check if the id has been passed in
                if kind_to_associate in kwargs:
                    # if it was, do the association
                    target_klass = core.kind_to_class(kind_to_associate)
                    target = target_klass.get_by_id(kwargs[kind_to_associate])
                    entity = self.associate('associate', entity, target,
                                            put=False)

        # At one point we created qualtrics link pds for students here. Now
        # that happens in the program app via the getQualtricsLinks functional
        # node.

        # now we're done, so we can put all the changes to the new entity
        entity.put()

        return entity

    def create_qualtrics_link_pds(self, program, program_config, user):
        pd_batch = [
            {
                'variable': 's{}__qualtrics_link'.format(m['activity_ordinal']),
                'value': QualtricsLink.get_link(
                    program, m['activity_ordinal'], m['qualtrics_default_link'])
            }
            for m in program_config['outline']
            if 'type' in m and m['type'] == 'activity'
        ]
        logging.info("Grabbing {} qualtrics links for {}."
                     .format(len(pd_batch), user))
        link_pds = {
            'pd_batch': pd_batch,
            'program': user.assc_program_list[0],
            'scope': user.id,
        }

        # Have the student create the PDs
        user_api = Api(user)
        # Create the PDs defined above
        user_api.batch_put_pd(link_pds)

    def delete(self, kind, id):
        logging.info('Api.delete(kind={}, id={})'.format(kind, id))

        entity = core.Model.get_from_path(kind, id)
        if not self.user.has_permission('delete', entity):
            raise PermissionDenied()
        deleted_list = self._get_children(kind, id, [('deleted =', False)])
        cache = {}
        for e in deleted_list:
            # IdModel entities have relationships and need to be disassociated
            # when they are deleted. NamedModel entities (e.g. ShortLink)
            # don't and we can skip this step.
            if isinstance(e, IdModel):
                cache = self._disassociate(e.id, cache=cache)
            e.deleted = True
        # save changes to deleted entities
        db.put(deleted_list)
        # save changes to users which were disassociated from deleted entities
        db.put([e for id, e in cache.items()])
        return True

    def delete_everything(self):
        if self.user.user_type == 'god' and util.is_development():
            util.delete_everything()
        else:
            raise PermissionDenied("Only gods working on a development server "
                                   "can delete everything.")
        return True

    def get(self, kind, kwargs, ancestor=None):
        """Query entities in the datastore.

        Specify an ancestor to make an "ancestor query": a query limited to
        one entity group which is strongly consistent.

        * Applies query filters based on what permissions the user has.
        * Works around App Engine limitations for complex queries.
        * Calls class startup methods, allowing on-instantiation code execution
        """
        if 'n' in kwargs:
            n = int(kwargs['n'])
            del(kwargs['n'])
        else:
            n = 1000

        if 'order' in kwargs:
            order = kwargs['order']
            del(kwargs['order'])
        else:
            order = None

        permissions_filters = self.user.get_permission_filters(kind, 'get')
        # request_filters = [(k + ' =', v) for k, v in kwargs.items()]
        request_filters = []
        for k, v in kwargs.items():
            operator = ' IN' if type(v) is list else ' ='
            request_filters.append((k + operator, v))

        logging.info('Api.get(kind={}, kwargs={}, ancestor={})'
                     .format(kind, kwargs, ancestor))
        logging.info('permission filters: {}'.format(permissions_filters))
        logging.info('request filters: {}'.format(request_filters))

        filters = permissions_filters + request_filters
        klass = core.kind_to_class(kind)
        query = klass.all().filter('deleted =', False)

        if order:
            query.order(order)

        if isinstance(ancestor, core.Model):
            query.ancestor(ancestor)

        if kind in config.kinds_with_get_filters:
            filters = filters + klass.get_filters()

        safe_filters, unsafe_filters = Api.limit_subqueries(filters)

        # build the query
        for filter_tuple in safe_filters:
            query.filter(*filter_tuple)
        # get full, in-memory entities
        results = query.fetch(n)
        # post-processing, if necessary
        if len(unsafe_filters) > 0:
            results = Api.post_process(results, unsafe_filters)

        # run custom startup code, if such behavior is defined
        for e in results:
            if hasattr(e, 'startup'):
                e.startup()

        return results

    def get_by_ids(self, ids):
        grouped_ids = {}
        for id in ids:
            kind = core.get_kind(id)
            if kind not in grouped_ids:
                grouped_ids[kind] = []
            grouped_ids[kind].append(id)
        results = []
        for kind, ids in grouped_ids.items():
            results += self.get(kind, {'id': ids})
        return results

    def get_from_path(self, kind, id):
        results = self.get(kind, {'id': id})
        if len(results) is not 1:
            raise IdError()
        return results[0]

    def import_links(self, program, session_ordinal, filename):
        """Read in a cloud storage file full of Qualtrics unique links.

        See https://docs.google.com/document/d/1xrTaGf8-f0wyXg5ZnIH1O6uzSv-ro_ei1MpZOlwCXjA/edit
        """
        if self.user.user_type != 'god':
            raise PermissionDenied()

        # Our convention is to read link csv files out of a bucket named by
        # the app id. But for silly google reasons, the app id is prefixed by
        # 's~' internally (something to do with text search indexing). Take off
        # that bit before using the app id.
        app_id = app_identity.get_application_id()
        if app_id[:2] == 's~':
            app_id = app_id[2:]

        # Set GCS path dependent on program and session.
        path = '/{}_unique_qualtrics_links/{}-{}/{}'.format(
            app_id, program.abbreviation, session_ordinal, filename)

        retry_params = gcs.RetryParams()
        links = []

        # Try the gcs transaction
        try:
            f = gcs.open(path, mode='r', retry_params=retry_params)
        except gcs.NotFoundError:
            return ('GCS File not found. Did you upload a new file to the '
                    'bucket?')

        # Try the csv read
        try:
            reader = csv.reader(f)
            for row in reader:
                if row[7] == 'Link':
                    continue
                link = row[7]
                l = QualtricsLink.create(
                    key_name=link, link=link, program=program.id,
                    session_ordinal=session_ordinal)
                links.append(l)
        except Exception as e:
            logging.error('Something went wrong with the CSV import! {}'
                          .format(e))
            logging.error('CSV has been deleted, try uploading again.')
            # Throwing out links
            links = []

        finally:
            f.close()

        gcs.delete(path)

        db.put(links)
        return len(links)

    def init_activities(self, user_type, teacher_id, program_id, cohort_id=None, classroom_id=None, is_test=False):
        logging.info(
            'Api.init_activities(program={}, cohort={}, classroom={})'.format(
                program_id, cohort_id, classroom_id))

        program = self.get_from_path('program', program_id)

        # Get and check templates.
        templates = program.activity_templates(user_type)
        if len(templates) is 0:
            raise Exception("Program {} has no templates; cannot "
                            "initialize activities.".format(program.name))

        # Check that these activities don't already exist.
        params = {
            'user_type': user_type,
            'teacher': teacher_id,
            'assc_program_list': program.id,
            'is_test': is_test,
        }
        if cohort_id:
            params['assc_cohort_list'] = cohort_id
        if classroom_id:
            params['assc_classroom_list'] = classroom_id
        existing_activities = self.get('activity', params)

        if len(existing_activities) is not 0:
            # Some previous process created these activities, so do nothing.
            # Return an empty list b/c no activites were created.
            return []

        # Now we should be ready to create activities.
        created_activities = []
        for index, template in enumerate(templates):
            params = {
                # 'name': template['name'],
                'activity_ordinal': index + 1,
                'user_type': user_type,
                'teacher': teacher_id,
                'status': 'incomplete',
                'program_abbreviation': program.abbreviation,
                'program': program.id,
                'is_test': is_test,
            }
            if cohort_id:
                params['cohort'] = cohort_id
            if classroom_id:
                params['classroom'] = classroom_id
            created_activities.append(self.create('activity', params))
        return created_activities

    def preview_reminders(self, program, user_type):
        """Show what reminder emails will look like.

        Permissions are open, because this is read only and only uses data from
        the current user.
        See core@Reminder for details.
        """
        activities = self.get_by_ids(self.user.owned_activity_list)
        reminders = Reminder.preview_reminders(
            program, user_type, self.user, activities)
        return {'message': reminders}

    def program_outline(self, program_id):
        program = self.get('program', {'id': program_id})[0]
        t_conf = Program.get_app_configuration(program.abbreviation, 'teacher')
        s_conf = Program.get_app_configuration(program.abbreviation, 'student')
        return {'teacher': t_conf['outline'] if t_conf else None,
                'student': s_conf['outline'] if s_conf else None}

    def recursive_update(self, kind, id, params, preview=False):
        """Brute-force changes to an entity and all its children.

        Intentionally EXCLUDES pd entities in this recursion, because there
        could be thousands of entities to move and this could not be done
        without a timeout.

        Creates logs of its activity in case anything needs to be undone. Logs
        are JSON serialization of the set of all entities before changes and
        the set of entities after changes. This way, if some data is erased by
        this function, it can be found again.

        Returns a list of changed entities.

        Lana. Lana. LAAANAAAA. Danger zone.
        """
        if self.user.user_type != 'god':
            raise PermissionDenied()

        # Get the requested entity's children, limiting ourselves to
        # non-deleted ones. Keeping deleted entities around is really only for
        # emergency data recovery.
        entities = self._get_children(kind, id, [('deleted =', False)],
                                      exclude_kinds=['pd'])

        # keep a record of these entities before they were changed
        before_snapshot = [e.to_dict() for e in entities]

        #   Make all the requested property changes to all the retrieved
        # entities, if those properties exist. It's important to have this
        # flexibility because a single conceptual change (e.g. changing cohort
        # associations of all children) requires various kinds of property
        # updates (e.g. to assc_cohort_list of Activity and cohort of Pd).
        #   Also build a unique set of only the changed entities to make the
        # db.put() as efficient as possible.
        to_put = set()
        for e in entities:
            for k, v in params.items():
                if hasattr(e, k) and getattr(e, k) != v:
                    to_put.add(e)
                    setattr(e, k, v)
        to_put = list(to_put)

        after_snapshot = [e.to_dict() for e in to_put]

        if not preview:
            db.put(list(to_put))

            # save the log
            body = json.dumps({
                'entities before recursive update': before_snapshot,
                'entities after recursive update': after_snapshot,
            })
            log_entry = LogEntry.create(log_name='recursive_udpate', body=body)
            log_entry.put()

        return to_put

    def search(self, query, start=0, end=1):
        """Search the full text index. Return results from start to end.
        Ignore results that the user does not have permission to see.
        """

        indexer = Indexer.get_or_insert('the indexer')
        index = indexer.get_index()
        results = []

        matches = index.search(query)

        for match in matches:
            entity_id = match.doc_id

            try:
                entity = self.get_by_ids([entity_id])[0].to_dict()
                if not entity['is_test'] and not entity['deleted']:
                    results.append(entity)
            except PermissionDenied:
                pass
            except IndexError:
                logging.warning("Could not get entity: " + entity_id)

            if len(results) == end - start:
                break

        logging.info("""Search()
            query: {},
            n_results: {}
            result: {}
            """.format(query, len(results[start:]), results[start:]))

        return results[start:]

    def see(self, kind, kwargs):
        if 'n' in kwargs:
            n = kwargs['n']
            del(kwargs['n'])
        else:
            n = 1000

        # Although we almost always want to 'see' the entity's name, sometimes
        # want to specify a different property, like email. Allow this via the
        # 'see' key word.
        if 'see' in kwargs:
            projection = kwargs['see']
            del(kwargs['see'])
        else:
            projection = 'name'

        permissions_filters = self.user.get_permission_filters(kind, 'see')
        # request_filters = [(k + ' =', v) for k, v in kwargs.items()]
        request_filters = []
        for k, v in kwargs.items():
            operator = ' IN' if type(v) is list else ' ='
            request_filters.append((k + operator, v))

        logging.info('Api.see(kind={}, kwargs={})'.format(kind, kwargs))
        logging.info('permission filters: {}'.format(permissions_filters))
        logging.info('request filters: {}'.format(request_filters))

        filters = permissions_filters + request_filters
        klass = core.kind_to_class(kind)
        safe_filters, unsafe_filters = Api.limit_subqueries(filters)

        # Projection queries are nice and efficient for 'see' b/c they only
        # return what you're looking for (name and id), but they won't work if
        # you are filtering on the same thing you're projecting (see
        # https://developers.google.com/appengine/docs/python/datastore/projectionqueries#Python_Limitations_on_projections)
        # so fork into one of two modes: projection when not filtering by name,
        # and regular otherwise.
        # Also, post processing on projection results doesn't work because
        # python can't introspect the entity's properties.
        if 'name' in kwargs or len(unsafe_filters) > 0:
            # regular-type query
            query = klass.all().filter('deleted =', False)
        else:
            # projection query
            query = db.Query(klass, projection=[projection])
            query.filter('deleted =', False)
        for filter_tuple in safe_filters:
            query.filter(*filter_tuple)
        results = query.fetch(n)

        if len(unsafe_filters) > 0:
            results = Api.post_process(results, unsafe_filters)

        # Fill in the id property.
        for e in results:
            setattr(e, 'id', e.key().name())

        return results

    def see_by_ids(self, ids):
        grouped_ids = {}
        for id in ids:
            kind = core.get_kind(id)
            if kind not in grouped_ids:
                grouped_ids[kind] = []
            grouped_ids[kind].append(id)
        results = []
        for kind, ids in grouped_ids.items():
            results += self.see(kind, {'id': ids})
        return results

    def show_reminders(self, date_string=None):
        god_api = Api(User(user_type='god'))
        cron = Cron(god_api)
        reminders = cron.get_reminders_by_date(date_string)

        # Add a preview of how the text will be converted to html when sent.
        for r in reminders:
            r['html'] = markdown.markdown(r['body'])
        return reminders

    def stratify(self, name, program, proportions, attributes, reset_history=False):
        """Look up or create a stratifier with the provided details and use it
        it to stratify a user with provided attributes into a group. Setting
        reset_history to True will delete all StratifierHistory entities
        associated with the matching stratifier."""
        s_query = Stratifier.all().filter('deleted =', False)
        s_query.filter('name =', name)
        s_query.filter('program =', program)
        s_query.filter('proportions_json =', util.hash_dict(proportions))
        if s_query.count() > 1:
            raise Exception(
                "More than one stratifier with parameters {}, {}, {}.".format(
                    name, program, util.hash_dict(proportions)))
        s = s_query.get()
        if s is None:
            s = Stratifier.create(name=name, program=program,
                                  proportions=proportions)
            s.put()
        elif reset_history:
            sh_query = StratifierHistory.all().filter('stratifier =', s.id)
            db.delete(sh_query.fetch(1000, keys_only=True))
        return s.stratify(attributes)

    def unassociate(self, action, from_entity, to_entity, put=True):
        logging.info(
            'Api.unassociate(action={}, from_entity={}, to_entity={}, put={})'
            .format(action, from_entity.id, to_entity.id, put))

        # create the requested association
        from_kind = core.get_kind(from_entity)
        to_kind = core.get_kind(to_entity)
        if not self.user.can_associate(action, from_entity, to_entity):
            raise PermissionDenied()
        logging.info("action {}".format(action))
        if action == 'disown':
            property_name = 'owned_' + to_kind + '_list'
        elif action == 'unassociate':
            property_name = 'assc_' + to_kind + '_list'
        relationship_list = getattr(from_entity, property_name)
        if to_entity.id in relationship_list:
            relationship_list.remove(to_entity.id)
        setattr(from_entity, property_name, relationship_list)

        # recurse through cascading relationships
        start_cascade = (action == 'unassociate' and from_kind == 'user' and
                         to_kind in config.user_disassociation_cascade)
        if start_cascade:
            for k in config.user_disassociation_cascade[to_kind]:
                # figure out the target entity
                attr = 'assc_{}_list'.format(k)
                target_id = getattr(to_entity, attr)[0]
                target_entity = core.Model.get_from_path(k, target_id)
                # make sure the user is ALREADY associated with the target
                if target_id in getattr(from_entity, attr):
                    # then actually unassociate
                    from_entity = self.unassociate(
                        'unassociate', from_entity, target_entity, put=False)

        if not put:
            # avoid multiple db.puts when creating entities
            return from_entity
        else:
            from_entity.put()

        return from_entity

    def update(self, kind, id, kwargs):
        entity = core.Model.get_from_path(kind, id)
        if not self.user.has_permission('put', entity):
            raise PermissionDenied()
        # if creating a user, can this user create this TYPE of user
        # this is necessary to check if user can promote target user
        # to the proposed level; that does not get checked in user.can_put()
        if kind == 'user' and 'user_type' in kwargs:
            if not self.user.can_put_user_type(kwargs['user_type']):
                raise PermissionDenied(
                    "{} cannot create users of type {}.".format(
                        self.user.user_type, kwargs['user_type']))

        # some updates require additional validity checks
        if kind in config.kinds_requiring_put_validation:
            kwargs = entity.validate_put(kwargs)

        # run the actual update
        for k, v in kwargs.items():
            setattr(entity, k, v)
        entity.put()
        return entity

    def _disassociate(self, id, cache={}):
        """Find all users associated with this entity and remove the
        relationship. Does not touch the datastore."""
        logging.info('Api._disassociate(id={})'.format(id))

        kind = core.get_kind(id)
        for relation in ['assc', 'owned']:
            prop = '{}_{}_list'.format(relation, kind)
            query = User.all().filter('deleted =', False)
            query.filter(prop + ' =', id)
            for entity in query.run():
                if entity.id in cache:
                    # prefer the cached entity over the queried one b/c the
                    # datastore is eventually consistent and repeatedly getting
                    # the same entity is not guaranteed to reflect changes.
                    entity = cache[entity.id]
                else:  # cache the entity so it can be used again
                    cache[entity.id] = entity
                relationship_list = getattr(entity, prop)
                relationship_list.remove(id)
        return cache

    def _get_children(self, kind, id, filters=[], exclude_kinds=[]):
        """Returns a list of the requested entity and all its children. What
        'children' means is defined by config.children_cascade."""
        # Confusingly enough, a pegasus kind is not the same as an app engine
        # kind. Example: class StraitifierHistory:
        # pegasus kind (used in api urls): 'stratifier_history'
        # app engine kind (used in keys): 'StratifierHistory'
        klass = core.kind_to_class(kind)
        entity = klass.get_by_id(id)
        results = [entity]

        # children-fetching differs based on user type
        if kind == 'user':
            if entity.user_type in ['god']:
                raise Exception()
            kind = entity.user_type

        # Depending on the current kind, we need to get children of other
        # kinds. Exactly which kinds and filters apply is defined in
        # config.children_cascade. For instance, activities with user type
        # 'teacher' are children of a user with user type 'teacher', but
        # activities with user type 'student' are not (those are children of a
        # classroom). Since this structure doesn't map perfectly onto pure
        # kinds, we need a little fanciness to achieve the needed flexibility.
        if kind in config.children_cascade:
            for info in config.children_cascade[kind]:
                loop_filters = filters[:]
                # activities need some extra filtering
                if info.kind == 'teacher_activity':
                    loop_filters.append(('user_type =', 'teacher'))
                    child_kind = 'activity'
                elif info.kind == 'student_activity':
                    loop_filters.append(('user_type =', 'student'))
                    child_kind = 'activity'
                else:
                    child_kind = info.kind

                if child_kind not in exclude_kinds:
                    child_klass = core.kind_to_class(child_kind)
                    q = child_klass.all().filter(info.property + ' =', id)
                    for filter_tuple in loop_filters:
                        q.filter(*filter_tuple)
                    for child in q.run():
                        results += self._get_children(
                            child_kind, child.id, filters, exclude_kinds)

        return results
