# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.osv.expression import get_unaccent_wrapper
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    warning = fields.Text('Warning')
    bill_to_id = fields.Many2one('res.partner', 'Bill to')
    security_level = fields.Integer('Security Level', default=1)
    is_company = fields.Boolean(default=True)
    pk_contact = fields.Integer('PK_Contact')
    min_billing_time = fields.Selection(
        [('60', 'Zone 1 (1h)'), ('120', 'Zone 2 (2h)'), ('180', 'Zone-3 (3h)'), ('240', 'Zone-4 (4h)'), ('720', 'Zone-5 (12h)')],
        default='120', string="Min Billing Time")
    child_ids = fields.One2many(tracking=True)
    name = fields.Char(tracking=True)
    ref = fields.Char(tracking=True)
    type = fields.Selection(tracking=True)
    street = fields.Char(tracking=True)
    street2 = fields.Char(tracking=True)
    zip = fields.Char(tracking=True)
    city = fields.Char(tracking=True)
    email = fields.Char(tracking=True)
    phone = fields.Char(tracking=True)
    mobile = fields.Char(tracking=True)
    without_email_address = fields.Boolean(
        string='Without email',
        tracking=True
    )

    _sql_constraints = [
        ('code_unique', 'unique(ref)', 'The code already exists!'),
        ('pk_contact_unique', 'unique(pk_contact)', 'The pk_contact already exists!'),
    ]

    @api.depends('is_company', 'name', 'parent_id.name', 'type', 'company_name', 'ref')
    def _compute_display_name(self):
        """ override to add ref to dependencies
        """
        diff = dict(show_address=None, show_address_only=None, show_email=None)
        names = dict(self.with_context(**diff).name_get())
        for partner in self:
            partner.display_name = names.get(partner.id)

    @api.constrains('ref')
    def _check_unique_insensitive(self):
        """ validate that ref is unique, ignoring case (DJ == dj)
        """
        for partner in self:
            for similar_id in self.search([('ref', '=ilike', partner.ref)]):
                if similar_id != partner:
                    raise ValidationError(_('The code already exists!'))

    def name_get(self):
        """ prefix display_name with ref
        """
        res = []
        for partner in self:
            name = partner.name or ''

            if partner.company_name or partner.parent_id:
                if not name and partner.type in ['invoice', 'delivery', 'other']:
                    name = dict(self.fields_get(['type'])['type']['selection'])[partner.type]
                if not partner.is_company:
                    name = "%s, %s" % (partner.commercial_company_name or partner.parent_id.name, name)
            # ADDED START
            if partner.ref:
                name = "%s, %s" % (partner.ref, name)
            # ADDED END
            if self._context.get('show_address_only'):
                name = partner._display_address(without_company=True)
            if self._context.get('show_address'):
                name = name + "\n" + partner._display_address(without_company=True)
            name = name.replace('\n\n', '\n')
            name = name.replace('\n\n', '\n')
            if self._context.get('show_email') and partner.email:
                name = "%s <%s>" % (name, partner.email)
            if self._context.get('html_format'):
                name = name.replace('\n', '<br/>')
            res.append((partner.id, name))
        return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        """ sort ref matches first
        """
        if args is None:
            args = []
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            self.check_access_rights('read')
            where_query = self._where_calc(args)
            self._apply_ir_rules(where_query, 'read')
            from_clause, where_clause, where_clause_params = where_query.get_sql()
            where_str = where_clause and (" WHERE %s AND " % where_clause) or ' WHERE '

            # search on the name of the contacts and of its company
            search_name = name
            startby_name = name
            if operator in ('ilike', 'like'):
                search_name = '%%%s%%' % name
                startby_name = '%s%%' % name
            if operator in ('=ilike', '=like'):
                operator = operator[1:]

            unaccent = get_unaccent_wrapper(self.env.cr)

            # CHANGES: improving SQL sort order + where_clause_params + startby_name
            query = """SELECT id
                        FROM res_partner
                        {where} ({email} {operator} {percent}
                            OR {display_name} {operator} {percent}
                            OR {reference} {operator} {percent})
                            -- don't panic, trust postgres bitmap
                        ORDER BY
                            CASE WHEN {pref} ilike {percent} THEN 0 ELSE 1 END,
                            CASE WHEN {pref} {operator} %s THEN 0 ELSE 1 END,
                            CASE WHEN {pname} {operator} {percent} THEN 0 ELSE 1 END,
                            CASE WHEN {pname} {operator} {percent} THEN 0 ELSE 1 END,
                            {display_name} {operator} {percent} desc,
                            {display_name}
                    """.format(where=where_str,
                               operator=operator,
                               email=unaccent('email'),
                               pname=unaccent('res_partner.name'),
                               pref=unaccent('res_partner.ref'),
                               display_name=unaccent('display_name'),
                               reference=unaccent('ref'),
                               percent=unaccent('%s'))

            where_clause_params += [
                search_name, search_name, search_name,  # where clause
                name, search_name,  # ref exact/partial
                startby_name, search_name,  # name start/partial
                search_name  # display_name
            ]
            if limit:
                query += ' limit %s'
                where_clause_params.append(limit)
            self.env.cr.execute(query, where_clause_params)
            partner_ids = map(lambda x: x[0], self.env.cr.fetchall())

            if partner_ids:
                return self.browse(partner_ids).name_get()
            else:
                return []
        return super(ResPartner, self).name_search(name, args, operator=operator, limit=limit)

    def copy(self, default=None):
        """ mangle ref to keep unique
        """
        self.ensure_one()
        if self.ref:
            default = dict(default or {}, ref=_('%s (copy)') % self.ref)
        return super(ResPartner, self).copy(default)


