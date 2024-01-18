# coding: utf-8

import logging

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.addons.uranos_ts.project_issue import (
    add_progression_to_followup,
    create_uranos_followup,
    get_create_open_event,
    get_event_from_uranos,
    open_close_followup,
    open_ts_cursor,
    update_uranos_followup,
)
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command

_logger = logging.getLogger(__name__)

STATE_STRING = {2: 'open', 1: 'cancel', 0: 'close'}


def create_request(task):
    if not task.request_pk:
        if task.partner_id or task.project_id.partner_id:
            # create Odoo Event
            action_msg = _('Requête créée depuis Odoo')
            task.env['microcom.timesheet'].create(task._prepare_timesheet(action_msg))
            # FU created from task
            # if task.user_id:
            #     task.env['project.task.followup'].create(task._prepare_main_followup())
        else:
            raise UserError(_('Project/customer or contact required'))


def get_or_create_open_action(cursor, task):
    event = get_event_from_uranos(task, cursor)
    if event:
        pk_action = event['PK_Action']
    else:
        # Add new action to create or update followup
        action_msg = _('Action créée depuis Odoo')
        ts_record = task.env['microcom.timesheet'].create(
            task._prepare_timesheet(action_msg, end=task.env['microcom.timesheet'].calculate_now())
        )
        pk_action = ts_record.pk_action
    return pk_action


def create_ts_followup(followup, pk_action):
    if not pk_action:
        # must have a quickTS entry and not create in MSSQL only
        raise ValidationError("pk_action required to create followup now")
    if followup.task_id.request_pk:
        cursor = followup.env.context.get('open_ts_cursor')
        if cursor:
            return create_ts_followup_inner(followup, cursor, pk_action)
        else:
            try:
                with open_ts_cursor(followup) as cursor:
                    if cursor is None:
                        return False
                    return create_ts_followup_inner(followup, cursor, pk_action)
            except Exception as ex:
                raise UserError(ex)


def update_followup(followup, pk_action):
    if not pk_action and not followup.env.context.get('no_progression'):
        # must have a quickTS entry and not create in MSSQL only
        raise ValidationError("pk_action required to update followup now")
    if followup.pk_followup:
        try:
            with open_ts_cursor(followup) as cursor:
                if cursor is None:
                    return False
                update_uranos_followup(followup, cursor)
                if not followup.env.context.get('no_progression'):
                    # deadlock when recursive cursor accesses the same record
                    # pk_action = get_or_create_open_action(cursor, followup.task_id)
                    add_progression_to_followup(cursor, followup.pk_followup, pk_action, 'M')
        except Exception as ex:
            raise UserError(ex)


def create_ts_followup_inner(followup, cursor, pk_action):
    if followup.task_id.request_pk:
        # deadlock when recursive cursor accesses the same record
        # pk_action = get_or_create_open_action(cursor, followup.task_id.with_context(skip_create_ts_followup=True))
        pk_followup = create_uranos_followup(followup, pk_action, cursor)
        return pk_followup


