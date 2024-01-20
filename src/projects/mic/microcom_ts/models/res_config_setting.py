# coding: utf-8

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    minimum_date = fields.Date('Date minimale permise')
    minimum_admin_date = fields.Date('Date minimale permise pour admin')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    minimum_date = fields.Date('Date minimale permise', related='company_id.minimum_date', readonly=False)
    minimum_admin_date = fields.Date('Date minimale permise pour admin', related='company_id.minimum_admin_date', readonly=False)