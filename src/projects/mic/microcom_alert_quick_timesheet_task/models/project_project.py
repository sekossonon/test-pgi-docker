# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Alert quick timesheet task
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################

from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    customer_validation = fields.Boolean(
        string='Customer validation'
    )
    task_validation = fields.Boolean(
        string='Task validation'
    )