def write_fu_from_request(task_id, pk_request, cursor):
    assert cursor

    # determine which FU should be main: same user on same request
    main_fu = None
    if not task_id.followup_ids.filtered('is_main'):
        best_sql = """
            SELECT fu.PK_FollowUP
            FROM [FollowUp] fu
            JOIN [R_MultiContact_FollowUp] fuc on fuc.FollowUpID = fu.PK_FollowUP
            WHERE RequestID = %d and Employee_ContactID = %d
        """
        best_sql_args = (pk_request, task_id.user_id.pk_contact)
        cursor.execute(best_sql, best_sql_args)
        main_fu = cursor.fetchall()
        if main_fu:
            main_fu = main_fu[0]['PK_FollowUP']
    #
    sql = """
        SELECT fu.PK_FollowUP, fu.Name, fu.Description, fu.DateDue, fu.TimeDue, fu.Status, fu.DefaultBillingID
        FROM [FollowUp] fu
        WHERE RequestID = %d
    """
    sql_args = (pk_request,)
    cursor.execute(sql, sql_args)
    for found in cursor.fetchall():
        followup_id = task_id.followup_ids.filtered(lambda fu: fu.pk_followup == found['PK_FollowUP'])
        # Si le followup est présent dans Odoo, le mettre à jour. Sinon le créer à partir des informations de Timesheet.
        if followup_id:
            followup_id.update_task_followup(found)
        else:
            # Aller chercher le user associé au Followup dans Timesheet.
            # S'il y a plusieurs users, ne garder que le premier.
            sql = """
                SELECT FollowUpID, Employee_ContactID, Code, LastName, FirstName, email
                FROM [R_MultiContact_FollowUp]
                LEFT JOIN [Contact] ON (Contact.PK_Contact = Employee_ContactID)
                WHERE FollowUpID = %d
            """
            sql_args = (found['PK_FollowUP'],)
            cursor.execute(sql, sql_args)
            followup_contact = cursor.fetchone()

            if followup_contact:
                # Il devrait toujours y avoir un followup_contact, mais j'ai ajouté la condition au cas...
                user_id = task_id.env['res.users'].sudo().with_context(active_test=False).search(
                    domain=[('pk_contact', '=', followup_contact['Employee_ContactID'])],
                    order='active DESC',
                    limit=1
                )
                # billing_id = task_id.env['microcom.timesheet.billing']
                billing_id = task_id.env['microcom.timesheet.billing'].search(
                    [('pk_typebilling', '=', found['DefaultBillingID'])])
                if not user_id:
                    contact = task_id.env['res.partner'].sudo().with_context(active_test=False).search(
                        domain=[('pk_contact', '=', followup_contact['Employee_ContactID'])],
                        order='active DESC',
                        limit=1
                    )
                    if not contact:
                        contact = task_id.env['res.partner'].sudo().create({
                            'ref': followup_contact['Code'],
                            'email': followup_contact['email'],
                            'firstname': followup_contact['FirstName'],
                            'lastname': followup_contact['LastName'],
                            'pk_contact': followup_contact['Employee_ContactID'],
                            'active': False
                        })
                    user_id = task_id.env['res.users'].sudo().with_context(no_reset_password=True).create({
                        'login': followup_contact['email'],
                        'partner_id': contact.id,
                        'active': False
                    })
                followup = task_id.env['project.task.followup'].with_context({'no_uranos_create': True}).create({
                    'name': found['Name'] or '.',
                    'description': found['Description'],
                    'date_deadline': found['DateDue'],
                    'deadline_minute': found['TimeDue'],
                    'pk_followup': found['PK_FollowUP'],
                    'user_id': user_id.id,
                    'billing_code_id': billing_id.id,
                    'state': STATE_STRING.get(found['Status']),
                    'task_id': task_id.id
                })
                if followup.pk_followup == main_fu:
                    # task user might not be first in followup
                    followup.is_main = True
                    followup.user_id = task_id.user_id


class Project(models.Model):
    _inherit = 'project.project'

    department_id = fields.Many2one('res.partner.department', 'Department')
    invoice_rate_ids = fields.One2many('timesheet.invoice.rate', 'project_id', 'Taux de facturation')
    user_can_edit_budget = fields.Boolean(compute='_compute_user_can_edit_budget')
    no_budget_required = fields.Boolean(default=False, string='No budget required')

    def _compute_user_can_edit_budget(self):
        user_is_supervisor = self.user_has_groups('microcom_tasks.group_project_supervisor')
        for project in self:
            project.user_can_edit_budget = user_is_supervisor or (project.user_id == self.env.user)


