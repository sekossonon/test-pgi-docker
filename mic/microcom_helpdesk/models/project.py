# -*- coding: utf-8 -*-

import pytz

from odoo import api, fields, models, _
from datetime import timedelta
from odoo.exceptions import UserError
import json


# --------------------------------------------------------------------------------
# copied from partner-contact/partner_tz/tools/tz_utils.py in v15
UTC_TZ = pytz.timezone("UTC")


def tz_to_tz_naive_datetime(from_tz, to_tz, date_time):
    """
    Convert tz-naive datetime from a specifc tz to a tz-naive datetime of a specific tz

    :param from_tz: pytz.timezone object or tz selection value
    :param to_tz: pytz.timezone object or tz selection value
    :param date_time: tz-naive datetime.datetime object
    :return: tz-naive datetime.datetime object
    """
    if isinstance(from_tz, str):
        from_tz = pytz.timezone(from_tz)
    if isinstance(to_tz, str):
        to_tz = pytz.timezone(to_tz)
    return from_tz.localize(date_time).astimezone(to_tz).replace(tzinfo=None)


def tz_to_utc_naive_datetime(from_tz, date_time):

    return tz_to_tz_naive_datetime(from_tz, UTC_TZ, date_time)


def utc_to_tz_naive_datetime(to_tz, date_time):
    return tz_to_tz_naive_datetime(UTC_TZ, to_tz, date_time)
# --------------------------------------------------------------------------------


class Project(models.Model):
    _inherit = "project.project"

    project_type = fields.Selection([('project', 'Project'), ('helpdesk', 'Helpdesk')], 'Project Type', required=True, default='project')
    new_tickets_count = fields.Integer(compute="_count_tasks")
    inprogress_count = fields.Integer(compute="_count_tasks")
    late_to_start_count = fields.Integer(compute="_count_tasks")
    late_to_end_count = fields.Integer(compute="_count_tasks")
    validator_ids = fields.Many2many('res.users', string='Tickets Validators')


    @api.depends('task_ids')
    def _count_tasks(self):
        date_now = fields.Datetime.now()
        stage_solved = self.env.ref('microcom_helpdesk.helpdesk_stage_solved').id
        stage_closed = self.env.ref('microcom_helpdesk.helpdesk_stage_closed').id
        stage_canceled = self.env.ref('microcom_helpdesk.helpdesk_stage_canceled').id
        for project in self:
            project.new_tickets_count = self.env['project.task'].search_count([
                ('project_id', '=', project.id),
                ('stage_id', '=', self.env.ref('microcom_helpdesk.helpdesk_stage_new').id)
            ])
            project.inprogress_count = self.env['project.task'].search_count([
                ('project_id', '=', project.id),
                ('stage_id', '=', self.env.ref('microcom_helpdesk.helpdesk_stage_inprogress').id)
            ])
            project.late_to_start_count = self.env['project.task'].search_count([
                ('project_id', '=', project.id),
                ('assignment_deadline', '<', date_now),
                ('stage_id', '=', self.env.ref('microcom_helpdesk.helpdesk_stage_new').id)
            ])
            project.late_to_end_count = self.env['project.task'].search_count([
                ('project_id', '=', project.id),
                ('date_deadline', '<', date_now),
                ('stage_id', 'not in', (stage_solved, stage_closed, stage_canceled))
            ])

    def show_new_tickets(self):
        tasks = self.env['project.task'].search([('project_id', '=', self.id), ('stage_id', '=', self.env.ref('microcom_helpdesk.helpdesk_stage_new').id)])
        return {
            'name': _('New Tickets'),
            'domain': [('id', 'in', tasks.ids)],
            'res_model': 'project.task',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'kanban,tree,form,calendar,pivot,graph',
            'view_type': 'form',
            'context': {'default_project_id': self.id},
        }


    def show_inprogress_tickets(self):
        tasks = self.env['project.task'].search([('project_id', '=', self.id),
                                                 ('stage_id', '=', self.env.ref('microcom_helpdesk.helpdesk_stage_inprogress').id)])
        return {
            'name': _('Tickets In Progress'),
            'domain': [('id', 'in', tasks.ids)],
            'res_model': 'project.task',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'kanban,tree,form,calendar,pivot,graph',
            'view_type': 'form',
            'context': {'default_project_id': self.id},
        }


    def show_should_be_started_tickets(self):
        date_now = fields.Datetime.now()
        tasks = self.env['project.task'].search([('project_id', '=', self.id),
                                                 ('assignment_deadline', '<', date_now),
                                                 ('stage_id', '=', self.env.ref('microcom_helpdesk.helpdesk_stage_new').id)])
        return {
            'name': _('Tickets Should have started'),
            'domain': [('id', 'in', tasks.ids)],
            'res_model': 'project.task',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'kanban,tree,form,calendar,pivot,graph',
            'view_type': 'form',
            'context': {'default_project_id': self.id},
        }


    def show_should_be_ended_tickets(self):
        date_now = fields.Datetime.now()
        stage_solved = self.env.ref('microcom_helpdesk.helpdesk_stage_solved').id
        stage_closed = self.env.ref('microcom_helpdesk.helpdesk_stage_closed').id
        stage_canceled = self.env.ref('microcom_helpdesk.helpdesk_stage_canceled').id
        tasks = self.env['project.task'].search([('project_id', '=', self.id),
                                                 ('date_deadline', '<', date_now),
                                                 ('stage_id', 'not in', (stage_solved, stage_closed, stage_canceled))])
        return {
            'name': _('Tickets Should be done'),
            'domain': [('id', 'in', tasks.ids)],
            'res_model': 'project.task',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'kanban,tree,form,calendar,pivot,graph',
            'view_type': 'form',
            'context': {'default_project_id': self.id},
        }

    @api.constrains('project_type')
    def constrains_project_type(self):
        for project in self:
            if project.project_type == "helpdesk":
                stages = project.env['project.task.type'].search([('project_type', '=', 'helpdesk')])
                project.type_ids = stages


