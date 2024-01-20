# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Alert quick timesheet task
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################

from odoo import fields, models, api, _
from odoo.addons.microcom_alert_quick_timesheet_task.models.microcom_timesheet import STATUS_COLOR_DESCRIPTION


class MicrocomTimesheetHistory(models.TransientModel):
    _name = 'microcom.timesheet.history'
    _description = 'Microcom timesheet history'
    _order = 'date, user_name'

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        ctx = self.env.context
        res['timesheet_ids'] = self.get_microcom_timesheet_history_action(ctx)
        return res

    timesheet_ids = fields.One2many(
        'microcom.timesheet.history.line',
        'line_id'
    )

    def get_microcom_timesheet_history_action(self, args):
        self = self.sudo()
        obj = self.env['microcom.timesheet']
        task_id = args.get('task_id')
        partner_id = args.get('partner_id')

        timesheets = obj._get_timesheet(task_id, partner_id, open_view=True)
        res = []
        for timesheet in timesheets:
            vals = {
                'partner_id': timesheet.partner_id.id,
                'project_id': timesheet.project_id.id,
                'task_id': timesheet.task_id.id,
                'user_name': timesheet.user_id.name,
                'name': timesheet.name,
                'date': timesheet.date,
                'state': timesheet.state,
                'task_id': timesheet.task_id.id,
                'display_timesheet_alert_description': timesheet.display_timesheet_alert_description,
                'color_ts': timesheet.color_ts,
            }
            res.append(vals)
        return [(0, 0, line_vals) for line_vals in res]


class MicrocomTimesheetHistory(models.TransientModel):
    _name = 'microcom.timesheet.history.line'
    _description = 'Microcom timesheet history line'
    _order = 'date, user_name'

    line_id = fields.Many2one(
        'microcom.timesheet.history',
        string='Lines'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner'
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project'
    )
    task_id = fields.Many2one(
        'project.task',
        string='Task'
    )
    user_name = fields.Char(
        string='User'
    )
    name = fields.Char(
        string='Description'
    )
    date = fields.Date(
        string='Date'
    )
    state = fields.Selection(
        [
            ('open', 'Open'),
            ('closed', 'Closed'),
            ('supervised', 'Supervised'),
            ('corrected', 'Corrected'),
            ('billed', 'Billed'),
            ('cancelled', 'Cancelled'),
        ], string='Status'
    )
    color_ts = fields.Char(
    )
    display_timesheet_alert_description = fields.Selection(
        STATUS_COLOR_DESCRIPTION,
        default='nothing',
        string=' '
    )
