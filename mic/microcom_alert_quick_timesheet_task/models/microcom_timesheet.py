# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Alert quick timesheet task
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################

from odoo import fields, models, api, _, SUPERUSER_ID
from datetime import timedelta

STATUS_COLOR_DESCRIPTION = [
    ('major_incident', 'Level 5 task already in progress'),  # red
    ('nothing', 'Nothing to report'),  # green
    ('task_progress', 'A task is already in progress'),  # Yellow
    ('task_within_h', 'A task is already in progress (Within 48 hours)'),  # Light Yellow
    ('task_same_real_time_open', 'The same Task is in real-time (Opened)'),  # Orange
    ('task_same_in_progress_time_48h', 'The same Task is in real-time (Within 48 hours)'),  # Light Orange
]

HOURS = 48
PRIORITY_MICROCOM = '5'


class MicrocomTimesheet(models.Model):
    _inherit = 'microcom.timesheet'

    @api.model
    def get_default_color(self):
        return self.sudo().env['ir.config_parameter'].get_param(
            'microcom_alert_quick_timesheet_task.nothing_to_report', '#228B22')

    display_timesheet_alert_description = fields.Selection(
        STATUS_COLOR_DESCRIPTION,
        default='nothing',
        string=' '
    )
    color_ts = fields.Char(
        default=get_default_color
    )
    user_timesheet_alert_id = fields.Many2one(
        'res.users',
        string='User'
    )

    def get_tz_convert_date_now_minus_48h(self):
        return (fields.Datetime.context_timestamp(self, fields.Datetime.now()) - timedelta(hours=HOURS)).date()

    def _get_domain_microcom_timesheet_open(self):
        return [('state', '=', 'open')]

    def _get_domain_microcom_timesheet_close(self):
        date = self.get_tz_convert_date_now_minus_48h()
        return [('state', '=', 'closed'), ('date', '>=', date)]

    @api.model
    def _get_timesheet(self, task_id, partner_id, open_view=False):
        self = self.sudo()
        """Nothing to report"""
        state = 'nothing'
        user = False
        obj_par = self.env['ir.config_parameter']
        obj = ts_list = self.env['microcom.timesheet']
        #
        color_ts = obj_par.get_param('microcom_alert_quick_timesheet_task.nothing_to_report', '#228b22')
        domain = [
            ('partner_id', '=', partner_id),
            ('user_id', '!=', self.env.uid),
            #'|', ('task_id.customer_validation', '=', True),
            ('task_id.task_validation', '=', True)
        ]
        open_timesheet_domain = self._get_domain_microcom_timesheet_open()
        close_timesheet_domain = self._get_domain_microcom_timesheet_close()
        #
        open_timesheet = obj.search(open_timesheet_domain + domain)
        closed_timesheet = obj.search(close_timesheet_domain + domain)
        all_timesheet = open_timesheet + closed_timesheet
        #
        date = self.get_tz_convert_date_now_minus_48h()
        if all_timesheet:
            task_ids = all_timesheet.mapped('task_id')
            task_validation = any(x.task_validation for x in task_ids)
            #
            if task_validation:
                #
                ticket_type_id = self.env.ref('microcom_helpdesk.task_type_incident', False)
                if ticket_type_id and any(
                        ts.priority_microcom == PRIORITY_MICROCOM and ts.ticket_type_id.id == ticket_type_id.id for ts
                        in open_timesheet.mapped('task_id')
                ):
                    """Level 5 task already in progress"""
                    state = 'major_incident'
                    color_ts = obj_par.get_param('microcom_alert_quick_timesheet_task.task_high_priority_in_progress',
                                                 '#ff0000')
                    user = open_timesheet and open_timesheet[0].user_id
                    ts_list = open_timesheet
                else:
                    "JAUNE pâle Même client mais pas même tâche (dans les dernier 48 h)"
                    task_in_progress_time = closed_timesheet.filtered(
                        lambda x: x.date and x.date >= date and x.task_id.id != task_id
                    )
                    if task_in_progress_time:
                        state = 'task_within_h'
                        color_ts = obj_par.get_param('microcom_alert_quick_timesheet_task.task_within_h', '#fffacd')
                        ts_list = task_in_progress_time + ts_list
                        user = task_in_progress_time[0].user_id

                    "JAUNE Même client mais pas même tâche temps réel (FT ouverte)"
                    task_in_progress = open_timesheet.filtered(
                        lambda x: x.task_id.id != task_id
                    )
                    if task_in_progress:
                        state = 'task_progress'
                        color_ts = obj_par.get_param('microcom_alert_quick_timesheet_task.task_progress', '#ffd700')
                        ts_list = task_in_progress + ts_list
                        user = task_in_progress[0].user_id
                    #

                    "ORANGE pâle même tâche temps réel (dans les dernier 48 h)"
                    task_same_in_progress_time = closed_timesheet.filtered(
                        lambda x: x.date and x.date >= date and x.task_id.id == task_id
                    )
                    if task_same_in_progress_time:
                        state = 'task_same_in_progress_time_48h'
                        color_ts = obj_par.get_param('microcom_alert_quick_timesheet_task.task_same_in_progress_time',
                                                     '#fbae9e')
                        ts_list = task_same_in_progress_time + ts_list
                        user = task_same_in_progress_time[0].user_id

                    "ORANGE même tâche temps réel (FT ouverte)"
                    task_same_real_time_open = open_timesheet.filtered(
                        lambda x: x.task_id.id == task_id
                    )
                    if task_same_real_time_open:
                        state = 'task_same_real_time_open'
                        color_ts = obj_par.get_param('microcom_alert_quick_timesheet_task.task_same_real_time_open',
                                                     '#ff5f1f')
                        ts_list = task_same_real_time_open + ts_list
                        user = task_same_real_time_open[0].user_id

        dict = {
            'display_timesheet_alert_description': state,
            'user_timesheet_alert_id': user and user.id or False,
            'color_ts': color_ts
        }
        if not open_view:
            return dict
        else:
            return ts_list

    @api.onchange('partner_id', 'task_id')
    def _onchange_partner_task_alert(self):
        if self.partner_id or self.task_id:
            partner_id = self.partner_id and self.partner_id.id or False
            task_id = self.task_id and self.task_id.id or False
            #
            self.update(self._get_timesheet(task_id, partner_id))
