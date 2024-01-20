# coding: utf-8
import unicodedata

import pymssql

from odoo import api, fields, models, _
from odoo.tools import config
from .res_config import get_connection_kwargs


def odoo_is_in_test_mode():
    """Help detect if odoo is run in test mode"""
    params_list = ['test_file', 'test_tags', 'test_enable']
    return any([config.options.get(p) for p in params_list]) and config.options.get('stop_after_init')

# res_partner does not map directly to TS tables
# for instance, address/email/phone are in separate TS tables
#
# because TS is in maintenance mode, the requirements are reduced.
# we update TS.Contact from Odoo.res_partner
# we insure Odoo.res_partner with ref have a matching TS.Contact
#
# mapping between Odoo and TS is done with Odoo.id == TS.OdooID
# missing entries are created only when record.is_primary_contact() is True

# complications:
# - sub-partners are passed as command, as single create/write may affect many records
# - write() may create/remove sub-partner


class Mapping(object):
    """ Mapping between Odoo and Timesheet """

    def __init__(self, odoo, uranos, maxlen=None):
        self.odoo = odoo
        self.uranos = uranos
        self.maxlen = maxlen

    def __str__(self):
        return '<{}>'.format(self.odoo)

    def truncate(self, vals):
        full = vals[self.odoo]
        if isinstance(full, str):
            if self.maxlen:
                full = full[:self.maxlen]
            return unicodedata.normalize('NFKD', full).encode(encoding='ascii', errors='ignore')
            # patch: ignore accents
            # encoding here cause exception at execute()
            # encoding at connection puts chinese strings in database
        elif full is False:
            return None
        elif isinstance(full, models.Model) and not full:
            return None
        else:
            return full


def get_new_id(cursor):
    cursor.execute("Select SCOPE_IDENTITY() as ident")
    ident = cursor.fetchone()

    return ident['ident']


def sql_insert(cursor, table, columns, vals):
    cmd = 'INSERT INTO dbo.{} ({}) VALUES ({})'.format(
        table,
        ','.join(col.uranos for col in columns),
        ','.join(['%s'] * len(columns)))
    args = tuple(col.truncate(vals) for col in columns)
    # print cmd % args
    cursor.execute(cmd, args)


def sql_update(cursor, table, columns, vals, where):
    cmd = 'UPDATE dbo.{} SET {} {}'.format(
        table,
        ','.join('{} = %s'.format(col.uranos) for col in columns),
        where)
    args = tuple(col.truncate(vals) for col in columns)
    # print cmd % args
    cursor.execute(cmd, args)


def sql_contact(cursor, vals, record):
    """ Create / update entry

    Updates changes to Contact entry. Creates primary contact if missing.
    :param record: user or partner
    """
    mapping = [
        Mapping('firstname', 'FirstName', 50),
        Mapping('lastname', 'LastName', 200),
        Mapping('active', 'statusID', None),
        Mapping('website', 'WebAddress', 50),
        Mapping('comment', 'Remark', None),
        Mapping('lang', 'Language', 1),
        Mapping('ref', 'Code', 10),
        Mapping('warning', 'Warning', None),
        Mapping('bill_to_id', 'BillToID', None),
        Mapping('security_level', 'SecurityLevel', None),
        Mapping('min_billing_time', 'MinBillingTime', None),
        # TS-only field
        Mapping('OdooID', 'OdooID', None),
    ]
    pk_contact = record.pk_contact

    # adjust vals
    if not pk_contact and record.is_primary_contact():
        # primary contact is missing, will create below
        # vals is sparse on update, take data from record
        vals = {k: record[k] for k in (col.odoo for col in mapping) if k in record}
    if 'name' in vals and 'lastname' not in vals:
        # name has same mapping as lastname
        vals['lastname'] = vals['name']
    if 'active' in vals:
        # TS.statusID 0 = active, TS.statusID 1 = inactive
        vals['active'] = 1 - vals['active']
    if 'bill_to_id' in vals:
        # map to PK_Contact
        vals['bill_to_id'] = record.bill_to_id.pk_contact if record.bill_to_id else None

    columns = [col for col in mapping if col.odoo in vals]
    if not pk_contact and record.is_primary_contact():
        # must create primary contact if missing
        vals = dict(vals, OdooID=record._get_odoo_id())
        columns = [col for col in mapping if col.odoo in vals]
        sql_insert(cursor, 'Contact', columns, vals)
        pk_contact = get_new_id(cursor)
        record.with_context(set_pk_contact=True).pk_contact = pk_contact
    elif columns and pk_contact:
        where = 'WHERE PK_Contact = {}'.format(pk_contact)
        sql_update(cursor, 'Contact', columns, vals, where)

    if pk_contact:
        # fix roles
        sql_role(cursor, vals, record, pk_contact, record.customer, 1)
        sql_role(cursor, vals, record, pk_contact, record.supplier, 3)
        # fix employee + role
        sql_roleemployee(cursor, vals, record, pk_contact)


