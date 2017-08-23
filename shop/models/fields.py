# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import enum

from django.conf import settings
from django.db import models
from django.utils.six import python_2_unicode_compatible, with_metaclass, string_types
from django.utils.translation import ugettext_lazy


postgresql_engine_names = [
    'django.db.backends.postgresql',
    'django.db.backends.postgresql_psycopg2',
]

if settings.DATABASES['default']['ENGINE'] in postgresql_engine_names:
    from django.contrib.postgres.fields import JSONField as _JSONField
else:
    from jsonfield.fields import JSONField as _JSONField


class JSONField(_JSONField):
    def __init__(self, *args, **kwargs):
        kwargs.update({'default': {}})
        super(JSONField, self).__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(JSONField, self).deconstruct()
        del kwargs['default']
        return name, path, args, kwargs


class ChoiceEnumMeta(enum.EnumMeta):
    def __new__(cls, name, bases, attrs):
        new_class = super(ChoiceEnumMeta, cls).__new__(cls, name, bases, attrs)
        values = [p.value for p in new_class.__members__.values()]
        if len(values) > len(set(values)):
            msg = "Duplicate values found in class '{}'".format(name)
            raise ValueError(msg)
        return new_class

    def __call__(cls, value, *args, **kwargs):
        if isinstance(value, string_types):
            try:
                value = cls.__members__[value]
            except KeyError:
                pass  # let the super method complain
        return super(ChoiceEnumMeta, cls).__call__(value, *args, **kwargs)


@python_2_unicode_compatible
class ChoiceEnum(with_metaclass(ChoiceEnumMeta, enum.Enum)):
    """
    Utility class to handle choices in Django model fields
    """
    def __str__(self):
        return ugettext_lazy('.'.join((self.__class__.__name__, self.name)))

    @classmethod
    def default(cls):
        try:
            return next(iter(cls))
        except StopIteration:
            return None

    @classmethod
    def choices(cls):
        choices = [(c.value, str(c)) for c in cls]
        return choices


class ChoiceEnumField(models.PositiveSmallIntegerField):
    description = ugettext_lazy("Customer recognition state")

    def __init__(self, *args, **kwargs):
        self.enum_type = kwargs.pop('enum_type', ChoiceEnum)
        if not issubclass(self.enum_type, ChoiceEnum):
            raise ValueError("enum_type must be a subclass of `ChoiceEnum`.")
        kwargs.update(choices=self.enum_type.choices())
        kwargs.setdefault('default', self.enum_type.default())
        super(ChoiceEnumField, self).__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(ChoiceEnumField, self).deconstruct()
        if 'choices' in kwargs:
            del kwargs['choices']
        if kwargs['default'] is self.enum_type.default():
            del kwargs['default']
        elif isinstance(kwargs['default'], self.enum_type):
            kwargs['default'] = kwargs['default'].value
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection, context):
        return self.enum_type(value)

    def get_prep_value(self, state):
        if isinstance(state, self.enum_type):
            return state.value
        return state

    def to_python(self, state):
        return self.enum_type(state)

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        return value.name
