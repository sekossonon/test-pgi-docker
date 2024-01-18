# -*- coding: utf-8 -*-
# flake8: noqa F841

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common

from .common import BaseTimesheetTestCase


class TestEvent(BaseTimesheetTestCase):
    def setUp(self):
        super().setUp()

    def _create_event(self, start_time, end_time, name=None, start_date=None, **kwargs):
        if name is None:
            name = 'ev{}_{}'.format(start_time, end_time)
        #
        start_time = self._time_as_minute(start_time)
        end_time = self._time_as_minute(end_time)

        quick_event = self.env['microcom.timesheet.event'].create({
            'name': name,
            'start_date': start_date or fields.Date.context_today(self.env['microcom.timesheet.event']),
            'start_minute': start_time,
            'end_minute': end_time,
            **kwargs
        })
        # disable immediate calculation
        return quick_event.with_context(updating_overlap=True)

    def _calculate_duration_minutes(self, event):
        # TODO react when siblings are changed
        # we need to force update because depends() is incomplete
        event._compute_duration_minute()
        return event.duration_minute

    def test_calculate_duration_minute(self):
        event_1 = self._create_event(start_time='8:00', end_time='12:00')
        event1_ts1 = self._create_quick_entry(start_time='8:00', end_time="12:00", event_id=event_1.id)

        computed_duration = self.convert_minute2char(self._calculate_duration_minutes(event_1))
        expected_duration = '4:00'
        self.assertEqual(
            computed_duration, expected_duration,
            """Given an event(8:00-12:00) and a ts record(8:00-12:00) of that event
                When calculating duration of the event
                Then we should have 4:00 as result
            """
        )

        event1_ts2 = self._create_quick_entry(start_time='9:30', end_time="10:00", event_id=event_1.id)
        computed_duration = self.convert_minute2char(self._calculate_duration_minutes(event_1))
        expected_duration = '4:00'
        self.assertEqual(
            computed_duration, expected_duration,
            f"""Given an event_1 (8:00-12:00) and the following ts records
                    | name | start | end  | event  |
                    --------------------------------
                    |ts1   |8:00   |12:00 | event_1|
                    -------------------------------|
                    |ts2   |9:30   |10:00 | event_1|
                When calculating duration of the event 1
                Then we should have {expected_duration} as result
            """
        )

        event_2 = self._create_event(start_time='9:30', end_time='10:00')
        event2_ts1 = self._create_quick_entry(start_time='9:30', end_time="10:00", event_id=event_2.id)
        computed_duration = self.convert_minute2char(self._calculate_duration_minutes(event_1))
        expected_duration = '3:30'
        self.assertEqual(
            computed_duration, expected_duration,
            f"""Given event_1(8:00-12:00) and event_2(9:30-10:00) and the following ts records
                    | name | start | end  | event  |
                    |------+-------+------+--------|
                    |ts1   |8:00   |12:00 | event 1|
                    |ts2   |9:30   |10:00 | event 2|
                When calculating duration of the event 1
                Then we should have {expected_duration} as result
            """
        )

        event_3 = self._create_event(start_time='11:30', end_time='12:00')
        event3_ts1 = self._create_quick_entry(start_time='11:30', end_time="12:00", event_id=event_3.id)
        computed_duration = self.convert_minute2char(self._calculate_duration_minutes(event_1))
        expected_duration = '3:00'
        self.assertEqual(
            computed_duration, expected_duration,
            f"""Given event_1(8:00-12:00) and event_2(9:30-10:00), event_3(11:30-12:00) and the following ts records
                            | name | start | end  | event  |
                            |------+-------+------+--------|
                            |ts1   |8:00   |12:00 | event 1|
                            |ts2   |9:30   |10:00 | event 2|
                            |ts2   |11:30  |12:00 | event 3|
                        When calculating duration of the event 1
                        Then we should have {expected_duration} as result
                    """
        )