class Task(models.Model):
    _inherit = "project.task"

    project_id = fields.Many2one(default=lambda self: self._default_project())
    ticket_number = fields.Char('Ticket Number', compute="_compute_ticket_number", store=True, copy=False)
    project_type = fields.Selection(related="project_id.project_type", store=True, readonly=True)
    source_id = fields.Many2one('task.source', 'Source', required=True) #TODO: unable to set NOT NULL on column 'source_id'
    ticket_type_id = fields.Many2one('task.ticket.type', 'Ticket Type')
    ticket_subtype_id = fields.Many2one('task.ticket.subtype', 'Ticket Subtype')
    phone_from = fields.Char('Contact Phone') #TODO: Two fields (phone_from, partner_phone) of project.task() have the same label: Phone. [Modules: microcom_helpdesk and project]
    ticket_date = fields.Datetime('Ticket Date', default=lambda t: fields.Datetime.now())
    contact_id = fields.Many2one('res.partner')
    show_all_contacts = fields.Boolean('Show All contacts')
    assignment_delay_id = fields.Many2one('project.task.assignment.delay', string='Assignment delay')
    assignment_deadline = fields.Datetime('Assignment deadline', compute='_compute_assignment_deadline', store=True)
    assigned = fields.Boolean('Assigned', compute='_compute_assigned', store=True)
    mail_ids = fields.One2many('project.mail', 'task_id', string='Mails')
    all_attachment_ids = fields.Many2many('ir.attachment', string='Attachments', compute='_compute_all_attachment_ids')
    department_id = fields.Many2one(related='project_id.department_id', store=True)
    contact_domain_field = fields.Char('Contact domain field', compute="_compute_contact_domain_field")

    @api.depends('show_all_contacts', 'partner_id')
    def _compute_contact_domain_field(self):
        for rec in self:
            if rec.show_all_contacts or not rec.partner_id:
                contact_domain_field = []
            else:
                contact_domain_field = json.dumps([('parent_id', '=', rec.partner_id.id)])
            rec.contact_domain_field = contact_domain_field

    @api.model
    def _default_project(self):
        # TODO default project necessary for project_type
        return self.env.context.get('default_project_id')

    @api.depends('user_ids', 'stage_id')
    def _compute_assigned(self):
        helpdesk_stage_new = self.env.ref('microcom_helpdesk.helpdesk_stage_new', raise_if_not_found=False)
        for record in self:
            record.assigned = record.user_id and record.stage_id != helpdesk_stage_new

    @api.depends('attachment_ids', 'mail_ids.attachment_ids')
    def _compute_all_attachment_ids(self):
        for record in self:
            ticket_attachments = record.mail_ids.mapped('attachment_ids')
            record.all_attachment_ids = (record.attachment_ids + ticket_attachments).sorted()

    @api.depends('assignment_delay_id', 'ticket_date')
    def _compute_assignment_deadline(self):
        """ set task deadline, respecting office hours
        """
        for task in self:
            if task.ticket_date and task.assignment_delay_id:
                user_tz = pytz.timezone(task.env.user.tz or 'UTC')
                # TODO put office hours in system parameters + use "office tz"
                start_office_hour = 8
                end_office_hour = 18
                closed_duration = 24 - (end_office_hour - start_office_hour)

                def start_within_office_hours(local_date):
                    # after office hour, advance past midnight
                    if local_date.hour >= end_office_hour:
                        local_date = local_date.replace(hour=23) + timedelta(hours=2)
                    # before office hour, advance to start
                    if local_date.hour < start_office_hour:
                        local_date = local_date.replace(hour=start_office_hour, minute=0, second=0, microsecond=0)
                    return local_date

                def skip_weekend(local_date):
                    # TODO skip holidays before/after weekend
                    # weeekend, move to next Monday
                    if local_date.weekday() == 5:
                        local_date = local_date + timedelta(days=2)
                    elif local_date.weekday() == 6:
                        local_date = local_date + timedelta(days=1)
                    return local_date

                local_date = utc_to_tz_naive_datetime(user_tz, task.ticket_date)
                local_date = start_within_office_hours(local_date)
                local_date = skip_weekend(local_date)
                local_date += timedelta(hours=task.assignment_delay_id.time_delay)
                if local_date.hour < start_office_hour or local_date.hour >= end_office_hour:
                    # skip closed hours
                    # this is a shortcut, time_delay must be less than 14h or in 24h blocks
                    # e. g. 17:00 + 16h delay = 9:00, only 2h effective delay
                    local_date += timedelta(hours=closed_duration)
                local_date = skip_weekend(local_date)

                task.assignment_deadline = local_date

    @api.onchange('contact_id')
    def _onchange_contact_id(self):
        if self.contact_id:
            if not self.partner_id:
                self.partner_id = self.contact_id.parent_id or self.contact_id
            self.phone_from = self.contact_id.phone
            self.email_from = self.contact_id.email

    # @api.onchange('partner_id')
    # def _onchange_partner_id(self):
    #     # TODO:MIGRATION: super from v11 project copied email from client into email_from
    #     if self.partner_id and self.project_type != 'helpdesk':
    #         return super()._onchange_partner_id()

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id.project_type == 'project':
            self.source_id = self.env.ref('microcom_helpdesk.task_source_project')
        if self.project_id.process_ids:
            self.process_id = self.project_id.process_ids[0]

    @api.constrains('project_id.validator_ids', 'stage_id')
    def constrains_start_end(self):
        for task in self:
            cannot_close = task.project_id.validator_ids and task.env.user not in task.project_id.validator_ids
            if cannot_close and task.stage_id == self.env.ref('microcom_helpdesk.helpdesk_stage_closed'):
                raise UserError('Only the validators can change the stage to done')

    def message_get_suggested_recipients(self):
        recipients = super().message_get_suggested_recipients()
        for task in self.filtered('contact_id'):
            reason = _('Customer Email') if task.contact_id.email else _('Contact')
            if task.contact_id:
                recipients = task._message_add_suggested_recipient(
                    {task.id: []}, partner=task.contact_id, reason=reason)
        return recipients

    @api.model_create_multi
    def create(self, vals):
        result = super().create(vals)
        for res in result:
            if res.project_id.project_type == 'helpdesk' and not res.ticket_number:
                res.ticket_number = self.env['ir.sequence'].next_by_code('helpdesk.ticket')
        return result

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if 'stage_id' in vals:
                if (rec.stage_id.is_closed_type or rec.stage_id.is_canceled_type):
                    for mail in rec.mail_ids:
                        mail.state = 'done'
            if rec.project_id.project_type == 'helpdesk' and not rec.ticket_number:
                # infinite recursion if sequence does not exist
                ticket_number = self.env['ir.sequence'].next_by_code('helpdesk.ticket')
                if ticket_number:
                    rec.ticket_number = ticket_number
        return res


    @api.depends('request_pk')
    def _compute_ticket_number(self):
        for record in self:
            if record.request_pk:
                record.ticket_number = record.request_pk


class ProjectTaskType(models.Model):
    _inherit = "project.task.type"

    project_type = fields.Selection([('project', 'Project'), ('helpdesk', 'Helpdesk')], 'Project Type', required=True, default='project')


class TaskSource(models.Model):
    _name = "task.source"
    _description = 'Task Source'

    name = fields.Char('Name', required=True, translate=True)


class TaskTicketType(models.Model):
    _name = "task.ticket.type"
    _description = 'Ticket Type'

    name = fields.Char('Name', required=True, translate=True)


class TaskTicketSubtype(models.Model):
    _name = "task.ticket.subtype"
    _description = 'Ticket Subtype'

    name = fields.Char('Name', required=True, translate=True)


class TaskAssignmentDelay(models.Model):
    _name = "project.task.assignment.delay"
    _description = "Dealine to assign user to a ticket"

    name = fields.Char('Name', required=True, translate=True)
    email_description = fields.Char('Description for email', required=True, translate=True)
    time_delay = fields.Integer('Delay in office hours')
