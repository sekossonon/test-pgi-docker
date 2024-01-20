# -*- coding: utf-8 -*-

from odoo.tests import common
from odoo.exceptions import ValidationError


class TestPartnerSearch(common.SingleTransactionCase):
    """ validate result order
    """

    @classmethod
    def setUpClass(self):
        super(TestPartnerSearch, self).setUpClass()
        self.ResPartner = self.env['res.partner']
        # QQ is not present in demo data
        self.ref_qqt = self.ResPartner.create(dict(ref='qqt', name='Q=Q=T'))
        self.ref_aqqt = self.ResPartner.create(dict(ref='aqqt', name='A=Q=Q=T'))
        self.ref_bqqt_name = self.ResPartner.create(dict(ref='bqqt', name='B=Q=Q='))
        self.ref_qqqt = self.ResPartner.create(dict(ref='qqqt', name='Q=Q=Q=T'))
        self.ref_yqqt_ref = self.ResPartner.create(dict(ref='tqqy', name='Y=Q=Q=T'))
        self.ref_zqqt = self.ResPartner.create(dict(ref='zqqt', name='Z=Q=Q=T'))
        self.ref_name_qq = self.ResPartner.create(dict(ref='bb', name='qq'))

    def test_search_exact_ref(self):
        dataset = self.ResPartner.name_search('qqt')
        expected = [
            # exact ref
            (self.ref_qqt.id, u'qqt, Q=Q=T'),
            # ref match, sorted by display_name
            (self.ref_aqqt.id, u'aqqt, A=Q=Q=T'),
            (self.ref_bqqt_name.id, u'bqqt, B=Q=Q='),
            (self.ref_qqqt.id, u'qqqt, Q=Q=Q=T'),
            (self.ref_zqqt.id, u'zqqt, Z=Q=Q=T'),
            # tqqy should not be found
            # bb should not be found
        ]
        self.assertEqual(dataset, expected)

    def test_search_partial_ref(self):
        dataset = self.ResPartner.name_search('qq')
        expected = [
            # ref match, sorted by display_name
            (self.ref_aqqt.id, u'aqqt, A=Q=Q=T'),
            (self.ref_bqqt_name.id, u'bqqt, B=Q=Q='),
            (self.ref_qqqt.id, u'qqqt, Q=Q=Q=T'),
            (self.ref_qqt.id, u'qqt, Q=Q=T'),
            (self.ref_yqqt_ref.id, u'tqqy, Y=Q=Q=T'),
            (self.ref_zqqt.id, u'zqqt, Z=Q=Q=T'),
            # name match
            (self.ref_name_qq.id, u'bb, qq'),
        ]
        self.assertEqual(dataset, expected)

    def test_search_start_name(self):
        dataset = self.ResPartner.name_search('Q=Q')
        expected = [
            # name start match, sorted by display_name
            (self.ref_qqqt.id, u'qqqt, Q=Q=Q=T'),
            (self.ref_qqt.id, u'qqt, Q=Q=T'),
            # sorted by display_name
            (self.ref_aqqt.id, u'aqqt, A=Q=Q=T'),
            (self.ref_bqqt_name.id, u'bqqt, B=Q=Q='),
            (self.ref_yqqt_ref.id, u'tqqy, Y=Q=Q=T'),
            (self.ref_zqqt.id, u'zqqt, Z=Q=Q=T'),
            # bb should not be found
        ]
        self.assertEqual(dataset, expected)

    def test_search_partial_name(self):
        # for some reason 'Q_T' will find 'bqqt, B_Q_Q_'
        # no issue with 'Q=T'
        dataset = self.ResPartner.name_search('Q=T')
        expected = [
            # sorted by display_name only
            (self.ref_aqqt.id, u'aqqt, A=Q=Q=T'),
            (self.ref_qqqt.id, u'qqqt, Q=Q=Q=T'),
            (self.ref_qqt.id, u'qqt, Q=Q=T'),
            (self.ref_yqqt_ref.id, u'tqqy, Y=Q=Q=T'),
            (self.ref_zqqt.id, u'zqqt, Z=Q=Q=T'),
            # bqqt should not be found
            # bb should not be found
        ]
        self.assertEqual(dataset, expected)


class TestPartner(common.TransactionCase):

    def test_check_unique_insensitive(self):
        """ module should reject ref code which differ only by case (qq vs QQ)
        """
        self.env['res.partner'].create(dict(ref='qq', name='first qq'))
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create(dict(ref='QQ', name='second qq'))

    def test_copy(self):
        """ module should append '(copy)' to ref code
        """
        first = self.env['res.partner'].create(dict(ref='qq', name='first qq'))
        second = first.copy()
        self.assertEqual(second.ref, 'qq (copy)')

    def test_cover_name_get(self):
        """ improve name_get() coverage for duplicated code
        """
        company = self.env['res.partner'].create(dict(name='company'))
        sub1 = self.env['res.partner'].create(dict(
            parent_id=company.id, type='other', email='other@example.com'))
        res = sub1.with_context(show_address=True, show_email=True).name_get()
        expected = [(sub1.id, u'Other Address\n  \n <other@example.com>')]
        self.assertEqual(res, expected)

    def test_cover_name_get_address_only(self):
        """ improve name_get() coverage for duplicated code
        """
        company = self.env['res.partner'].create(dict(name='company'))
        sub1 = self.env['res.partner'].create(dict(parent_id=company.id, type='other'))
        res = sub1.with_context(show_address_only=True, html_format=True).name_get()
        expected = [(sub1.id, u'<br/>  <br/>')]
        self.assertEqual(res, expected)
