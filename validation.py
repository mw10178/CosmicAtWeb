#!/usr/bin/env python
# coding: utf-8

# tool for data validation of dynamic forms
# Copyright (C) 2015  Martin Ohmann
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import logging
import re
from collections import OrderedDict
from copy import deepcopy

from i18n import _
from safeeval import safeeval

logging.basicConfig(level = logging.DEBUG, format = '%(filename)s:%(funcName)s:%(lineno)d:%(message)s')
log = logging.getLogger('validation')

class ValidationError(Exception):
    pass


class ValidatorTypeError(Exception):
    pass


class Validator(object):

    """
    title is a meaningful description of the formfield
    """
    def validate(self, name, title, value):
        pass


class Castable(Validator):

    def __init__(self, cast_func, **kwargs):
        self.cast_func = cast_func
        self.allow_empty = kwargs.get('allow_empty', False)
        self.msg_fmt = ''

    def validate(self, name, title, value):
        try:
            if self.allow_empty and value == '':
                return value
            value = self.cast_func(value)
        except ValueError:
            raise ValidationError(self.msg_fmt % title)
        return value


class Int(Castable):

    """
    Validates if value can be cast to integer
    """
    def __init__(self, **kwargs):
        super(Int, self).__init__(int, **kwargs)
        self.msg_fmt = _('%s has to be an integer')


class Float(Castable):

    """
    Validates if value ca be cast to float
    """
    def __init__(self, **kwargs):
        super(Float, self).__init__(float, **kwargs)
        self.msg_fmt = _('%s has to be a float value')


class Range(Validator):

    """
    Validates if value is within range
    """
    def __init__(self, rmin, rmax, **kwargs):
        self.rmin = rmin
        self.rmax = rmax
        self.exclude_min = kwargs.get('exclude_min', False)
        self.exclude_max = kwargs.get('exclude_max', False)
        self.allow_empty = kwargs.get('allow_empty', False)
        self.castable = None
        self.l = ']' if self.exclude_min else '['
        self.r = '[' if self.exclude_max else ']'
        self.msg_fmt = _('%(title)s has to be within range %(l)s%(min).10g,%(max).10g%(r)s')

    def validate(self, name, title, value):
        if self.allow_empty and value == '':
            return value

        if self.castable != None:
            value = self.castable.validate(name, title, value)
        try:
            if self.exclude_min and not(self.rmin < value <= self.rmax):
                raise ValueError
            elif self.exclude_max and not(self.rmin <= value < self.rmax):
                raise ValueError
            elif self.exclude_min and self.exclude_max and not(self.rmin < value < self.rmax):
                raise ValueError
            elif not (self.rmin <= value <= self.rmax):
                raise ValueError
        except ValueError:
            raise ValidationError(self.msg_fmt %
                { 'title': title, 'min': self.rmin, 'max': self.rmax,
                    'l': self.l, 'r': self.r })
        return value


class IntRange(Range):

    """
    Validates if value is castable to int and within range
    """
    def __init__(self, *args, **kwargs):
        super(IntRange, self).__init__(*args, **kwargs)
        self.castable = Int(**kwargs)


class FloatRange(Range):

    """
    Validates if value is castable to float and within range
    """
    def __init__(self, *args, **kwargs):
        super(FloatRange, self).__init__(*args, **kwargs)
        self.castable = Float(**kwargs)


class Gte(Validator):

    def __init__(self, val, **kwargs):
        self.val = val
        self.allow_empty = kwargs.get('allow_empty', False)

    def validate(self, name, title, value):
        if self.allow_empty and value == '':
            return value
        if value < self.val:
            raise ValidationError(
                _("%(title)s has to be greater than or equal to %(value).10g") %
                { 'title': title, 'value': self.val })
        return value


class Regexp(Validator):

    """
    Validates if value matches the given regexp,
    regexp_desc can supply a meaningful transcription
    of the given regexp
    """
    def __init__(self, regexp, **kwargs):
        self.regexp = regexp
        self.re = re.compile(regexp)
        self.allow_empty = kwargs.get('allow_empty', False)
        self.regexp_desc = kwargs.get('regexp_desc', None)

        if self.regexp_desc == None:
            self.regexp_desc = regexp

    def validate(self, name, title, value):
        if self.allow_empty and value == '':
            return value
        if not self.re.match(value):
            raise ValidationError(
                _("%(title)s has to match %(desc)s") %
                { 'title': title, 'desc': self.regexp_desc })
        return value


class NotEmpty(Validator):

    """
    Validates if value is not an empty string
    """
    def validate(self, name, title, value):
        if value == "":
            raise ValidationError(_("%s must not be empty") %
                    title)
        return value


class OneOf(Validator):

    """
    Validates if value is in item_list
    """
    def __init__(self, item_list):
        if not isinstance(item_list, (list, tuple)):
            raise ValueError("list or tuple expected")

        self.item_list = item_list

    def validate(self, name, title, value):
        if not value in self.item_list:
            raise ValidationError(
                _("%(title)s has to be one of %(items)s") %
                { 'title': title, 'items': ', '.join(self.item_list)})
        return value


