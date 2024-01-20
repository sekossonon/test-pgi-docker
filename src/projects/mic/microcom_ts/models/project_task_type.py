# coding: utf-8

from odoo import fields, models


class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    display_on_dashboard = fields.Boolean(
        string='Display on dashboard'
    )
