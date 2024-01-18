from odoo.tests import common
from datetime import datetime


class testBirthdayCheck(common.TransactionCase):

    def setUp(self):
        super(testBirthdayCheck, self).setUp()
        self.env['hr.employee'].create({'name': 'Jonny Bravo', 'birthday': '2010-08-10'})
        self.env['hr.employee'].create({'name': 'Harry Potter', 'birthday': '2010-08-10'})
        self.env['hr.employee'].create({'name': 'Mario Bros', 'birthday': '2008-02-29'})

    def test_birthdate_standard(self):
        date = datetime(2010, 8, 10)
        celebrated_partners = self.env['hr.employee'].get_partners_celebrated_for_date(date)
        self.assertEqual(len(celebrated_partners), 2, "not working")

    def test_birthdate_leap_year(self):
        date = datetime(2012, 2, 29)
        celebrated_partners = self.env['hr.employee'].get_partners_celebrated_for_date(date)
        self.assertEqual(len(celebrated_partners), 1, "leap year not working")

    def test_birthdate_not_leap_year(self):
        date = datetime(2011, 2, 28)
        celebrated_partners = self.env['hr.employee'].get_partners_celebrated_for_date(date)
        self.assertEqual(len(celebrated_partners), 1, "not leap year not working")
