# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Alert quick timesheet task
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################

from odoo import fields, models, _, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # major_incident
    task_high_priority_in_progress = fields.Char(
        string='High priority task in progress',
        default='#ff0000'
    )
    # nothing
    nothing_to_report = fields.Char(
        string='Nothing to report',
        default='#228b22'
    )
    # task_progress
    task_progress = fields.Char(
        string='Other task in progress',
        default='#ffd700'
    )
    # task_within_48h
    task_within_h = fields.Char(
        string='Other Task in progress (Within 48 hours)',
        default='#fffacd'

    )
    task_same_real_time_open = fields.Char(
        string='Same task in real-time (Opened)',
        default='#ff5f1f'
    )
    # task_same_in_progress_time_48h
    task_same_in_progress_time = fields.Char(
        string='Same task (Within 48 hours)',
        default='#fbae9e'
    )
