# -*- coding: utf-8 -*-
# flake8: noqa F841

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common


def overlap_pair(entry):
    return entry.overlap_minute, entry.overlap


class TestActionOverlap(common.TransactionCase):
    def setUp(self):
        super().setUp()
        #
        self.env.user.tz = 'UTC'
        self.ts8_17 = self._create_action_entry(8, 17)
        self.ts9_11 = self._create_action_entry(9, 11)
        self.ts10_12 = self._create_action_entry(10, 12)
        self.ts11_12 = self._create_action_entry(11, 12)
        self.ts13_16 = self._create_action_entry(13, 16)
        self.ts14_15 = self._create_action_entry(14, 15)

    def _create_action_entry(self, start_time, end_time, unit_amount=None, name=None):
        if name is None:
            name = 'ts{}_{}'.format(start_time, end_time)
        #
        if type(start_time) == str and ':' in start_time:
            start_hour, start_minute = start_time.split(':')
            start_time = int(start_hour) * 60 + int(start_minute)
        else:
            start_time = int(start_time) * 60
        #
        if type(end_time) == str and ':' in end_time:
            end_hour, end_minute = end_time.split(':')
            end_time = int(end_hour) * 60 + int(end_minute)
        else:
            end_time = int(end_time) * 60
        #
        if unit_amount is None:
            unit_amount = end_time - start_time
        else:
            unit_amount *= 60
        event_id = self.env['uranos.event'].create({
            'date_start_event': fields.Date.today(),
            'time_start_event': start_time,
            'time_end_event': end_time,
        })
        billing_id = self.env['uranos.billing'].create({
            'billing_time': unit_amount,
        })
        action_id = self.env['uranos.action'].create({
            'event_id': event_id.id,
            'billing_id': billing_id.id,
            'name': name,
            'overlap': False,
            'overlap_minute': -99,
        })
        return action_id

    def test_start_end_iterate(self):
        """ start/end time are returned in order
        """
        recordset = self.ts8_17 + self.ts9_11 + self.ts10_12
        output = [x for x in recordset.start_end_iterate()]
        timelist = [next_datetime.hour
                    for active_records, next_record, next_datetime, previous_datetime, when in output]
        expected = [8, 9, 10, 11, 12, 17]
        self.assertEqual(timelist, expected)

    def test_start_end_iterate_close_before_open(self):
        """ end time is returned before start time when equal
        """
        recordset = self.ts9_11 + self.ts10_12 + self.ts11_12
        output = [x for x in recordset.start_end_iterate()]
        timelist = [(next_datetime.hour, when)
                    for active_records, next_record, next_datetime, previous_datetime, when in output]
        expected = [(11, 'end_date'), (11, 'start_date')]
        self.assertEqual(timelist[2:4], expected)

    def test_incomplete(self):
        """ nothing done if duration is not set
        """
        self.ts9_11.billing_id.billing_time = 0 * 60
        self.ts9_11.analyze_one_day()
        self.assertFalse(self.ts9_11.overlap)

    def test_no_overlap(self):
        """ disjoint events treated separately
        """
        recordset = self.ts9_11 + self.ts11_12 + self.ts14_15
        recordset.analyze_one_day()
        self.assertEqual(overlap_pair(self.ts9_11), (0, 'single'))
        self.assertEqual(overlap_pair(self.ts11_12), (0, 'single'))
        self.assertEqual(overlap_pair(self.ts14_15), (0, 'single'))

    def test_overflow(self):
        """ max duration events
        """
        recordset = self.ts9_11 + self.ts10_12 + self.ts11_12
        recordset.analyze_one_day()
        self.assertEqual(overlap_pair(self.ts9_11), (0, 'full'))
        self.assertEqual(overlap_pair(self.ts10_12), (60, 'overflow'))
        self.assertEqual(overlap_pair(self.ts11_12), (60, 'overflow'))

    def test_underflow_first(self):
        """ short on first timeslice, no leak from later
        """
        recordset = self.ts9_11 + self.ts10_12 + self.ts11_12
        self.ts9_11.billing_id.billing_time = 0.5 * 60
        self.ts10_12.billing_id.billing_time = 1.5 * 60
        self.ts11_12.billing_id.billing_time = 1.0 * 60
        recordset.analyze_one_day()
        self.assertEqual(overlap_pair(self.ts9_11), (-30, 'underflow'))
        self.assertEqual(overlap_pair(self.ts10_12), (0, 'full'))
        self.assertEqual(overlap_pair(self.ts11_12), (30, 'overflow'))

    def test_underflow_last(self):
        """ short on last timeslice, no leak from earlier
        """
        recordset = self.ts9_11 + self.ts10_12 + self.ts11_12
        self.ts9_11.billing_id.billing_time = 2.5 * 60
        self.ts10_12.billing_id.billing_time = 0.25 * 60
        self.ts11_12.billing_id.billing_time = 0.25 * 60
        recordset.analyze_one_day()
        # all overflow taken by second entry
        self.assertEqual(overlap_pair(self.ts9_11), (30, 'overflow'))
        self.assertEqual(overlap_pair(self.ts10_12), (-30, 'underflow'))
        self.assertEqual(overlap_pair(self.ts11_12), (0, 'full'))

    def test_underflow_double_last(self):
        """ short on last timeslice, no leak from earlier
        """
        recordset = self.ts9_11 + self.ts10_12 + self.ts8_17
        self.ts9_11.billing_id.billing_time = 2.5 * 60
        self.ts10_12.billing_id.billing_time = 0.25 * 60
        self.ts8_17.billing_id.billing_time = 1.25 * 60
        recordset.analyze_one_day()
        # excess overflow into last
        self.assertEqual(overlap_pair(self.ts9_11), (30, 'overflow'))
        self.assertEqual(overlap_pair(self.ts10_12), (-30, 'underflow'))
        self.assertEqual(overlap_pair(self.ts8_17), (-300, 'underflow'))

    def test_underflow_early(self):
        """ good on last timeslice, no leak to earlier
        """
        recordset = self.ts9_11 + self.ts10_12 + self.ts11_12
        self.ts9_11.billing_id.billing_time = 1.25 * 60
        self.ts10_12.billing_id.billing_time = 0.25 * 60
        self.ts11_12.billing_id.billing_time = 1.0 * 60
        recordset.analyze_one_day()
        # all overflow taken by second entry
        # self.assertEqual(overlap_pair(self.ts9_11), (0, 'full'))
        self.assertEqual(overlap_pair(self.ts9_11), (-30, 'underflow'))
        self.assertEqual(overlap_pair(self.ts10_12), (0, 'full'))
        self.assertEqual(overlap_pair(self.ts11_12), (0, 'full'))

    def test_with_minutes(self):
        """ failed in manual tests
        """
        ts10_15 = self._create_action_entry('10:00', '15:55', unit_amount=2.5, name='ts10_15')
        ts12_13 = self._create_action_entry('12:22', '13:33', unit_amount=0.5, name='ts12_13')
        recordset = ts10_15 + ts12_13
        recordset.analyze_one_day()
        self.assertEqual(overlap_pair(ts10_15), (-142, 'underflow'))
        self.assertEqual(overlap_pair(ts12_13), (-33, 'underflow'))