class Task(models.Model):
    _inherit = "project.task"

    microcom_timesheet_ids = fields.One2many('microcom.timesheet', 'task_id', 'Microcom Timesheets')
    open_ts_event = fields.Many2one('microcom.timesheet', compute='_compute_open_ts_event', string='Open Event')
    timesheet_count = fields.Integer('Timesheet count', compute='_compute_timesheet_count')
    followup_ids = fields.One2many('project.task.followup', 'task_id', string='Follow up')
    is_open = fields.Boolean('Is Open', compute='_compute_is_open')
    no_budget_required = fields.Boolean(default=False, string='No budget required')
    user_can_edit_budget = fields.Boolean(compute='_compute_user_can_edit_budget')
    budget_line_ids = fields.One2many('project.task.budget.line', 'task_id', 'Budget')
    budget_template_id = fields.Many2one('task.budget.template', 'Budget Template', tracking=True)
    planned_hours = fields.Float(string='Planned', compute="_compute_total_hours", store=True)
    max_hours = fields.Float(string='Max', compute="_compute_total_hours", store=True)
    mic_overtime = fields.Float(
        compute='_compute_mic_progress_hours',
        store=True
    )
    stage_dashboard = fields.Boolean(
        related='stage_id.display_on_dashboard',
        store=True
    )
    partner_timesheet_hours = fields.Float(
        related='partner_id.partner_timesheet_hours',
        store=True
    )

    def action_view_partner_timesheet(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("microcom_ts.microcom_full_timesheet_action_ro")
        action['domain'] = [
            ('partner_id', '=', self.partner_id.id)
        ]
        action['context'] = {'default_partner_id': self.partner_id.id}
        # action['views'] = [[False, 'list'], [False, 'form']]
        return action

    @api.depends('budget_line_ids.planned_hours', 'budget_line_ids.max_hours')
    def _compute_total_hours(self):
        for rec in self:
            rec.planned_hours = sum(line.planned_hours for line in rec.budget_line_ids)
            rec.max_hours = sum(line.planned_hours for line in rec.budget_line_ids)

    @api.constrains('budget_template_id')
    def constrains_update_budget_lines(self):
        for rec in self:
            rec.budget_line_ids.unlink()
            for line in rec.budget_template_id.line_ids:
                budget_vals = {
                    'name': line.name,
                    'task_id': rec.id,
                    'employee_ids': [Command.set(line.employee_ids.ids)],
                    'stage_ids': [Command.set(line.stage_ids.ids)],
                    'planned_hours': line.planned_hours,
                    'max_hours': line.max_hours,
                    'billing_code_id': line.billing_code_id.id,
                    'percentage': line.percentage,
                    'template_line_id': line.id}
                self.env['project.task.budget.line'].create(budget_vals)
            formula_lines = rec.budget_line_ids.filtered(lambda x: x.template_line_id.template_line_ids)
            for fl in formula_lines:
                lines = rec.budget_line_ids.filtered(lambda l: l.template_line_id.id in fl.template_line_id.template_line_ids.ids)
                fl.budget_line_ids = lines

    def button_save_as_template(self):
        if not self.budget_line_ids:
            raise UserError(_('No budget lines to save'))
        return {
            'name': _('Save budget template'),
            'view_mode': 'form',
            'res_model': 'wizard.budget.template',
            'type': 'ir.actions.act_window',
            'context': {'default_task_id': self.id},
            'target': 'new',
        }

    @api.constrains('budget_line_ids')
    def _constrains_budget_line(self):
        for rec in self:
            if rec.budget_line_ids:
                rec.planned_hours = sum(l.planned_hours for l in rec.budget_line_ids)
                rec.max_hours = sum(l.max_hours for l in rec.budget_line_ids)
                
    @api.depends('actual_duration', 'max_hours', 'planned_hours')
    def _compute_mic_progress_hours(self):
        for task in self:
            if (task.planned_hours > 0.0):
                task.mic_overtime = max(task.actual_duration - (task.max_hours or task.planned_hours), 0)
            else:
                task.mic_overtime = -1

    @api.depends('microcom_timesheet_ids')
    def _compute_open_ts_event(self):
        for record in self:
            open_event = record.microcom_timesheet_ids.filtered(
                lambda l: l.user_id == self.env.user and l.date == fields.Date.context_today(
                    self) and l.state == 'open' and l.temp_state == 'open')
            self.open_ts_event = open_event[:1]

    @api.depends('microcom_timesheet_ids')
    def _compute_timesheet_count(self):
        for record in self:
            record.timesheet_count = len(record.microcom_timesheet_ids.filtered(
                lambda l: l.user_id.id == record._uid))

    def _compute_is_open(self):
        for record in self:
            record.is_open = not (record.stage_id.is_closed_type or record.stage_id.is_canceled_type)

    def _compute_user_can_edit_budget(self):
        user_is_supervisor = self.user_has_groups('microcom_tasks.group_project_supervisor')
        for task in self:
            task.user_can_edit_budget = user_is_supervisor or (task.project_id.user_id == self.env.user)

    @api.onchange('user_id', 'date_deadline')
    def onchange_user_deadline(self):
        main_followup = self.followup_ids.filtered('is_main')
        if main_followup:
            main_followup.user_id = self.user_id
            main_followup.date_deadline = self.date_deadline

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        # when creating from TS request, followups are processed separately
        if not self.env.context.get('skip_fu', False):
            for record, vals in zip(res, vals_list):
                record.adjust_main_followup(vals)
        return res

    def write(self, vals):
        old_status = {}
        for record in self:
            old_status[record] = self._get_request_status(record.stage_id)
        res = super().write(vals)
        if not self.env.context.get('safe_request_status', False):
            for record in self:
                if old_status[record] != self._get_request_status(record.stage_id):
                    if record.request_pk > 0:
                        raise UserError('Please use button when changing request status')
        # some recursive write are called when creating from TS request
        if not self.env.context.get('skip_fu', False):
            self.adjust_main_followup(vals)
        return res

    @api.model
    def _get_request_status(self, stage_id):
        """ TS/MSSQL Request Status column
        """
        if stage_id.is_closed_type:
            return 0
        elif stage_id.is_canceled_type:
            return 1
        else:
            return 2

    def adjust_main_followup(self, vals):
        for record in self:
            main_followup = record.followup_ids.filtered('is_main')
            # use the first followup from assigned user as main if any
            # when linked to TS, we must create main followup if missing
            if 'followup_ids' in vals or 'request_pk' in vals:
                if not main_followup:
                    user_followups = record.followup_ids.filtered(lambda x: x.user_id == self.env.user)
                    if user_followups:
                        main_followup = user_followups[0]
                        main_followup.is_main = True
                    elif record.request_pk:
                        main_followup = self.env['project.task.followup'].create(record._prepare_main_followup())
            if main_followup:
                # update main followup
                main_vals = {}
                if 'date_deadline' in vals and record.date_deadline:
                    main_vals['date_deadline'] = record.date_deadline
                if 'user_id' in vals and record.user_id:
                    main_vals['user_id'] = record.user_id
                if main_vals:
                    # write will create a microcom.timesheet entry if there are none
                    # this will cause a deadlock in get_followup_from_uranos()
                    # we must explicitly create an entry if needed
                    #
                    context_today = fields.Date.context_today(record)
                    timesheet = record.microcom_timesheet_ids.filtered(
                        lambda x: x.user_id == self.env.user and x.state == 'open' and x.date == context_today)
                    if not timesheet:
                        action_msg = _('Action créée depuis Odoo')
                        time = self.env['microcom.timesheet'].calculate_now()
                        self.env['microcom.timesheet'].create(
                            record._prepare_timesheet(action_msg, start=time, end=time))
                    #
                    main_followup.write(main_vals)

    def button_create_ts_event(self):
        wiz = self.env['microcom.timesheet.create.event'].create({
            'task_id': self.id,
        })
        return {
            'name': _('Create Event'),
            'view_mode': 'form',
            'res_model': 'microcom.timesheet.create.event',
            'type': 'ir.actions.act_window',
            'res_id': wiz.id,
            'target': 'new',
        }

    def get_followup_id(self, user_id):
        open_followups = self.followup_ids.filtered(lambda x: x.state == 'open')
        best_followup_ids = open_followups.filtered(lambda x: x.user_id == user_id)
        if not best_followup_ids:
            best_followup_ids = open_followups.filtered(lambda x: x.is_main)
        if best_followup_ids:
            return best_followup_ids[0]
        return False

    def _prepare_timesheet(self, name, description=False, internal_comment=False, date=False, start=False, end=False,
                           billing_code=False):
        if not start:
            start = self.env['microcom.timesheet'].calculate_now()
        if not date:
            date = fields.Date.context_today(self)
        if not billing_code:
            billing_code = self.env['microcom.timesheet'].get_default_billing_code(
                task_id=self
            )

        return {
            'partner_id': self.partner_id.id,
            'user_id': self._uid,
            'task_id': self.id,
            'project_id': self.project_id.id,
            'date': date,
            'start_minute': start,
            'end_minute': end,
            'name': name,
            'description': description,
            'internal_comment': internal_comment,
            'billing_code_id': billing_code and billing_code.id,
        }

    def _prepare_main_followup(self):
        time = self.env['microcom.timesheet'].calculate_now()
        if time < 12 * 60:
            date = self.date_deadline or fields.Date.context_today(self)
            time = 17 * 60
        else:
            date = fields.Date.to_string(
                fields.Date.from_string(fields.Date.context_today(self)) + relativedelta(days=1))
            time = 12 * 60
        name = 'resp: ' + self.name or ''

        return {
            'name': name,
            'date_deadline': date,
            'deadline_minute': time,
            'user_id': self.user_id.id,
            'state': 'open',
            'task_id': self.id,
            'is_main': True
        }

    def button_stop_event(self):
        self.ensure_one()
        active_timesheet = self.microcom_timesheet_ids.filtered(
            lambda ts: ts.user_id == self.env.user
                       and ts.date == fields.Date.context_today(self)
                       and ts.state == 'open'
                       and ts.temp_state == 'open'
        )[:1]
        if active_timesheet:
            active_timesheet.end_minute = self.env['microcom.timesheet'].calculate_now()
            active_timesheet.duration_minute = active_timesheet.end_minute - active_timesheet.start_minute
            active_timesheet.temp_state = 'closed'

    def close_request_button(self):
        """ replace partial behavior
        """
        if self.env.context.get('no_create_timesheet'):
            stage_id = self.env['project.task.type'].search([('is_closed_type', '=', True)], limit=1)
            self.with_context(safe_request_status=True).write(
                {
                    'stage_id': stage_id.id
                }
            )
        wiz = self.env['microcom.timesheet.close.request'].create({
            'mode': 'close',
            'task_id': self.id,
        })
        wiz._onchange_task_id()
        return {
            'name': _('Close Task'),
            'view_mode': 'form',
            'res_model': 'microcom.timesheet.close.request',
            'type': 'ir.actions.act_window',
            'res_id': wiz.id,
            'target': 'new',
        }

    def reopen_request_button(self):
        """ replace partial behavior
        """
        wiz = self.env['microcom.timesheet.close.request'].create({
            'mode': 'open',
            'task_id': self.id,
        })
        wiz._onchange_task_id()
        return {
            'name': _('Reopen Request'),
            'view_mode': 'form',
            'res_model': 'microcom.timesheet.close.request',
            'type': 'ir.actions.act_window',
            'res_id': wiz.id,
            'target': 'new',
        }

    def button_synchronize_followup(self):
        with open_ts_cursor(self) as cursor:
            if cursor is None:
                raise ValidationError(_('TS is not connected'))
            write_fu_from_request(self, self.request_pk, cursor)

    def _nightly_synchronize_followup(self):
        open_task_ids = self.env['project.task'].search([('stage_id.is_closed_type', '=', False),
                                                         ('stage_id.is_canceled_type', '=', False)])
        for task in open_task_ids:
            task.button_synchronize_followup()


class ProjectTaskFollowup(models.Model):
    _name = 'project.task.followup'
    _description = 'followup'
    _order = 'is_main desc, state desc, date_deadline'

    name = fields.Char('Name', required=True)
    description = fields.Text('Description')
    user_id = fields.Many2one('res.users', string='User', required=True)
    user_ref = fields.Char('User Ref.', related="user_id.partner_id.ref")
    task_id = fields.Many2one('project.task', string='Task')
    customer_partner_id = fields.Many2one('res.partner', string='Customer', related="task_id.partner_id")
    customer_partner_ref = fields.Char('Customer Reference', related="task_id.partner_id.ref")
    date_deadline = fields.Date('Deadline', required=True)
    deadline_minute = fields.Integer('Deadline Minute')
    deadline_time = fields.Char('Time', compute='_compute_deadline_time', readonly=False)
    state = fields.Selection([('open', 'Open'), ('cancel', 'Cancel'), ('close', 'Close')], 'State', default='open')
    pk_followup = fields.Integer('PK Followup')
    is_main = fields.Boolean('Main Followup')
    has_changes = fields.Boolean('Has Changes', compute='_compute_uranos_changes', compute_sudo=True)
    uranos_changes = fields.Text('Changes', compute='_compute_uranos_changes', compute_sudo=True)
    uranos_followup_id = fields.Many2one('uranos.followup', compute="_compute_uranos_followup", store=True)
    overdue = fields.Boolean('Overdue', compute="_compute_overdue", store=True)
    billing_code_id = fields.Many2one('microcom.timesheet.billing', string="Code")
    duration_minute = fields.Integer(string="Duration Minute")
    mic_overtime = fields.Float(
        related='task_id.mic_overtime',
        store=True
    )

    @api.onchange('deadline_time')
    def _onchange_deadline_time(self):
        for record in self:
            if record.deadline_time == '=':
                record.deadline_minute = self.env['microcom.timesheet'].calculate_now()
            else:
                record.deadline_minute = self.env['microcom.timesheet'].convert_char2minute(record.deadline_time)

    @api.depends('pk_followup')
    def _compute_uranos_followup(self):
        for record in self:
            record.uranos_followup_id = self.env['uranos.followup'].search([('pk_followup', '=', record.pk_followup)])

    @api.depends('deadline_minute')
    def _compute_deadline_time(self):
        for record in self:
            record.deadline_time = self.env['microcom.timesheet'].convert_minute2char(record.deadline_minute)

    @api.depends('deadline_minute', 'date_deadline')
    def _compute_overdue(self):
        now_minute = self.env['microcom.timesheet'].calculate_now()
        today = fields.Date.context_today(self)
        for record in self:
            if record.date_deadline and record.state == 'open' and record.date_deadline < today or (
                    record.date_deadline == today and record.deadline_minute < now_minute):
                record.overdue = True
            else:
                record.overdue = False


    @api.model
    def create(self, vals):
        res = super().create(vals)
        if not self.env.context.get('no_uranos_create'):
            # deadlock if quickTS entry is not explicitly created
            # get the pk_action passed in context else trying to select it from a ts record
            # the pk_action would be passed in the context in case where the current ts record
            # as not finished the process
            pk_action = self.env.context.get('pk_action') or res._select_microcom_timesheet().pk_action
            res.pk_followup = create_ts_followup(res, pk_action)
        return res

    def write(self, vals):
        res = super().write(vals)
        #
        if not self.env.context.get('no_uranos_create'):
            if set(vals).intersection({'name', 'description', 'date_deadline', 'deadline_minute', 'user_id',
                                       'billing_code_id', 'duration_minute'}):
                # deadlock if quickTS entry is not explicitly created
                pk_action = self.env.context.get('pk_action') or self._select_microcom_timesheet().pk_action
                update_followup(self, pk_action)
        return res

    def name_get(self):
        res = []
        for followup in self:
            name = followup.name or ''
            code = followup.user_ref or ''
            if self._context.get('show_user_code'):
                if code:
                    name = "[%s] %s" % (code, name)
                else:
                    name = "%s" % name
            else:
                name = name
            res.append((followup.id, name))
        return res

    def _select_microcom_timesheet(self):
        microcom_timesheet_id = self.env['microcom.timesheet'].search([
            ('task_id', '=', self.task_id.id),
            ('user_id', '=', self.env.user.id),
            ('state', '=', 'open'),
        ], order='id desc', limit=1)
        if not microcom_timesheet_id:
            action_msg = _('Entry created by update followup')
            time = self.env['microcom.timesheet'].calculate_now()
            microcom_timesheet_id = self.env['microcom.timesheet'].create(
                self.task_id._prepare_timesheet(action_msg, start=time, end=time))

            if not microcom_timesheet_id.billing_code_id:
                # set billing code
                microcom_timesheet_id.onchange_user_project()
            microcom_timesheet_id.followup_id = self
        if not microcom_timesheet_id.pk_action:
            # force sync
            microcom_timesheet_id.update_ts({})
        return microcom_timesheet_id

    def button_close_followup(self):
        self.state = 'close'
        microcom_timesheet_id = self._select_microcom_timesheet()
        pk_action = microcom_timesheet_id.pk_action
        open_close_followup(self.pk_followup, task=self.task_id, pk_action=pk_action, action='close')

    def button_open_followup(self):
        self.state = 'open'
        microcom_timesheet_id = self._select_microcom_timesheet()
        pk_action = microcom_timesheet_id.pk_action
        open_close_followup(self.pk_followup, task=self.task_id, pk_action=pk_action, action='open')

    def button_sync(self):
        with open_ts_cursor(self) as cursor:
            if cursor is None:
                raise ValidationError(_('TS is not connected'))
            self.sync_followup(cursor)

    def button_do_nothing(self):
        pass

    @api.depends('uranos_followup_id.write_date', 'write_date')
    def _compute_uranos_changes(self):
        for record in self:
            if not record.uranos_followup_id:
                record.has_changes = False
                continue
            change_list = []
            uranos_followup_id = record.uranos_followup_id
            if record.name != uranos_followup_id.name:
                change_list.append((_('Name'), uranos_followup_id.name, record.name))
            if record.description != uranos_followup_id.description:
                change_list.append((_('Description'), uranos_followup_id.description, record.description))
            # TODO add internal_comment and possibility to edit Description.
            # if record.internal_comment != uranos_followup_id.internal_comment:
            #    change_list.append((_('Internal Comment'), uranos_followup_id.internal_comment, record.internal_comment))
            if record.date_deadline != uranos_followup_id.date_due:
                change_list.append((_('Deadline'), uranos_followup_id.date_due, record.date_deadline))
            if record.deadline_minute != uranos_followup_id.time_due:
                change_list.append((_('Time'), uranos_followup_id.time_due, record.deadline_minute))
            record.uranos_changes = '\n'.join('{}: {} → {}'.format(a, b or '', c or '') for a, b, c in change_list)
            record.has_changes = bool(change_list)

    def sync_followup(self, cursor):
        assert cursor

        sql = """
                SELECT fu.PK_FollowUP, fu.Name, fu.Description, fu.DateDue, fu.TimeDue, fu.DefaultBillingID, fu.Status
                FROM [FollowUp] fu
                WHERE PK_FollowUp = %d
            """
        sql_args = (self.pk_followup,)
        cursor.execute(sql, sql_args)
        uranos_followup = cursor.fetchone()
        if uranos_followup:
            self.update_task_followup(uranos_followup)

    def update_task_followup(self, uranos_followup):
        billing_id = self.env['microcom.timesheet.billing'].search(
            [('pk_typebilling', '=', uranos_followup['DefaultBillingID'])])
        self.with_context({'no_uranos_create': True}).write({
            'name': uranos_followup['Name'] or '.',
            'description': uranos_followup['Description'],
            'date_deadline': uranos_followup['DateDue'],
            'deadline_minute': uranos_followup['TimeDue'],
            'billing_code_id': billing_id.id,
            'state': STATE_STRING.get(uranos_followup['Status'])
        })

    def _patch_sync_followup(self):
        followups = self.search([('pk_followup', '!=', False)])
        with open_ts_cursor(self) as cursor:
            if cursor is None:
                raise ValidationError(_('TS is not connected'))
            for followup in followups.with_context(no_progression=True):
                update_followup(followup, None)


class TaskBudgetTemplate(models.Model):
    _name = 'task.budget.template'
    _description = 'Template of budget'

    name = fields.Char('Template Name', required=True)
    line_ids = fields.One2many('task.budget.template.line', 'template_id', 'Lines')


class TaskBudgetTemplateLine(models.Model):
    _name = 'task.budget.template.line'
    _description = 'Line of budget for template'

    name = fields.Char('Description', required=True)
    template_id = fields.Many2one('task.budget.template', 'Template')
    employee_ids = fields.Many2many('hr.employee', string='Expected Employees', required=True)
    billing_code_id = fields.Many2one('microcom.timesheet.billing', 'Billing Code')
    planned_hours = fields.Float('Min')
    max_hours = fields.Float('Max')
    stage_ids = fields.Many2many('project.task.type', string='Stages', required=True)
    percentage = fields.Float('Percentage', required=True)
    template_line_ids = fields.Many2many('task.budget.template.line', 'budget_template_rel', 'temp_line1', 'temp_line2', string='Lines')

    @api.onchange('employee_ids')
    def onchange_employee_ids(self):
        for budget in self:
            if budget.employee_ids and not budget.billing_code_id:
                budget.billing_code_id = budget.employee_ids[0].billing_code_id

    def button_recompute_hours(self):
        if self.template_line_ids and self.percentage:
            planned_hours = sum(l.planned_hours for l in self.template_line_ids)
            self.planned_hours = planned_hours * self.percentage / 100
            max_hours = sum(l.max_hours for l in self.template_line_ids)
            self.max_hours = max_hours * self.percentage / 100


class ProjectTaskBudgetLine(models.Model):
    _name = 'project.task.budget.line'
    _description = 'Line of budget'

    name = fields.Char('Description', required=True)
    task_id = fields.Many2one('project.task', 'Task')
    employee_ids = fields.Many2many('hr.employee', string='Expected Employees')
    billing_code_id = fields.Many2one('microcom.timesheet.billing', 'Billing Code')
    planned_hours = fields.Float('Min')
    max_hours = fields.Float('Max')
    stage_ids = fields.Many2many('project.task.type', string='Stages')
    template_line_id = fields.Many2one('task.budget.template.line', 'Template line')
    planned_hours_bg_color = fields.Char('Planned hours bg color', compute='_compute_durations_bg_color')
    max_hours_bg_color = fields.Char('Max hours bg color', compute='_compute_durations_bg_color')
    allowed_stage_ids = fields.Many2many('project.task.type', related="task_id.project_id.type_ids")
    percentage = fields.Float('Percentage', required=True)
    budget_line_ids = fields.Many2many('project.task.budget.line','budget_line_rel','line1_id', 'line2_id', string='Lines')

    @api.depends('budget_line_ids', 'planned_hours', 'max_hours')
    def _compute_durations_bg_color(self):
        for record in self:
            record.planned_hours_bg_color = False
            record.max_hours_bg_color = False
            COLOR_BAD_MIN = 'rgba(255,255,0,0.3)'
            COLOR_BAD_MAX = 'rgba(255,255,0,0.3)'
            if record.budget_line_ids and record.percentage:
                planned_hours = sum(l.planned_hours for l in record.budget_line_ids)
                formula_planned_hours = planned_hours * record.percentage / 100
                max_hours = sum(l.max_hours for l in record.budget_line_ids)
                formula_max_hours = max_hours * record.percentage / 100
                if formula_planned_hours != record.planned_hours:
                    record.planned_hours_bg_color = COLOR_BAD_MIN
                if formula_max_hours != record.max_hours:
                    record.max_hours_bg_color = COLOR_BAD_MAX

    @api.constrains('max_hours', 'planned_hours')
    def constrains_planned_hours(self):
        for rec in self:
            if rec.planned_hours or rec.max_hours:
                rec.task_id._constrains_budget_line()

    @api.onchange('employee_ids')
    def onchange_employee_ids(self):
        for budget in self:
            if budget.employee_ids and not budget.billing_code_id:
                employee = budget.employee_ids[0]
                budget.billing_code_id = employee.billing_code_id
                if budget.task_id.partner_id and budget.task_id.project_id:
                    project_rate = self.env['timesheet.invoice.rate'].search([
                        ('project_id', '=', budget.task_id.project_id.id),
                        ('partner_id', '=', budget.task_id.partner_id.id),
                        ('employee_id', '=', employee.id)
                    ], limit=1)
                    if not project_rate:
                        project_rate = self.env['timesheet.invoice.rate'].search([
                            ('partner_id', '=', budget.task_id.partner_id.id),
                            ('employee_id', '=', employee.id)
                        ], limit=1)
                    if project_rate:
                        budget.billing_code_id = project_rate.billing_code_id

    def button_recompute_hours(self):
        if self.budget_line_ids and self.percentage:
            planned_hours = sum(l.planned_hours for l in self.budget_line_ids)
            self.planned_hours = planned_hours * self.percentage / 100
            max_hours = sum(l.max_hours for l in self.budget_line_ids)
            self.max_hours = max_hours * self.percentage / 100