class Expression(Validator):

    """
    Tries to evaluate the given expression,
    the expression is surrounded by the optional prefix and suffix,
    'args' are passed to safeeval as local variables
    if 'transform' is set to False, the expression will be evaluated,
    but the result will not be stored into the form_data dict
    """
    def __init__(self, prefix = '', suffix = '', args = {}, **kwargs):
        self.prefix = prefix
        self.suffix = suffix
        self.transform = kwargs.get('transform', False)
        self.return_type = kwargs.get('return_type', None)
        self.safeeval = safeeval()
        self.args = args

        # add args to safeeval's local variables
        if self.args != None:
            for k, v in args.items():
                self.safeeval[k] = v


    def validate(self, name, title, value):
        if value == "":
            return value
        try:
            variables = ', '.join(self.args.keys()) if self.args != None else _('none')
            msg = _("%(title)s is no valid expression, "
                    "allowed variables: %(vars)s") % {
                            'title': title,
                            'vars': variables }
            result = self.safeeval(self.prefix + value + self.suffix)

            if self.return_type != None:
                if not isinstance(result, self.return_type):
                    msg = _("Expression %(title)s returned an invalid type. "
                            "Expected: %(expected)s, found: %(found)s. Maybe accidently "
                            "used comma as decimal separator?") % {
                                    'title': title,
                                    'expected': self.return_type.__name__,
                                    'found': type(result).__name__ }
                    raise TypeError
            # only transform field value if intended
            if self.transform:
                return result
        except Exception:
            raise ValidationError(msg)
        return value


class DataValidator(object):

    def add(self, name, validator, **kwargs):
        pass

    def validate(self):
        pass


class FormDataValidator(DataValidator):

    """
    The FormValidator applies validators to certain fields of the form_data.
    """
    def __init__(self, form_data, strict=False):
        self.fields = OrderedDict()
        self.errors = []
        self.strict = strict
        self.form_data = deepcopy(form_data)

    """
    Add a validator for a form field defined by name. title will be
    used in error messages
    """
    def add(self, name, validator, **kwargs):
        if isinstance(validator, (list, tuple)):
            for v in validator:
                self.add(name, v, **kwargs)
            return

        if not isinstance(validator, Validator):
            raise ValidatorTypeError('invalid validator for field %s: %s' %
                    (name, str(validator)))

        if not name in self.fields:
            title = kwargs.get('title', name)
            stop = kwargs.get('stop_on_error', False)
            self.fields[name] = {
                'stop_on_error': stop,
                'title': title,
                'validators': []
            }

        self.fields[name]['validators'].append(validator)

    def validate(self):
        for name in self.fields:
            title = self.fields[name].get('title')

            if self.strict and not name in self.form_data:
                raise ValidationError('%s not found in form data' % title)

            for v in self.fields[name]['validators']:
                try:
                    value = ''
                    key_exists = True if name in self.form_data else False

                    if key_exists:
                        value = self.form_data[name]

                    # the validator is allowed to transform the form_data, e.g.
                    # perform type conversions if needed, or normalize values
                    value = v.validate(name, title, value)

                    if key_exists:
                        self.form_data[name] = value
                except ValidationError as e:
                    # it is sufficient to add the first error of each field to
                    # the error list
                    self.errors.append(str(e))
                    if self.fields[name].get('stop_on_error'):
                        return False
                    break

        return self.is_valid()

    def is_valid(self):
        return len(self.errors) == 0

    def get_errors(self):
        return self.errors

    def get_form_data(self):
        return self.form_data


if __name__ == '__main__':

    form_data = {
        'field1': 1,
        'field2': "10",
        'field3': "3.5",
        'field4': "adfwe3.5",
        'field10': "-0.5, 1.5",
        'field11': "",
        'field12': "",
        'field13': "sdf",
        'field14': "lat",
        'field15': "p[0] + p[1] * x",
        'field16': "10 < x < 20",
        'field17': "1.5, 2,6",
    }

    v = FormDataValidator(form_data)
    v.add('field1', Int(), field_title='Feld1')
    v.add('field1', Float())
    v.add('field2', IntRange(0, 5), field_title='Feld2')
    v.add('field3', FloatRange(0, 10), field_title='Feld3')
    v.add('field4', Float())
    v.add('field5', Float())
    v.add('field10', Regexp('^\s*[-+]?[0-9]*\.?[0-9]+\s*,\s*[-+]?[0-9]*\.?[0-9]+\s*$'))
    v.add('field11', NotEmpty())
    v.add('field12', [NotEmpty(), Float()])
    v.add('field13', [NotEmpty(), Regexp('^(lat|lon)$', regexp_desc='something like e.g. lat, lon, latitude or longitude')])
    v.add('field14', OneOf(['lat1', 'lon']))
    v.add('field15', Expression(transform=True, prefix='lambda x,*p:'))
    var = 'x'
    val = 15
    v.add('field16', Expression(args={var: val}))
    v.add('field2', IntRange(1, 2, exclude_min=True, allow_empty=True))
    v.add('field17', Regexp('^(\s*[-+]?[0-9]*\.?[0-9]+\s*,)*(\s*[-+]?[0-9]*\.?[0-9]+\s*)$'))

    v.validate()

    if v.is_valid():
        print 'form data valid'
    else:
        print 'errors:'
        print v.get_errors()

    print 'original:'
    print form_data
    print 'copy:'
    print v.get_form_data()