class ResUsers(models.Model):
    _inherit = "res.users"

    privilege = fields.Selection([('1', 'Supervisor'), ('2', 'Proofreader')],  'Privilege')
    # These are string and not int because openerp consider 0 as False
    contact_group = fields.Selection(
        [('0', 'None'), ('547', 'PROGRAMMER GROUP'), ('548', 'DESIGNER GROUP'), ('563', 'TECHNICIAN GROUP')],
        'Group')
    clearance_level = fields.Integer('Clearance Level', default=1)

    _sql_constraints = [
        ('partner_id_unique', 'unique(partner_id)', 'You cannot have two users linked to the same partner !')
    ]

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """ link to an existing partner
        """
        # allows to transform a known partner into a user and reset its default login
        # later changes to email will not propagate to login
        self.login = self.partner_id.email

    def name_get(self):
        """ prefix display_name with ref
        """
        result = []
        for record in self:
            name = record.name
            # CHANGE START
            if record.ref:
                name = "%s, %s" % (record.ref, name)
            # CHANGE END
            result.append((record.id, name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """ sort ref matches first
        """
        if args is None:
            args = []
        users = self.browse()
        if name and operator in ['=', 'ilike']:
            users = self.search([('login', '=', name)] + args, limit=limit)
        if not users:
            users = self.name_search_sorted(name=name, args=args, operator=operator, limit=limit)
        return users.name_get()

    @api.model
    def name_search_sorted(self, name='', args=None, operator='ilike', limit=100):
        """ add custom order-by to execute() args
        """
        self.check_access_rights('read')

        query = self._where_calc(args)
        query.add_join(("res_users", "res_partner", "partner_id", "id", "partner_id"),
                       implicit=False, outer=False)
        self._apply_ir_rules(query, 'read')
        from_clause, where_clause, where_clause_params = query.get_sql()
        where_str = where_clause and (" WHERE %s AND " % where_clause) or ' WHERE '

        # search on the name of the contacts and of its company
        contains_name = name
        startsby_name = name
        if operator in ('ilike', 'like'):
            contains_name = '%' + name + '%'
            startsby_name = name + '%'
        if operator in ('=ilike', '=like'):
            operator = operator[1:]

        unaccent = get_unaccent_wrapper(self.env.cr)

        query = """SELECT res_users.id
                    FROM {from_clause}
                    {where_str} ({display_name} {operator} {percent}
                        OR {reference} {operator} {percent})
                    ORDER BY
                        CASE WHEN {reference} ilike %s THEN 0 ELSE 1 END,
                        CASE WHEN {reference} ilike %s THEN 0 ELSE 1 END,
                        CASE WHEN {pname} ilike {percent} THEN 0 ELSE 1 END,
                        CASE WHEN {pname} ilike {percent} THEN 0 ELSE 1 END,
                        {pname},
                        res_users.login
                """.format(from_clause=from_clause,
                           where_str=where_str,
                           operator=operator,
                           pname=unaccent('res_users__partner_id.name'),
                           display_name=unaccent('display_name'),
                           reference=unaccent('ref'),
                           percent=unaccent('%s'))
        where_clause_params.extend([
            contains_name, contains_name,  # where clause
            name, contains_name,           # ref exact/partial
            startsby_name, contains_name,  # name start/partial
        ])
        if limit:
            query += ' limit %s'
            where_clause_params.append(limit)
        self.env.cr.execute(query, where_clause_params)

        user_ids = map(lambda x: x[0], self.env.cr.fetchall())
        return self.browse(user_ids)
