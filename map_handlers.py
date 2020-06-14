"""URL Handlers designed to be simple wrappers over our map reduce jobs.
See map.py.
"""

import json
import logging
import mapreduce
import traceback
import webapp2

import core
import id_model
import map as map_module  # don't collide with native function map()
import url_handlers
import util


debug = util.is_development()


class MapHandler(url_handlers.BaseHandler):
    """Superclass for all map-reduce-related urls."""

    def do_wrapper(self, *args, **kwargs):
        """Do setup for map handlers.

        - Jsons output
        - logs exception traces
        """
        try:
            self.write_json(self.do(*args, **kwargs))
        except Exception as error:
            trace = traceback.format_exc()
            logging.error("{}\n{}".format(error, trace))
            response = {
                'success': False,
                'message': '{}: {}'.format(error.__class__.__name__, error),
                'trace': trace,
            }
            self.write_json(response)

    def write_json(self, obj):
        r = self.response
        r.headers['Content-Type'] = 'application/json; charset=utf-8'
        r.write(json.dumps(obj))


class DeidentifyHandler(MapHandler):
    """Hash *student* properties so they can't be identified with participants.

    We only deidentify students b/c only they have the possibility of lacking
    parental consent. Adult participants are not a concern.

    Also has a preview mode, which doesn't use map reduce, but queries for
    a sample of data and runs the mapper function on it, showing you the before
    and after results.
    Args:
        preview: bool, default False, if True, don't run mapreduce job, just
            preview changes
        n: int, default 100, how many entities to include in the preview sample
        list_name: str, the relationship list, e.g. 'assc_cohort_list'
        list_values_json: json str, the entity ids to be found in the list,
            e.g. 'Cohort_XYZ'. Students matching on ANY of these ids will be
            deidentified. This makes it easy to run one job that deidentifies
            several schools or cohorts at once.
        [other arugments]: str, filters for the preview sample query
    """
    def do(self):
        params = util.get_request_dictionary(self.request)

        # The list values must be given in the GET or POST as
        # 'list_values_json' so they are interpreted as a list by
        # util.get_request_dictionary. Check that the list came through.
        if type(params['list_values']) is not list:
            raise Exception("Parameter 'list_values_json' missing or invalid.")

        # Params not in this list will be used to filter previews.
        expected_keys = ['n', 'preview', 'list_name', 'list_values', 'salt']

        # Don't run the map reduce job, just show a sample of what it
        # would do.
        if 'preview' in params and params['preview'] is True:
            n = int(params['n']) if 'n' in params else 100

            # Set up a fake job context for the mapper
            conf = map_module.deidentify(
                params['list_name'], params['list_values'], params['salt'],
                submit_job=False)
            context = map_module.get_fake_context(conf)

            # This function will modify the user if they should be deidentified
            # (if the user has the specified relationship).
            mapper = map_module.DeidentifyMapper()

            # Get some entities to preview.
            query = id_model.User.all()
            for k, v in params.items():
                if k not in expected_keys:
                    query.filter(k + ' =', v)
            sample = query.fetch(n)
            before = [e.to_dict() for e in sample]

            results = [mapper.do(context, e) for e in sample]
            after = [e.to_dict() for e in results]

            return {
                'success': True,
                'preview': True,
                'n': n,
                'data': {
                    'before': before,
                    'after': after,
                },
                'message': (
                    "Warning: the results returned here are the result of a "
                    "simple query-and-modify, not a true map reduce job. "
                    "Also, no changes have been saved."),
            }

        # Run it for real
        else:
            conf = map_module.deidentify(
                params['list_name'], params['list_values'], params['salt'])
            return {'success': True, 'data': conf.job_id}


