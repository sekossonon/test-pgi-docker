# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import datetime, timedelta

import pytz

TZ = pytz.timezone('Canada/Eastern')
from odoo.tools.misc import format_date


class MicrocomTimesheetDashboard(models.Model):
    _inherit = 'microcom.timesheet'

    # Dashbord
    @api.model
    def retrieve_dashboard(self):
        """ This function returns the values to populate the custom dashboard in
            the Timesheet views.
        """
        self = self.sudo()
        tasks_obj = self.env['project.task']
        timesheet_obj = self.env['microcom.timesheet']
        followup_obj = self.env['project.task.followup']
        #
        dt = fields.Date.context_today(self)
        # first_day = dt - timedelta(days=dt.weekday())
        # min = datetime.combine(first_day, datetime.min.time())
        # start = TZ.localize(min).astimezone(pytz.utc).replace(tzinfo=None)

        dict_followup = {
            0: {'id': 0, 'name': '', 'date': '', 'complete_name': ''},
            1: {'id': 0, 'name': '', 'date': '', 'complete_name': ''},
            2: {'id': 0, 'name': '', 'date': '', 'complete_name': ''}
        }

        result = {
            'all_open': 0,
            'all_late': 0,
            'all_overtime': 0,
            'my_task': 0,
            'my_last': 0,
            'my_overtime': 0,
            'all_followup': 0,
            'late_followups': 0,
            'all_future_followups': 0,
            'user_code': self.env.user.partner_id.ref,
            'future_followups': dict_followup

        }
        domain = [('stage_dashboard', '=', True)]
        department_domain = department_user_domain = []
        department_id = self.env.user.partner_id.department_id
        if department_id:
            department_domain = [
                ('department_id', '=', department_id.id)
            ]
            department_user_domain = [
                ('user_id.partner_id.department_id', '=', department_id.id)
            ]
        #
        all_tasks = tasks_obj.search(
            domain + department_domain
        )
        #
        # if not all_tasks:
        # return result

        all_open = all_tasks.filtered(lambda x: x.is_closed == False)
        result['all_open'] = len(all_open)
        all_late = all_open.filtered(
            lambda x: x.date_deadline and x.date_deadline <= fields.Date.context_today(self) or not x.date_deadline
        )
        result['all_late'] = len(all_late)
        all_overtime = all_open.filtered(lambda x: x.mic_overtime < 0)
        result['all_overtime'] = len(all_overtime)
        #
        user_id = self.env.uid
        my_task = all_open.filtered(lambda x: user_id in x.user_ids.ids or user_id == x.user_id.id)
        result['my_task'] = len(my_task)
        result['my_last'] = len(my_task.filtered(
            lambda x: x.date_deadline and x.date_deadline <= fields.Date.context_today(self) or not x.date_deadline))
        result['my_overtime'] = len(my_task.filtered(lambda x: x.mic_overtime < 0))

        domain = [
            ('user_id', '=', user_id),
            ('state', '=', 'open'),
        ]
        followup_ids = followup_obj.search(
            domain + department_user_domain

        ).sorted(key=lambda r: r.date_deadline, reverse=False)

        followup_ids._compute_overdue()
        result['all_followup'] = len(followup_ids.ids)
        result['late_followups'] = len(followup_ids.filtered(lambda x: x.overdue == True))
        future_followups = followup_ids.filtered(lambda x: x.date_deadline == dt)
        result['all_future_followups'] = len(future_followups)
        #
        i = 0
        for rec in future_followups.filtered(lambda x: x.overdue != True).sorted(key=lambda r: r.deadline_time,
                                                                                 reverse=False):
            date = format_date(self.env, rec.date_deadline, date_format='dd MMM yyyy')
            hours = rec.deadline_time

            complete_name = '%s' % (rec.task_id and rec.task_id.name or rec.name)
            name = (complete_name[:20] + '..') if len(complete_name) > 20 else complete_name
            #
            dict_followup[i] = {
                'id': rec.id,
                'name': name,
                'complete_name': complete_name,
                'date': '%s %s' % (date, hours)
            }
            i += 1
            if i >= len(dict_followup):
                break

        result['future_followups'] = dict_followup
        return result

    @api.model
    def open_action(self, domain, context):
        action = self.env['ir.actions.actions']._for_xml_id('project.action_view_all_task')
        domain += [
            ('department_id', '=', self.env.user.partner_id.department_id.id),
            ('stage_dashboard', '=', True)
        ]
        action['domain'] = domain
        action['context'] = context
        return action

    @api.model
    def project_task_all(self, task_id=False):
        domain = [
            ('is_closed', '=', False)
        ]
        context = {'group_by': 'stage_id'}
        return self.open_action(domain, context)

    @api.model
    def project_my_task(self, task_id=False):
        domain = [
            ('is_closed', '=', False),
            ('user_ids', '=', self.env.uid)
        ]
        context = {'group_by': 'stage_id'}
        return self.open_action(domain, context)

    @api.model
    def project_task_all_late(self, task_id=False):
        domain = [
            ('is_closed', '=', False),
            '|',
            ('date_deadline', '<=', fields.Date.context_today(self)),
            ('date_deadline', '=', False)
        ]
        context = {'group_by': 'stage_id'}
        return self.open_action(domain, context)

    @api.model
    def project_my_task_late(self, task_id=False):
        domain = [
            ('is_closed', '=', False),
            ('user_ids', '=', self.env.uid),
            '|',
            ('date_deadline', '<=', fields.Date.context_today(self)),
            ('date_deadline', '=', False)
        ]
        context = {'group_by': 'stage_id'}
        return self.open_action(domain, context)

    @api.model
    def project_task_all_overtime(self, task_id=False):
        domain = [
            ('is_closed', '=', False),
            ('mic_overtime', '<', 0)
        ]
        context = {'group_by': 'stage_id'}
        return self.open_action(domain, context)

    @api.model
    def project_my_task_overtime(self, task_id=False):
        domain = [
            ('is_closed', '=', False),
            ('user_ids', '=', self.env.uid),
            ('mic_overtime', '<', 0)
        ]
        context = {'group_by': 'stage_id'}
        return self.open_action(domain, context)

    # Followups
    @api.model
    def open_followup_action(self, domain, context):
        action = self.env['ir.actions.actions']._for_xml_id('microcom_ts.project_task_followup_action')
        action['domain'] = domain
        action['context'] = context
        return action

    @api.model
    def project_task_my_followup(self, followup=False):
        domain = [
            ('user_id', '=', self.env.uid),
            ('state', '=', 'open')
        ]
        context = {}
        return self.open_followup_action(domain, context)

    @api.model
    def project_task_my_followup_late(self, followup=False):
        domain = [
            ('user_id', '=', self.env.uid),
            ('overdue', '=', True),
            ('state', '=', 'open')
        ]
        context = {}
        return self.open_followup_action(domain, context)

    @api.model
    def project_task_my_followup_future(self, followup=False):
        dt = fields.Date.context_today(self)
        domain = [
            ('user_id', '=', self.env.uid),
            ('date_deadline', '=', dt),
            ('state', '=', 'open')
        ]
        context = {}
        return self.open_followup_action(domain, context)

    @api.model
    def future_followups(self, followup_id):
        action = self.env['ir.actions.actions']._for_xml_id('microcom_ts.project_task_followup_action')
        action['res_id'] = followup_id[0]
        action['views'] = [(self.env.ref('microcom_ts.project_task_followup_form').id, 'form')]
        return action
