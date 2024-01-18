# -*- coding: utf-8 -*-
# flake8: noqa F841

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common

from .common import BaseTimesheetTestCase


def overlap_pair(entry):
    return entry.overlap_minute, entry.overlap


class TestQuickOverlap(BaseTimesheetTestCase):
    def setUp(self):
        super().setUp()
        #
        self.env.user.tz = 'UTC'
        self.ts8_17 = self._create_quick_entry(8, 17)
        self.ts9_11 = self._create_quick_entry(9, 11)
        self.ts10_12 = self._create_quick_entry(10, 12)
        self.ts11_12 = self._create_quick_entry(11, 12)
        self.ts13_16 = self._create_quick_entry(13, 16)
        self.ts14_15 = self._create_quick_entry(14, 15)

    def test_start_end_iterate(self):
        """ start/end time are returned in order
        """
        recordset = self.ts8_17 + self.ts9_11 + self.ts10_12
        output = [x for x in recordset.start_end_iterate()]
        timelist = [next_minute / 60
                    for active_records, next_record, next_minute, previous_minute, when in output]
        expected = [8, 9, 10, 11, 12, 17]
        self.assertEqual(timelist, expected)

    def test_start_end_iterate_close_before_open(self):
        """ end time is returned before start time when equal
        """
        recordset = self.ts9_11 + self.ts10_12 + self.ts11_12
        output = [x for x in recordset.start_end_iterate()]
        timelist = [(next_minute / 60, when)
                    for active_records, next_record, next_minute, previous_minute, when in output]
        expected = [(11, 'end_date'), (11, 'start_date')]
        self.assertEqual(timelist[2:4], expected)

    def test_incomplete(self):
        """ nothing done if duration is not set
        """
        self.ts9_11.duration_minute = 0 * 60
        self.ts9_11.analyze_one_day()
        self.assertEqual(overlap_pair(self.ts9_11), (0, False))

    def test_single(self):
        recordset = self.ts9_11
        recordset.analyze_one_day()
        self.assertEqual(overlap_pair(self.ts9_11), (0, 'single'))

    def test_single_underflow(self):
        """ solo entry handled
        """
        recordset = self.ts9_11
        self.ts9_11.duration_minute = 0.5 * 60
        recordset.analyze_one_day()
        self.assertEqual(overlap_pair(self.ts9_11), (-90, 'underflow'))

    def test_inactive_underflow(self):
        """ inactive entry is cleared
        """
        recordset = self.ts9_11 + self.ts10_12
        self.ts9_11.duration_minute = 0.5 * 60
        self.ts10_12.duration_minute = 0
        recordset.analyze_one_day()
        self.assertEqual(overlap_pair(self.ts9_11), (-90, 'underflow'))
        self.assertEqual(overlap_pair(self.ts10_12), (0, False))

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
        self.ts9_11.duration_minute = 0.5 * 60
        self.ts10_12.duration_minute = 1.5 * 60
        self.ts11_12.duration_minute = 1.0 * 60
        recordset.analyze_one_day()
        self.assertEqual(overlap_pair(self.ts9_11), (-30, 'underflow'))
        self.assertEqual(overlap_pair(self.ts10_12), (0, 'full'))
        self.assertEqual(overlap_pair(self.ts11_12), (30, 'overflow'))

    def test_underflow_last(self):
        """ short on last timeslice, no leak from earlier
        """
        recordset = self.ts9_11 + self.ts10_12 + self.ts11_12
        self.ts9_11.duration_minute = 2.5 * 60
        self.ts10_12.duration_minute = 0.25 * 60
        self.ts11_12.duration_minute = 0.25 * 60
        recordset.analyze_one_day()
        # all overflow taken by second entry
        self.assertEqual(overlap_pair(self.ts9_11), (30, 'overflow'))
        self.assertEqual(overlap_pair(self.ts10_12), (-30, 'underflow'))
        self.assertEqual(overlap_pair(self.ts11_12), (0, 'full'))

    def test_underflow_double_last(self):
        """ short on last timeslice, no leak from earlier
        """
        recordset = self.ts9_11 + self.ts10_12 + self.ts8_17
        self.ts9_11.duration_minute = 2.5 * 60
        self.ts10_12.duration_minute = 0.25 * 60
        self.ts8_17.duration_minute = 1.25 * 60
        recordset.analyze_one_day()
        # excess overflow into last
        self.assertEqual(overlap_pair(self.ts9_11), (30, 'overflow'))
        self.assertEqual(overlap_pair(self.ts10_12), (-30, 'underflow'))
        self.assertEqual(overlap_pair(self.ts8_17), (-300, 'underflow'))

    def test_underflow_early(self):
        """ good on last timeslice, no leak to earlier
        """
        recordset = self.ts9_11 + self.ts10_12 + self.ts11_12
        self.ts9_11.duration_minute = 1.25 * 60
        self.ts10_12.duration_minute = 0.25 * 60
        self.ts11_12.duration_minute = 1.0 * 60
        recordset.analyze_one_day()
        # all overflow taken by second entry
        # self.assertEqual(overlap_pair(self.ts9_11), (0, 'full'))
        self.assertEqual(overlap_pair(self.ts9_11), (-30, 'underflow'))
        self.assertEqual(overlap_pair(self.ts10_12), (0, 'full'))
        self.assertEqual(overlap_pair(self.ts11_12), (0, 'full'))

    def test_with_minutes(self):
        """ failed in manual tests
        """
        ts10_15 = self._create_quick_entry('10:00', '15:55', duration=2.5, name='ts10_15')
        ts12_13 = self._create_quick_entry('12:22', '13:33', duration=0.5, name='ts12_13')
        recordset = ts10_15 + ts12_13
        recordset.analyze_one_day()
        self.assertEqual(overlap_pair(ts10_15), (-142, 'underflow'))
        self.assertEqual(overlap_pair(ts12_13), (-33, 'underflow'))
