# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    department_id = fields.Many2one("res.partner.department", "Department")


class ResPartnerDepartment(models.Model):
    _name = 'res.partner.department'
    _order = "parent_path"
    _parent_order = "name"
    _parent_store = True
    _description = "Department"

    name = fields.Char(required=True, translate=True)
    parent_id = fields.Many2one("res.partner.department", "Parent department",
                                ondelete="restrict")
    child_ids = fields.One2many("res.partner.department", "parent_id",
                                "Child departments")
    parent_path = fields.Char(index=True)
