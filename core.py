"""Contains the most fundamental classes of the pegasus data Model."""

from google.appengine.ext import db
from string import ascii_uppercase
import collections
import datetime
import logging                                      # error logging
import sys

from simple_profiler import Profiler
import config
import util


profiler = Profiler()


def kind_to_class(string):
    """
    Convert from lower_underscore_case to a class named StandingCamelCase.
    Necessary because our urls use lowercase strings to specify kinds of entities.
    See http://stackoverflow.com/questions/1176136/convert-string-to-python-class-object

    In Production:
        Be sure to check for strings that cannot be converted returned from Kind.all()
        I'm not sure why these only exist in production, but they do.

        concretely,
        check for 'AttributeError' as I have in Indexer.get_changed_entities
        update - bmh 2013
    """
    logging.info("core.kind_to_class(string={})".format(string))
    words = string.split('_')
    capitalize = lambda w: w[:1].upper() + w[1:]
    class_name = ''.join(map(capitalize, words))

    # Try to look up the class with this name in core.py (this file). If it's
    # not found, try named.py.
    try:
        klass = reduce(getattr, class_name.split('.'),
                       sys.modules['id_model'])
    except AttributeError:
        klass = reduce(getattr, class_name.split('.'),
                       sys.modules['named_model'])

    return klass


def get_kind(entity_or_id):
    """Get the lower_underscore_case name of an entity, called a 'kind'."""
    logging.info("core.get_kind(entity_or_id={})".format(entity_or_id))
    if isinstance(entity_or_id, Model):
        class_name = entity_or_id.__class__.__name__
    else:
        class_name = entity_or_id.split('_')[0]
    words = []
    previous_index = None
    for i, char in enumerate(class_name):
        if char in ascii_uppercase:
            if i is not 0:
                words.append(class_name[previous_index:i])
            previous_index = i
    if previous_index is None:
        raise Exception("core.get_kind() couldn't proccess input: {}."
                        .format(entity_or_id))
    words.append(class_name[previous_index:])
    return '_'.join([s.lower() for s in words])


class CredentialsMissing(Exception):
    """Raised when we fail to find expected authentication credentials."""
    pass


class PermissionDenied(Exception):
    pass


class Model(db.Model):
    """Superclass for all others; contains generic properties and methods."""

    created = db.DateTimeProperty(auto_now_add=True)

    # This property doesn't have auto_now=True on purpose. Our custom put hook
    # will update this property with the current time "manually" in almost all
    # cases. But when this property *shouldn't* be updated, it's possible to
    # leave it as is. This is currently used by the Aggregator.
    modified = db.DateTimeProperty()

    # This property is only set by the aggregator. It's here as a sort of log
    # b/c otherwise the aggregator leaves no record of when it touched a
    # given entity.
    aggregated = db.DateTimeProperty()

    systematic_updates = db.StringListProperty()

    @classmethod
    def get_from_path(klass, kind, key_name):
        k = kind_to_class(kind)
        return k.get_by_id(key_name)

    def before_put(self, set_modified_time):
        """Globally process entities before saving to datastore.

        Skips setting modified time if 'dont_set_modified_time' is True.
        """
        if set_modified_time:
            self.modified = self.datetime()

    def put(self, set_modified_time=True, **kwargs):
        """Hook into the normal my_entity.put() operations to add more options.

        Args:
            set_modified_time: bool, default True, set to False if you want
                to avoid the appearance of having modified the entity, e.g.
                for internal, programmtic modifications like aggregation.
            **kwargs: normal app engine arguments, see docs:
                https://developers.google.com/appengine/docs/python/datastore/modelclass#Model_put
        """
        self.before_put(set_modified_time)

        super(Model, self).put(**kwargs)

    def to_dict(self, override=None):
        """Convert an app engine entity to a dictionary.

        Args:
            override: obj, if provided, method turns this object into
                a dictionary, rather than self.
        """

        SIMPLE_TYPES = (int, long, float, bool, dict, basestring, list)
        output = {}

        obj = override or self

        for key, prop in obj.properties().iteritems():
            value = getattr(obj, key)

            if value is None or isinstance(value, SIMPLE_TYPES):
                output[key] = value
            elif isinstance(value, datetime.date):
                output[key] = str(value)
            elif isinstance(value, db.GeoPt):
                output[key] = {'lat': value.lat, 'lon': value.lon}
            elif isinstance(value, db.Model):
                output[key] = obj.to_dict(override=value)
            else:
                raise ValueError('cannot encode ' + repr(prop))

        # add key, if it exists (it is only created after a put)
        try:
            output['entity_key'] = str(obj.key())
        except:
            pass

        client_safe_output = {}
        for k, v in output.items():
            if k in config.client_private_properties:
                client_safe_output['_' + k] = v
            elif k not in config.client_hidden_properties:
                client_safe_output[k] = v

        # order them so they're easier to read
        ordered_dict = collections.OrderedDict(
            sorted(client_safe_output.items(), key=lambda t: t[0]))

        return ordered_dict

    def datetime(self):
        return datetime.datetime.utcnow()

# Hook into db.put, just like we hooked into db.Model.put
# We'll need a reference to the original function so we can use it within
# the new monkeypatched function.
_old_put = db.put


def _hooked_put(entity_or_entities, set_modified_time=True, **kwargs):
    """Replacement of db.put so we can hook in additional logic.

    Args same as standard db.put, but with additional key word argument:
        set_modified_time: bool, default True, set to False if you want
            to avoid the appearance of having modified the entity, e.g.
            for internal, programmtic modifications like aggregation.

    See https://developers.google.com/appengine/docs/python/datastore/functions#put
    """
    # put must be able to handle both single entities and lists of them.
    # Standardize into a list for convenience.
    if not isinstance(entity_or_entities, list):
        entities = [entity_or_entities]
    else:
        entities = entity_or_entities

    # Only run before_put() if these are lists of Model entities.
    # MapReduce, for instance, uses this code with entities that don't have
    # before_put defined, and so we should let them through silently.
    for e in entities:
        if hasattr(e, 'before_put'):
            e.before_put(set_modified_time)

    # Put the original argument to preserve default behavior.
    _old_put(entity_or_entities, **kwargs)


db.put = _hooked_put


class SecretValue(db.Model):
    """A secret key-value pair.

    Currently used for storing configuration values, like hash salts.
    """
    value = db.StringProperty(default='')
