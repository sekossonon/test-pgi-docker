# -*- coding: utf-8 -*-

from odoo.tests import common


class TestUserSearch(common.SingleTransactionCase):
    """ validate result order
    """

    @classmethod
    def setUpClass(self):
        super(TestUserSearch, self).setUpClass()
        self.ResUser = self.env['res.users']
        # QQ is not present in demo data
        self.ref_qqt = self.ResUser.create(dict(ref='qqt', name='Q=Q=T', login='xxt'))
        self.ref_aqqt = self.ResUser.create(dict(ref='aqqt', name='A=Q=Q=T', login='axxt'))
        self.ref_bqqt_name = self.ResUser.create(dict(ref='bqqt', name='B=Q=Q=', login='bxxt'))
        self.ref_qqqt = self.ResUser.create(dict(ref='qqqt', name='Q=Q=Q=T', login='qxxt'))
        self.ref_yqqt_ref = self.ResUser.create(dict(ref='tqqy', name='Y=Q=Q=T', login='txxy'))
        self.ref_zqqt = self.ResUser.create(dict(ref='zqqt', name='Z=Q=Q=T', login='zxxt'))
        self.ref_name_qq = self.ResUser.create(dict(ref='bb', name='qq', login='bb'))

    def test_search_exact_ref(self):
        dataset = self.ResUser.name_search('qqt')
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
        dataset = self.ResUser.name_search('qq')
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
        dataset = self.ResUser.name_search('Q=Q')
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
        dataset = self.ResUser.name_search('Q=T')
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


class TestUser(common.TransactionCase):

    def test_onchange_email(self):
        user1 = self.env['res.users'].create(dict(ref='bb', name='user1', login='bb'))
        partner1 = self.env['res.partner'].create(dict(
            ref='zz', name='partner1', email='zz@example.com'))
        user1.partner_id = partner1
        self.assertEqual(user1.name, 'partner1')
        user1._onchange_partner_id()
        self.assertEqual(user1.login, 'zz@example.com')
