# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    partner_timesheet_ids = fields.One2many(
        'microcom.timesheet',
        'partner_id',
        string='Partner Timesheet'
    )
    partner_timesheet_hours = fields.Float(
        compute='_compute_partner_timesheet',
        store=True,
        compute_sudo=True
    )

    @api.depends('partner_timesheet_ids', 'partner_timesheet_ids.duration_minute')
    def _compute_partner_timesheet(self):
        for rec in self:
            rec.partner_timesheet_hours = sum(rec.partner_timesheet_ids.mapped('duration_minute'))

    def action_view_partner_timesheet(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("microcom_ts.microcom_full_timesheet_action_ro")
        action['domain'] = [
            ('partner_id', '=', self.id)
        ]
        action['context'] = {'default_partner_id': self.id}
        return action
