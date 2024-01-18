# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Project State
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################

from odoo import fields, models


class ProjectProjectStage(models.Model):
    _inherit = 'project.project.stage'

    display_in_project_status = fields.Boolean(
        string='Display in project status',
        default=True
    )
