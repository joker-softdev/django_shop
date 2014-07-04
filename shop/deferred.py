# -*- coding: utf-8 -*-
import six
from django.db.models.base import ModelBase
from django.db import models
from django.core.exceptions import ImproperlyConfigured


class DeferredForeignKey(object):
    """
    Use this class to specify foreign keys in abstract classes. They will be converted into a real
    ``ForeignKey`` whenever a real model class is derived from a given abstract class.
    """
    def __init__(self, abstract_model, **kwargs):
        try:
            abstract_model = abstract_model._meta.object_name
        except AttributeError:
            assert isinstance(abstract_model, six.string_types), "%s(%r) is invalid. First parameter to ForeignKey must be either a model or a model name" % (self.__class__.__name__, abstract_model)
        else:
            assert abstract_model._meta.abstract, "%s can only define a relation with abstract class %s" % (self.__class__.__name__, abstract_model._meta.object_name)
        self.abstract_model = abstract_model
        self.options = kwargs


class DeferredManyToManyField(object):
    """
    Use this class to specify many-to-many keys in abstract classes. They will be converted into a
    real ``ManyToManyField`` whenever a real model class is derived from a given abstract class.
    """
    def __init__(self, model, *args, **kwargs):
        print "DeferredManyToManyField:", model


class ForeignKeyBuilder(ModelBase):
    _derived_models = {}
    _pending_mappings = []

    def __new__(cls, name, bases, attrs):
        print '#################__new__', name
        model = super(ForeignKeyBuilder, cls).__new__(cls, name, bases, attrs)
        if model._meta.abstract:
            return model
        for baseclass in bases:
            if not issubclass(model, baseclass):
                continue
            if baseclass.__name__ in cls._derived_models:
                if model.__name__ != cls._derived_models[baseclass.__name__]:
                    raise ImproperlyConfigured("Both Model classes '{0}' and '{1}' inherited" +
                        "from abstract base class {2}, which is disallowed in this configuration.")
            else:
                cls._derived_models[baseclass.__name__] = model.__name__
                # check for pending mappings and in case, process them
                new_mappings = []
                for mapping in cls._pending_mappings:
                    if mapping[2].abstract_model == baseclass.__name__:
                        if isinstance(mapping[2], DeferredForeignKey):
                            field = models.ForeignKey(model.__name__, **mapping[2].options)
                            field.contribute_to_class(mapping[0], mapping[1])
                    else:
                        new_mappings.append(mapping)
                cls._pending_mappings = new_mappings

        print "_derived_models ", cls._derived_models

        for attrname in dir(model):
            member = getattr(model, attrname)
            if isinstance(member, DeferredForeignKey):
                mapmodel = cls._derived_models.get(member.abstract_model)
                print "map ", member.abstract_model, " -> ", mapmodel
                if mapmodel:
                    field = models.ForeignKey(mapmodel, **member.options)
                    field.contribute_to_class(model, attrname)
                else:
                    cls._pending_mappings.append((model, attrname, member,))
        return model


class AbstractModel1(six.with_metaclass(ForeignKeyBuilder, models.Model)):
    class Meta:
        abstract = True

    name = models.CharField(max_length=20)
    parent = DeferredForeignKey('AbstractModel1', blank=True, null=True, related_name='rel_parent')
    that = DeferredForeignKey('AbstractModel2', blank=True, null=True, related_name='rel_that')

    def __init__(self, *args, **kwargs):
        print "AbstractModel1.__init__"
        super(AbstractModel1, self).__init__(*args, **kwargs)


class AbstractModel2(six.with_metaclass(ForeignKeyBuilder, models.Model)):
    class Meta:
        abstract = True

    identifier = models.CharField(max_length=20)
    other = DeferredForeignKey('AbstractModel1', blank=True, null=True)
