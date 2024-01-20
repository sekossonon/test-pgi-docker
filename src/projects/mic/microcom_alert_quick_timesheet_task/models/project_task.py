# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Alert quick timesheet task
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################

from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    customer_validation = fields.Boolean(
        related='project_id.customer_validation',
        store=True
    )
    task_validation = fields.Boolean(
        related='project_id.task_validation',
        store=True
    )
