# -*- coding: utf-8 -*-
from datetime import datetime

from odoo.tests import common

from odoo.addons.work_anniversary_auto_emails.models import work_anniversary_check


class testWorkAnniversaryCheck(common.TransactionCase):

    def setUp(self):
        super(testWorkAnniversaryCheck, self).setUp()
        self.env['res.users'].create(
            {'name': 'Jonny Bravo', 'hire_date': '2010-08-10', 'login': 1})
        self.env['res.users'].create(
            {'name': 'Harry Potter', 'hire_date': '2000-02-29', 'login': 2})
        self.env['res.users'].create(
            {'name': 'Mario Bros', 'hire_date': '2010-02-28', 'login': 3})

    def test_hired_date(self):
        date = datetime(2011, 8, 10)
        celebrated_partners_ids = work_anniversary_check.\
            get_users_celebrated_for_date(self, date)
        self.assertEqual(len(celebrated_partners_ids), 1, "not working")

    def test_hired_date_leap(self):
        date = datetime(2012, 2, 28)
        celebrated_partners_ids = work_anniversary_check. \
            get_users_celebrated_for_date(self, date)
        self.assertEqual(len(celebrated_partners_ids), 1,
                         "leap year not working")

    def test_hired_date_not_leap(self):
        date = datetime(2011, 2, 28)
        celebrated_partners_ids = work_anniversary_check. \
            get_users_celebrated_for_date(self, date)
        self.assertEqual(len(celebrated_partners_ids), 2,
                         "not leap year not working")