class ModifyKindHandler(MapHandler):
    """Run the named mapper.

    There must be a method of this class for each mapper.

    Also has a preview mode, which doesn't use map reduce, but queries for
    a sample of data and runs the mapper function on it, showing you the before
    and after results.
    Args:
        preview: bool, default False, if True, don't run mapreduce job, just
            preview changes
        n: int, default 100, how many entities to include in the preview sample
        [other arugments]: str, filters for the preview sample query
    """
    def do(self, mapper_name):
        params = util.get_request_dictionary(self.request)

        kind, mapper, params = getattr(self, mapper_name)(params)
        klass = core.kind_to_class(kind)

        # Don't run the map reduce job, just show a sample of what it
        # would do.
        if 'preview' in params and params['preview'] is True:
            # Get some entities to preview.
            n = int(params['n']) if 'n' in params else 10
            query = id_model.User.all()
            for k, v in params.items():
                if k not in ['n', 'preview']:
                    query.filter(k + ' =', v)
            sample = query.fetch(n)
            before = [e.to_dict() for e in sample]

            # Set up a fake job context for the mapper and run it on each
            # entity.
            context = self.get_fake_context(kind, mapper)
            results = [mapper().do(context, e) for e in sample]
            after = [e.to_dict() for e in sample]

            return {
                'success': True,
                'preview': True,
                'n': n,
                'data': {
                    'before': before,
                    'after': after,
                },
                'message': (
                    "Warning: the results returned here are the result of a "
                    "simple query-and-modify, not a true map reduce job. "
                    "Also, no changes have been saved."),
            }

        # Run it for real
        else:
            job_config = map_module.modify_kind(kind, mapper)
            return {'success': True, 'data': job_config.job_id}

    def lower_case_login(self, params):
        kind = 'user'
        mapper = map_module.LowerCaseLoginMapper
        return (kind, mapper, params)

    def certify_students(self, params):
        kind = 'user'
        mapper = map_module.CertifyStudentsMapper
        return (kind, mapper, params)

    def fix_aggregation_json_user(self, params):
        kind = 'user'
        mapper = map_module.AggregationJsonMapper
        return (kind, mapper, params)

    def fix_aggregation_json_activity(self, params):
        kind = 'activity'
        mapper = map_module.AggregationJsonMapper
        return (kind, mapper, params)

    def fix_aggregation_json_cohort(self, params):
        kind = 'cohort'
        mapper = map_module.AggregationJsonMapper
        return (kind, mapper, params)

    def get_fake_context(self, kind, mapper):
        conf = map_module.modify_kind(kind, mapper, submit_job=False)
        return map_module.get_fake_context(conf)


