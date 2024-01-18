# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    internal_code = fields.Char('IMD')
    owner_partner_id = fields.Many2one('res.partner', string='Owner (Customer)', tracking=True)
    owner = fields.Char('Owner', compute='_compute_owner', store=True)

    @api.depends('owner_user_id', 'owner_partner_id', 'location', 'employee_id')
    def _compute_owner(self):
        for equipment in self:
            if equipment.employee_id:
                equipment.owner = equipment.employee_id.display_name
            elif equipment.owner_partner_id:
                equipment.owner = equipment.owner_partner_id.display_name
            elif equipment.location:
                equipment.owner = equipment.location
            else:
                equipment.owner = _("Unassigned")