def sql_role(cursor, vals, record, pk_contact, create, role_id):
    """ delete/insert role m2m as required

    also insert customer role as required
    """
    cursor.execute(
        'SELECT ContactID FROM dbo.R_MultiContact_TypeRole WHERE ContactID=%s and TypeRoleID=%s',
        (pk_contact, role_id))
    found = cursor.fetchone()

    if found and not create:
        cursor.execute(
            'DELETE FROM dbo.R_MultiContact_TypeRole WHERE ContactID=%d and TypeRoleID=%d',
            (pk_contact, role_id))
    elif not found and create:
        cursor.execute(
            'INSERT INTO dbo.R_MultiContact_TypeRole (ContactID, TypeRoleID) VALUES (%s, %s)',
            (pk_contact, role_id))

        if role_id == 1:
            # create empty role customer if not present
            cursor.execute(
                'SELECT ContactID FROM dbo.RoleCustomer WHERE ContactID=%s',
                (pk_contact,))
            found = cursor.fetchone()

            if not found:
                cursor.execute(
                    'INSERT INTO dbo.RoleCustomer (ContactID, PriceListID) VALUES (%s, %s)',
                    (pk_contact, 27))


def sql_roleemployee(cursor, vals, record, pk_contact):
    """ update employee role

    also insert role m2m
    """
    mapping = [
        Mapping('privilege', 'PrivilegeID', None),
        Mapping('contact_group', 'Group_ContactId', None),
        Mapping('password', 'password', 50),
        Mapping('clearance_level', 'ClearanceLevel', None),
        # TS-only field
        Mapping('PK_Contact', 'ContactID', None),
    ]
    cursor.execute(
        'SELECT PK_RoleEmployee FROM dbo.RoleEmployee WHERE ContactID=%s',
        (pk_contact,))
    found = cursor.fetchone()
    pk_roleemployee = found and found.get('PK_RoleEmployee')

    columns = [col for col in mapping if col.odoo in vals]
    if not columns:
        return

    if not pk_roleemployee:
        # role employee is never deleted
        sql_role(cursor, vals, record, pk_contact, True, 2)
        # create role employee
        vals = dict(vals, PK_Contact=pk_contact)
        columns = [col for col in mapping if col.odoo in vals]
        sql_insert(cursor, 'RoleEmployee', columns, vals)
    else:
        where = 'WHERE PK_RoleEmployee = {}'.format(pk_roleemployee)
        sql_update(cursor, 'RoleEmployee', columns, vals, where)


def process_child_command(cursor, record, child_command):
    """ also process sub-partners that are passed as commands """
    _cmd, _id, _vals = child_command
    if _cmd == 0:  # create
        # TODO BUG: cannot link to child_ids
        # child_record = record.child_ids.filtered(lambda child: child.id == _vals['id'])
        # sql_contact(cursor, _vals, child_record)
        pass
    elif _cmd == 1:  # update
        child_record = record.child_ids.filtered(lambda child: child.id == _id)
        sql_contact(cursor, _vals, child_record)
    elif _cmd == 2:  # delete
        pass
    elif _cmd == 3:  # disconnect
        pass
    elif _cmd == 4:  # connect
        pass
    elif _cmd == 5:  # disconnect all
        pass
    elif _cmd == 6:  # reconnect all
        pass
    pass


def update_ts(record, vals):
    # prevent this method to run if running tests
    if odoo_is_in_test_mode():
        return

    connection_kwargs = get_connection_kwargs(record)
    if connection_kwargs:
        # try:
        with pymssql.connect(**connection_kwargs) as conn:
            cursor = conn.cursor()
            #
            sql_contact(cursor, vals, record)
            # only partner has child_ids
            for child_command in vals.get('child_ids', []):
                process_child_command(cursor, record, child_command)
            #
            conn.commit()
        # except Exception, ex:
        #     raise Warning(ex)


class ClientCategory(models.Model):
    _name = 'res.partner.microcom.category'
    _description = 'Partner Category'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')


class Partner(models.Model):
    _inherit = 'res.partner'

    client_category_id = fields.Many2one('res.partner.microcom.category', string='Client Category')
    # dummy fields for initial mapping
    lv_address_id = fields.Integer()
    lv_email_id = fields.Integer()
    lv_phone_id = fields.Integer()
    pk_contact = fields.Integer(copy=False)

    def is_primary_contact(self):
        """ partners are copied to TS if they have an internal reference
        """
        self.ensure_one()
        return bool(self.ref)

    def _get_odoo_id(self):
        self.ensure_one()
        return self.id

    def write(self, vals):
        super(Partner, self).write(vals)
        # stop recursion
        if 'set_pk_contact' not in self.env.context:
            for record in self:
                update_ts(record, vals)
        return True

    # Fixes: WARNING odoo.api.create: The model odoo.addons.uranos_ts.res_partner is not overriding the create method in batch
    @api.model_create_multi
    def create(self, vals_list):
        records = super(Partner, self).create(vals_list)
        for record, vals in zip(records, vals_list):
            update_ts(record, vals)
        return records


class ResPartnerDepartment(models.Model):
    _inherit = "res.partner.department"

    partner_ids = fields.One2many('res.partner', 'department_id')
    parent_path = fields.Char(unaccent=False) # parent_path field on model 'res.partner.department' should have unaccent disabled. Add `unaccent=False` to the field definition.


class User(models.Model):
    _inherit = 'res.users'

    def is_primary_contact(self):
        """ users are always copied to TS
        """
        return True

    def _get_odoo_id(self):
        self.ensure_one()
        return self.partner_id.id

    def write(self, vals):
        super(User, self).write(vals)
        # stop recursion
        if 'set_pk_contact' not in self.env.context:
            for record in self:
                update_ts(record, vals)
        return True

    # Fixes: WARNING odoo.api.create: The model odoo.addons.uranos_ts.res_partner is not overriding the create method in batch
    @api.model_create_multi
    def create(self, vals_list):
        records = super(User, self).create(vals_list)
        for record, vals in zip(records, vals_list):
            update_ts(record, vals)
        return records
