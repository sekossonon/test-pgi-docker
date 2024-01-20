# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    emails = fields.Char(string='Emails',
                         help='Format: aa@microcom.ca,bb@microcom.ca, '
                              'cc@microcom.ca')

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res['emails'] = params.get_param('work_anniversary.emails', default='')
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param("work_anniversary.emails", self.emails)
