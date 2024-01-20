# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.fields import Command
from odoo.exceptions import UserError, ValidationError
from odoo.addons.microcom_ts.models.project_task import write_fu_from_request
from odoo.addons.uranos_ts.project_issue import (
    close_all_followup_from_uranos,
    open_ts_cursor,
    update_uranos_followup_contact
)


class SynchronizeTimesheetDay(models.TransientModel):
    _name = 'microcom.timesheet.synchronize'
    _description = 'Synchronize timesheet'

    date = fields.Date('Day', default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', 'Employee', default=lambda x: x.env.user)

    def synchronize_day(self):
        self.env['microcom.timesheet'].import_day(self.date, self.user_id)


class ImportRequest(models.TransientModel):
    _name = 'microcom.timesheet.import.request'
    _description = 'Timesheet import request'

    partner_id = fields.Many2one('res.partner', 'Customer', required=True)
    uranos_request_id = fields.Many2one('uranos.request', 'Request', required=True)
    project_id = fields.Many2one('project.project', 'Project')

    def import_request(self):
        odoo_task = self.env['project.task'].with_context(active_test=False).sudo().search(
            [('request_pk', '=', self.uranos_request_id.pk_request)])

        if odoo_task:
            raise UserError(_('Task already exist'))

        task_id = self.env['project.task'].with_context(skip_fu=True).create({
            'partner_id': self.partner_id.id,
            'project_id': self.project_id.id,
            'name': 'Import',
            'source_id': self.env.ref('microcom_helpdesk.task_source_project').id
        })
        task_id.uranos_request_id = self.uranos_request_id
        task_id.button_synchronize()
        task_id.with_context(skip_fu=False).button_synchronize_followup()


class CloseRequest(models.TransientModel):
    _name = 'microcom.timesheet.close.request'
    _description = 'Timesheet close request'

    task_id = fields.Many2one('project.task', 'Task', required=True)
    microcom_timesheet_id = fields.Many2one('microcom.timesheet', 'Timesheet')
    # followup_id = fields.Many2one('project.task.followup', 'Followup')
    allowed_stage_ids = fields.Many2many('project.task.type', compute='_compute_allowed_stage_ids')
    stage_id = fields.Many2one('project.task.type', 'Stage')
    mode = fields.Selection([('open', 'Open'), ('close', 'Close')], default='close')

    @api.depends('task_id', 'mode')
    def _compute_allowed_stage_ids(self):
        for record in self:
            closed_stage_ids = self.task_id.project_id.type_ids.filtered(
                lambda x: x.is_closed_type or x.is_canceled_type)
            if self.mode == 'open':
                record.allowed_stage_ids = self.task_id.project_id.type_ids - closed_stage_ids
            elif self.mode == 'close':
                record.allowed_stage_ids = closed_stage_ids

    @api.onchange('task_id', 'mode')
    def _onchange_task_id(self):
        if self.microcom_timesheet_id.task_id != self.task_id:
            self.microcom_timesheet_id = self.env['microcom.timesheet'].search([
                ('task_id', '=', self.task_id.id),
                ('user_id', '=', self.env.user.id),
                ('state', '=', 'open'),
            ], order='id desc', limit=1)
        # if self.followup_id.task_id != self.task_id:
        #     # default to main followup when no other are open (main is always open)
        #     # otherwise, default to first followup for user (main if possible)
        #     best_followup = self.task_id.followup_ids.filtered(lambda x: x.state == 'open')
        #     if len(best_followup) > 1:
        #         best_followup = best_followup.filtered(lambda x: x.user_id == self.env.user)
        #         if len(best_followup) > 1:
        #             best_followup = best_followup.filtered('is_main') or best_followup[0]
        #     self.followup_id = best_followup
        if self.stage_id not in self.allowed_stage_ids:
            self.stage_id = self.allowed_stage_ids[:1]

    def button_close_request(self):
        #
        # ignore if same state
        if self.task_id.stage_id.is_closed_type or self.task_id.stage_id.is_canceled_type:
            if self.mode == 'close':
                raise UserError(_('Task is already closed'))
        else:
            if self.mode == 'open':
                raise UserError(_('Task is already open'))
        #
        if not self.microcom_timesheet_id:

            action_msg = _('Entry created by close wizard')
            time = self.env['microcom.timesheet'].calculate_now()
            self.microcom_timesheet_id = self.env['microcom.timesheet'].create(
                self.task_id._prepare_timesheet(action_msg, start=time, end=time))

            if not self.microcom_timesheet_id.billing_code_id:
                # set billing code
                self.microcom_timesheet_id.onchange_user_project()
            if not self.microcom_timesheet_id.followup_id:
                fu_data = self.task_id._prepare_main_followup()
                fu_data.update(is_main=False, billing_code_id=self.microcom_timesheet_id.billing_code_id.id)
                self.task_id.followup_ids = [Command.create(fu_data)]
                self.microcom_timesheet_id.select_followup()

        pk_request = self.task_id.request_pk
        pk_action = self.microcom_timesheet_id.pk_action
        if not pk_request:
            raise UserError(_('No request associated'))
        if not pk_action:
            raise UserError(_('No action associated'))
        cursor = self.env.context.get('open_ts_cursor')
        if cursor:
            self.close_request_inner(cursor, pk_request, pk_action)
        else:
            try:
                with open_ts_cursor(self) as cursor:
                    if cursor is None:
                        raise ValidationError(_('TS is not connected'))
                    self.close_request_inner(cursor, pk_request, pk_action)
            except Exception as ex:
                raise ex
        self.with_context(safe_request_status=True).task_id.stage_id = self.stage_id

    def close_request_inner(self, cursor, pk_request, pk_action):
        if self.mode == 'open':
            main_followup = self.task_id.followup_ids.filtered('is_main')
            if main_followup.pk_followup:
                cursor.execute(
                    "UPDATE dbo.FollowUp SET status = 2 WHERE PK_FollowUp = %s", (main_followup.pk_followup,))
                update_uranos_followup_contact(main_followup, cursor)
            cursor.execute("UPDATE dbo.Request SET status = 2 WHERE PK_Request = %s", (pk_request,))
        elif self.mode == 'close':
            close_all_followup_from_uranos(cursor, pk_request, pk_action)
            cursor.execute("UPDATE dbo.Request SET status = 0 WHERE PK_Request = %s", (pk_request,))
        # update Odoo followup from TS
        write_fu_from_request(self.task_id, pk_request, cursor)