class ModifyPdHandler(MapHandler):
    """Modify pd entities.

    CURRENTLY DISABLED PENDING FURTHER TESTING

    Ben's suggested tests that still need to be done:

    * Be sure spot checks are random and do a bunch If you can manage to do 20
      spot check for 20 random pds that should be moved and 20 that should not
      and do not notice a single error, then you have pretty strong assurances
      that there are not any error.
    * Be sure aggregate values come out as expected After moving a teacher to a
      new cohort, re-run the aggregator and make sure their totals appear in
      the new cohort as expected, too. This is a nice way to verify that there
      are not many rare errors, also that aggregation was not broken by the
      move.

    See also pull request #268.

    =====================

    Also has a preview mode, which doesn't use map reduce, but queries for
    a sample of data and runs the mapper function on it, showing you the before
    and after results.

    Runnable by school_admins and up, but with lots of restrictions.
    
    Args:
        preview: bool, default False, if True, don't run mapreduce job, just
            preview changes
        n: int, default 100, how many entities to include in the preview sample
        to_match: json dict, property-value pairs. Pds that match ALL these
            will be modified. String values for 'program' and 'cohort' are
            required. Other values may be strings or lists.
        to_change: json dict, property-value pairs. Matching pds will have
            these properties changed to the corresponding values. Only
            'cohort' and 'classroom' are allowed.
    """
    def do(self):
        return {'success': False,
                'message': "This tool needs further testing. See docstring of "
                           "ModifyPdHandler and pull request #268."}

        params = util.get_request_dictionary(self.request)
        to_match = params['to_match']
        to_change = params['to_change']

        # Must be at least a school admin to run this.
        user = self.get_current_user()
        if user.user_type not in ['god', 'researcher', 'school_admin']:
            raise core.PermissionDenied()

        # Although this mapper is written very generally and is capable of
        # changing any property of pd entities, we want to artificially limit
        # it to changing cohort and classroom, b/c that's all that our use
        # cases require.
        allowed_keys = set(['classroom', 'cohort'])
        illegal_keys = set(to_change.keys()).difference(allowed_keys)
        if len(to_change.keys()) is 0 or len(illegal_keys) > 0:
            raise Exception("Not allowed to change {}".format(illegal_keys))

        # You must, at minimum, specify a single cohort and single program
        # (not a list) in to_match, otherwise the scope of changes would be
        # out of control.
        if 'program' not in to_match or type(to_match['program']) is not unicode:
            raise Exception("Must specify a single program in to_match.")
        if 'cohort' not in to_match or type(to_match['cohort']) is not unicode:
            raise Exception("Must specify a single cohort in to_match.")

        # Check permissions. To run this job, the user must have permission on
        # any cohorts in either to_match or to_change.
        # These functions will raise their own exceptions if necessary.
        user.can_put_pd(to_match['program'], to_match['cohort'])
        if 'cohort' in to_change:
            user.can_put_pd(to_match['program'], to_change['cohort'])

        # Preview: don't run the map reduce job, just show a sample of what it
        # would do.
        if 'preview' in params and params['preview'] is True:
            n = int(params['n']) if 'n' in params else 100

            # Set up a fake job context for the mapper
            conf = map_module.modify_pd(to_match, to_change, submit_job=False)
            context = map_module.get_fake_context(conf)

            # This function will modify the entities.
            mapper = map_module.ModifyPdMapper()

            # Get some entities to preview.
            query = id_model.Pd.all()
            for k, v in to_match.items():
                if isinstance(v, list):
                    # Limit the length of the list b/c app engine has issues.
                    v = v[:30]
                    query.filter(k + ' IN', v)
                else:
                    query.filter(k + ' =', v)
            sample = query.fetch(n)
            before = [e.to_dict() for e in sample]

            results = [mapper.do(context, e) for e in sample]
            after = [e.to_dict() for e in sample]

            return {
                'success': True,
                'preview': True,
                'n': n,
                'data': {
                    'before': before,
                    'after': after,
                },
                'message': (
                    "Warning: the results returned here are the result of a "
                    "simple query-and-modify, not a true map reduce job. "
                    "Also, no changes have been saved."),
            }

        # Run it for real
        else:
            job_config = map_module.modify_pd(to_match, to_change)
            return {'success': True, 'data': job_config.job_id}


class StatusHandler(MapHandler):
    """Query status of a map reduce job.

    Returns: 'running', 'success', 'failed', or 'aborted'
    """
    def do(self, job_id):
        MapreduceJob = mapreduce.api.map_job.map_job_control.Job
        # The error message if the job id is wrong is confusing. Simplify it.
        try:
            job = MapreduceJob.get_job_by_id(job_id)
        except ValueError:
            raise Exception("Invalid job id: {}".format(job_id))

        return {
            'success': True,
            'data': job.get_status(),
        }


webapp2_config = {
    'webapp2_extras.sessions': {
        # cam. I think this is related to cookie security. See
        # http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html
        'secret_key': '8YcOZYHVrVCYIx972K3MGhe9RKlR7DOiPX2K8bB8',
    },
}

app = webapp2.WSGIApplication([
    ('/map/(lower_case_login)', ModifyKindHandler),
    ('/map/(certify_students)', ModifyKindHandler),
    ('/map/(fix_aggregation_json_user)', ModifyKindHandler),
    ('/map/(fix_aggregation_json_activity)', ModifyKindHandler),
    ('/map/(fix_aggregation_json_cohort)', ModifyKindHandler),
    ('/map/deidentify', DeidentifyHandler),
    ('/map/modify_pd', ModifyPdHandler),
    ('/map/status/(.*)', StatusHandler),
], config=webapp2_config, debug=debug)
