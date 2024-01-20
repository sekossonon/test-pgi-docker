# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools import config


def get_connection_kwargs(record):
    databaseConfig = record.env['ir.config_parameter'].sudo()
    if databaseConfig.get_param('uranos_timesheet.is_active'):
        return dict(
            host=databaseConfig.get_param('uranos_timesheet.hostname'),
            user=databaseConfig.get_param('uranos_timesheet.username'),
            password=config.options.get('ts_password'),
            database=config.options.get('ts_database'),
            port=databaseConfig.get_param('uranos_timesheet.port'), as_dict=True)
    else:
        return None


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    is_active = fields.Boolean('Activate export')
    hostname = fields.Char('Hostname', help='SQL Server hostname.')
    port = fields.Integer('Port number', help='SQL Server port number')
    username = fields.Char('Username', help='SQL Server username.')
    password = fields.Char('Password', help='SQL Server password.')
    database = fields.Char('Database name', help='SQL Server database name.')

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            hostname=params.get_param("uranos_timesheet.hostname", default=''),
            is_active=params.get_param("uranos_timesheet.is_active", default=False),
            port=int(params.get_param("uranos_timesheet.port", default='1433')),
            username=params.get_param("uranos_timesheet.username", default=''),
            # hide password
            # password=config.options.get('ts_password') and '<set>',
            # database=config.options.get('ts_database'),
        )
        return res

    def set_values(self):
        """ set default sale and purchase taxes for products """
        super(ResConfigSettings, self).set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param("uranos_timesheet.hostname", self.hostname)
        params.set_param("uranos_timesheet.is_active", self.is_active)
        params.set_param("uranos_timesheet.port", self.port)
        params.set_param("uranos_timesheet.username", self.username)
