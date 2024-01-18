# -*- coding: utf-8 -*-
# flake8: noqa F841

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common


class BaseTimesheetTestCase(common.TransactionCase):

    def _time_as_minute(self, value):
        """ convert string to integer minute if necessary
        """
        if type(value) == str and ':' in value:
            value_hour, value_minute = value.split(':')
            value = int(value_hour) * 60 + int(value_minute)
        else:
            value = int(value) * 60
        return value

    def _create_quick_entry(self, start_time, end_time, duration=None, name=None, **kwargs):
        if name is None:
            name = 'ts{}_{}'.format(start_time, end_time)
        #
        start_time = self._time_as_minute(start_time)
        end_time = self._time_as_minute(end_time)
        #
        if duration is None:
            duration = end_time - start_time
        else:
            duration *= 60
        quick_id = self.env['microcom.timesheet'].create({
            'name': name,
            'date': fields.Date.context_today(self.env['microcom.timesheet']),
            'start_minute': start_time,
            'end_minute': end_time,
            'duration_minute': duration,
            'overlap': False,
            'overlap_minute': -99,
            **kwargs
        })
        # disable immediate calculation
        return quick_id.with_context(updating_overlap=True)

    def convert_minute2char(self, minutes):
        return self.env['microcom.timesheet.calculations.mixin'].convert_minute2char(minutes)
