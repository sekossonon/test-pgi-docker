# -*- coding: utf-8 -*-

import datetime
import logging
import pytz
import random
import json

from collections import namedtuple

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.uranos_ts.project_issue import (
    ADDRESSES_PK_MAP,
    ADDRESSES_TYPE_MAP,
    create_action_inner,
    create_request_inner,
    create_travel_expense,
    delete_uranos_event,
    delete_travel_expense,
    open_ts_cursor,
)
from .project_task import create_ts_followup, update_followup

_logger = logging.getLogger(__name__)

UNKNOWN_BILLING = '????'

ADDRESS_SELECTION = [
    ('office', _('Office')),
    ('customer', _('Customer')),
    ('residence', _('Residence')),
]

TS_COLUMNS = {
    'pk_event',
    'user_id',
    'partner_id',
    'task_id',
    'billing_code_id',
    'date',
    'start_minute',
    'end_minute',
    'pk_action',
    'pk_request',
    'pk_billing',
    'name',
    'description',
    'internal_comment',
    'duration_minute',
    'state',
}

TS_TRAVEL_COLUMNS = {
    'pk_event',
    'event_end_minute',
    'event_start_minute',
    'start_address',
    'destination_address',
    'return_address',
    'start_km',
    'return_km',
}


def get_pk_action_for_date_user(self, cursor, date_start, pk_contact):
    assert cursor

    # state closed == 1
    sql = """
        SELECT e.PK_Event, a.PK_Action
        FROM [Event] e
        JOIN [Action] a ON a.EventID = e.PK_Event
        WHERE e.DateStartEvent = %s and e.Employee_ContactID = %d and e.state <> 1
    """
    sql_args = (date_start, pk_contact)
    cursor.execute(sql, sql_args)
    found = cursor.fetchall()
    return {x['PK_Action'] for x in found}


def pull_ts_from_event(self, cursor, pk_action):
    # internal safe operation, must find archived entries
    self = self.sudo().with_context(active_test=False)
    assert cursor

    def get_partner(pk_contact):
        return self.env['res.partner'].search([('pk_contact', '=', pk_contact)])

    def get_user(pk_contact):
        return self.env['res.users'].search([('pk_contact', '=', pk_contact)])

    def get_task(pk_request):
        return self.env['project.task'].search([('request_pk', '=', pk_request)])

    def fix_null(text):
        # convert null/None to null/False
        if text is None:
            return False
        return text

    def fix_numeric_null(number):
        if number is None:
            return 0
        return number

    def get_status(status):
        mapping = {
            0: 'open',
            1: 'closed',
            2: 'supervised',
            3: 'corrected',
            4: 'billed',
            # 5: 'cancelled',
        }
        return mapping.get(status, 'open')

    sql = """
        SELECT e.PK_Event, e.Employee_ContactID, r.Customer_ContactID,
            e.DateStartEvent, e.TimeStartEvent, e.TimeEndEvent,
            a.PK_Action, a.RequestID, a.BillingID, a.Name, a.Description, a.InternalComment, a.Status,
            b.BillingTime, b.TypeBillingID, TypeWork.Name as WorkCode, TypeRate.Name as RateCode
        FROM [Event] e
        JOIN [Action] a ON a.EventID = e.PK_Event
        JOIN [Billing] b on b.PK_Billing = a.BillingID
        JOIN [Request] r on r.PK_Request = a.RequestID
        Left Join TypeBilling on TypeBilling.PK_Type = b.TypeBillingID
        Left Join TypeWork on TypeWork.PK_Type = TypeBilling.WorkCodeID
        Left Join TypeRate on TypeRate.PK_Type = TypeBilling.RateCodeID
        WHERE PK_Action = %d
    """
    sql_args = (pk_action,)
    cursor.execute(sql, sql_args)
    found = cursor.fetchone()
    if not found:
        return {}
    # billing mapping
    billing_code_id = self.env['microcom.timesheet.billing']
    billing_pk = found['TypeBillingID']
    if billing_pk:
        billing_code_id = self.env['microcom.timesheet.billing'].search(
            [('pk_typebilling', '=', billing_pk)])
        if not billing_code_id:
            billing_code_id = self.env['microcom.timesheet.billing'].create({
                'name': UNKNOWN_BILLING,
                'pk_typebilling': billing_pk,
            })

    ts_dict = {
        'pk_event': found['PK_Event'],
        'user_id': get_user(found['Employee_ContactID']),
        'partner_id': get_partner(found['Customer_ContactID']),
        'task_id': get_task(found['RequestID']),
        'billing_code_id': billing_code_id,
        # returns datetime, expects date
        'date': found['DateStartEvent'].date(),
        'start_minute': found['TimeStartEvent'],
        'end_minute': found['TimeEndEvent'],
        'pk_action': found['PK_Action'],
        'pk_request': found['RequestID'],
        'pk_billing': found['BillingID'],
        # returns None for null, expects False
        'name': fix_null(found['Name']),
        'description': fix_null(found['Description']),
        'internal_comment': fix_null(found['InternalComment']),
        'duration_minute': fix_numeric_null(found['BillingTime']),
        'state': get_status(found['Status']),
    }
    if TS_COLUMNS != set(ts_dict.keys()):
        raise ValidationError(_('TS_COLUMNS has changed'))
    return ts_dict


def push_event_to_ts(self, cursor):
    assert cursor

    def fix_null(text):
        # convert null/None to null/False
        if text is False:
            return None
        return text

    # Event
    sql = """
        UPDATE [Event]
        SET Employee_ContactID = %s,
            DateStartEvent = %s,
            TimeStartEvent = %d,
            TimeEndEvent = %d
        WHERE PK_Event = %d
    """
    sql_args = (
        self.user_id.partner_id.pk_contact,
        self.date,
        self.start_minute,
        self.end_minute,
        self.event_id.pk_event)
    cursor.execute(sql, sql_args)
    # Action
    sql = """
        UPDATE [Action]
        SET Name = %s,
            Description = %s,
            InternalComment = %s,
            EventID = %s,
            RequestID = %s
        WHERE PK_Action = %d
    """
    sql_args = (
        fix_null(self.name),
        fix_null(self.description),
        fix_null(self.internal_comment),
        self.event_id.pk_event,
        self.task_id.request_pk,
        self.pk_action)
    cursor.execute(sql, sql_args)
    # Billing
    sql = """
        UPDATE [Billing]
        SET BillingTime = %d,
            TypeBillingID = %d
        WHERE PK_Billing = %d
    """
    sql_args = (
        self.duration_minute,
        self.billing_code_id.pk_typebilling or None,
        self.pk_billing)
    cursor.execute(sql, sql_args)

    # TravelExpense
    sql = """
            UPDATE [TravelExpense]
            SET AddressStartID = %d,
                TypeStart = %d,
                AddressReturnID = %d,
                TypeReturn = %d,
                AddressDestinationID = %d,
                StartKilometres = %d,
                ReturnKilometres = %d,
                TimeStartOnSite = %d,
                TimeEndOnSite = %d
            WHERE EventID = %d
        """
    sql_args = (
        ADDRESSES_PK_MAP.get(self.event_id.start_address),
        ADDRESSES_TYPE_MAP.get(self.event_id.start_address),
        ADDRESSES_PK_MAP.get(self.event_id.return_address),
        ADDRESSES_TYPE_MAP.get(self.event_id.return_address),
        ADDRESSES_PK_MAP.get(self.event_id.destination_address),
        self.event_id.start_km,
        self.event_id.return_km,
        self.event_id.start_minute,
        self.event_id.end_minute,
        self.event_id.pk_event)
    cursor.execute(sql, sql_args)


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

class TimesheetCalculationsMixin(models.AbstractModel):
    _name = 'microcom.timesheet.calculations.mixin'
    _description = _('Microcom timesheet calculation mixin')

    def _default_time(self):
        return self.calculate_now()

    def calculate_now(self):
        tz_name = self.env.context.get('tz')
        naive_now = datetime.datetime.now()
        time_now = utc_to_tz_naive_datetime(tz_name, naive_now)
        return time_now.hour * 60 + time_now.minute

    def convert_minute2char(self, minute):
        return '{}:{:02}'.format(*divmod(minute or 0, 60))

    def convert_char2minute(self, time):
        # normal time string
        if time:
            parts = [time[:-2], time[-2:]]
            if ':' in time:
                parts = time.split(':')
            elif 'h' in time:
                parts = time.split('h')
            try:
                minutes = int(parts[0] or '0') * 60 + int(parts[1] or '0')
            except ValueError:
                raise UserError(_('%s is not valid time') % time)
            if minutes < 0 or minutes >= 24 * 60:
                raise UserError(_('Time must be between 0:00 and 23:59'))
            return minutes
        else:
            return 0


class Timesheet(models.Model):
    _name = 'microcom.timesheet'
    _description = 'Timesheet for microcom, synchronized with uranos timesheet'
    _inherit = 'microcom.timesheet.calculations.mixin'
    _order = 'date, start_minute, id'

    task_name = fields.Char(string="Task Name", related='task_id.name')
    project_name = fields.Char(string="Project Name", related='project_id.name')
    task_id_domain = fields.Char(string="Task domain", store=False, readonly=True, compute="_compute_task_domain")
    project_id_domain = fields.Char(string="Project domain", store=False, readonly=True,
                                    compute="_compute_project_domain")
    user_id = fields.Many2one('res.users', 'Employee', default=lambda x: x.env.user)
    user_ref = fields.Char(related='user_id.ref')
    task_id = fields.Many2one('project.task', 'Task', ondelete='restrict')
    is_task_open = fields.Boolean(related='task_id.is_open')
    name = fields.Char('Short Description')
    description = fields.Text('Description')
    internal_comment = fields.Text('Internal Comment')
    billing_code_id = fields.Many2one('microcom.timesheet.billing', 'Code',
                                      help="""
                                      Voici les principaux codes.
                                      F# - Facturable. - Client
                                      G7 - Sous Garantie (Non facturable) - Client
                                      S7 - Soumission (Non facturable) - Client
                                      D7 - Travail interne. - Microcom
                                      P7 - Perte de temps. - Microcom
                                      C7 - Cours / Formation - Microcom
                                      Z0 - Temps personnel (Non payé - Dîner, pause, etc.)
                                      # = 1,2,3,4,5,6,8,9,A,B...
                                      Demandez le code qui corresponds à votre poste.
                                      """)
    billing_code_letter = fields.Char(related='billing_code_id.letter', store=True)
    billing_group_id = fields.Many2one(
        related='billing_code_id.group_id',
        string='Billing Group',
        store=True, ondelete="set null")
    state = fields.Selection([
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('supervised', 'Supervised'),
        ('corrected', 'Corrected'),
        ('billed', 'Billed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='open')
    # temp_stete allows to flag timesheet as closed before it will close on timesheet.
    # Used for the buttons "Stop Request" and "Create Request"
    temp_state = fields.Selection([
        ('open', 'Open'),
        ('closed', 'Closed')
    ], string='Temp Status', default='open')
    date = fields.Date('Day', default=fields.Date.context_today)
    start_minute = fields.Integer('Start Minute', default=lambda self: self._default_time())
    end_minute = fields.Integer('End Minute')
    duration_minute = fields.Integer('Duration Minute')
    start_time = fields.Char('Start', compute='_compute_start_time', readonly=False)
    end_time = fields.Char('End', compute='_compute_end_time', readonly=False)
    duration_time = fields.Char('Duration', compute='_compute_duration_time', readonly=False,
                                help="""
                                Il y a 2 codes spéciaux qu'on peut utiliser
                                = : permet de calculer automatiquement "Fin - Début"
                                == : permet de calculer automatiquement les trous dans une période de temps.
                                """)
    uranos_changes = fields.Text('Changes', compute='_compute_uranos_changes')
    has_changes = fields.Boolean('Has Changes', compute='_compute_uranos_changes')
    # uranos fields
    pk_event = fields.Integer(string='Pk_Event', related='event_id.pk_event')
    pk_travel_expense = fields.Integer(string='Pk_TravelExpense', related='event_id.pk_travel_expense')
    pk_action = fields.Integer(string='Pk_Action', copy=False)
    pk_request = fields.Integer(string='Pk_Request', copy=False)
    pk_billing = fields.Integer(string='Pk_Billing', copy=False)
    uranos_action_id = fields.Many2one(
        'uranos.action', 'Uranos Action', compute='_compute_uranos_action', store=True)
    action_status = fields.Char(
        related='uranos_action_id.status', depends=['uranos_action_id', 'uranos_action_id.status'],
        store=True, string='Action Status')
    overlap = fields.Selection([
        ('single', 'Singleton'),
        ('full', 'Full'),
        ('overflow', 'Excess'),
        ('underflow', 'Short'),
        ('weft', 'Interrupted')
    ], string='Overlap')
    overlap_minute = fields.Integer('Overlap Minutes')
    overlap_fg_color = fields.Char('Foreground Color', compute='_compute_overlap_colors')
    overlap_bg_color = fields.Char('Overlap Background Color', compute='_compute_overlap_colors')
    # filter help
    partner_id = fields.Many2one('res.partner', string='Customer')
    project_id = fields.Many2one('project.project', string='Project')
    project_department_id = fields.Many2one(related='project_id.department_id', string='Project Department', store=True)
    is_first_of_day = fields.Boolean('FOD', compute='compute_is_first_of_day')
    followup_id = fields.Many2one('project.task.followup', string='Followup')
    pk_followup = fields.Integer('PK Followup', related='followup_id.pk_followup')
    # microcom event fields
    event_id = fields.Many2one('microcom.timesheet.event', string='Event',
                               domain="[('start_date', '=', date), ('user_id', '=', user_id)]",
                               readonly=True)
    start_date = fields.Date('Start Date', related='event_id.start_date', readonly=True)
    event_start_minute = fields.Integer(related='event_id.start_minute', readonly=False)
    event_end_minute = fields.Integer(related='event_id.end_minute', readonly=False)
    event_duration_minute = fields.Integer(related='event_id.duration_minute', readonly=False)
    time_start_on_site = fields.Char('Time of arrival on site', compute='_compute_time_start_on_site', readonly=False)
    time_end_on_site = fields.Char('Departure time on site', compute='_compute_time_end_on_site', readonly=False)
    destination_address = fields.Selection(string='Destination Address',
                                           related='event_id.destination_address', readonly=False)
    start_address = fields.Selection(string='Start Address', related='event_id.start_address',
                                     depends=["event_id.start_address"], readonly=False)
    return_address = fields.Selection(string='Return Address', related='event_id.return_address',
                                      depends=["event_id.return_address"], readonly=False)
    start_km = fields.Float(related='event_id.start_km', readonly=False)
    return_km = fields.Float(related='event_id.return_km', readonly=False)
    request_km_refund = fields.Boolean(related='event_id.request_km_refund', readonly=False)
    has_transport_info = fields.Boolean(related='event_id.has_transport_info', readonly=False)
    line_bg_color = fields.Char('Background Color', related='event_id.line_bg_color', readonly=False)
    line_label_color = fields.Char('rgba(R,G,B[,A])', readonly=False)
    # end microcom event fields
    final_state = fields.Boolean('Final State')
    has_rsde = fields.Boolean(string="Has R&D",)
    planned_hours = fields.Float(related='task_id.planned_hours', string='Planned Hours')
    actual_duration = fields.Float(related='task_id.actual_duration', string='Actual Hours')
    actual_duration_color = fields.Char(compute='_compute_actual_duration_color')
    budget_line_id = fields.Many2one('project.task.budget.line', 'Budget line')
    total_budget = fields.Float('Budget', related='budget_line_id.planned_hours')
    spent_budget = fields.Float('Spent', compute='_compute_spent_budget')
    percent_spent_budget = fields.Float('%', compute='_compute_spent_budget')
    budget_fields_color = fields.Char('Budget fields color', compute='_compute_budget_fields_color')
    # uranos work fields
    employee_department_id = fields.Many2one(related="user_id.department_id", store=True)
    billing_time_reel = fields.Float(related="uranos_action_id.billing_time_reel", store=True)
    billing_rate = fields.Float(
        related="uranos_action_id.billing_rate", groups='uranos_ts.group_uranos_ts_admin', store=True)
    billing_amount = fields.Float(related="uranos_action_id.billing_amount",
                                  groups='uranos_ts.group_uranos_ts_admin', store=True)
    request_stage_id = fields.Many2one('project.task.type', 'Request Status', store=True, related='task_id.stage_id')
    billing_time = fields.Float('Cost Hours', related='uranos_action_id.billing_time', store=True)
    pay_rate_work = fields.Float('Cost Rate', related='uranos_action_id.pay_rate_work', store=True,
                                 group_operator="avg", groups='uranos_ts.group_uranos_ts_admin')
    billing_cost_bm = fields.Float(related='uranos_action_id.billing_cost_bm', store=True,
                                   groups='uranos_ts.group_uranos_ts_admin')
    profit = fields.Float(related="uranos_action_id.profit", store=True, groups='uranos_ts.group_uranos_ts_admin')
    statement_id = fields.Char(related='uranos_action_id.statement_id', store=True)
    fiscal_year = fields.Char('Fiscal Year', compute='_compute_fiscal_period', store=True)
    fiscal_quarter = fields.Char('Fiscal Quarter', compute='_compute_fiscal_period', store=True)
    project_category_id = fields.Many2one(related='project_id.project_category_id', store=True)
    client_category_id = fields.Many2one(related='partner_id.client_category_id', store=True)
    total = fields.Char('Total', default='Total')

    @api.depends('date')
    def _compute_fiscal_period(self):
        for record in self:
            if record.date:
                start_date = record.date
                year = start_date.year
                month = start_date.month
                # avril is the last month of the fiscal year
                if month > 4:
                    year += 1
                record.fiscal_year = 'AVR {}'.format(year)
                record.fiscal_quarter = 'T{} AVR {}'.format((month + 2) // 3, year)
            else:
                record.fiscal_year = False
                record.fiscal_quarter = False

    @api.constrains('date')
    def constrains_start_date(self):
        for rec in self:
            if rec.date:
                minimum_date = rec.project_id.company_id.minimum_date
                ts_admin_rights = 'uranos_ts.group_uranos_ts_admin,uranos_ts.group_uranos_approval'
                user_is_admin = self.user_has_groups(ts_admin_rights)
                if user_is_admin:
                    minimum_date = rec.project_id.company_id.minimum_admin_date
                if minimum_date and minimum_date > rec.date:
                    raise UserError("This period is currently closed, contact a manager to make corrections")

    @api.depends('budget_line_id')
    def _compute_spent_budget(self):
        for rec in self:
            if rec.budget_line_id:
                timesheets = self.env['microcom.timesheet'].search([('budget_line_id', '=', rec.budget_line_id.id)])
                rec.spent_budget = sum(ts.duration_minute / 60 for ts in timesheets)
            else:
                rec.spent_budget = 0
            rec.percent_spent_budget = rec.spent_budget * 100 / (rec.total_budget or 1)

    @api.depends('percent_spent_budget')
    def _compute_budget_fields_color(self):
        RED = 'rgba(255, 0, 0, 0.5)'
        YELLOW = 'rgba(255, 255, 0, 0.5)'
        for record in self:
            if record.percent_spent_budget >= 75 and record.percent_spent_budget <= 90:
                record.budget_fields_color = YELLOW
            elif record.percent_spent_budget > 90:
                record.budget_fields_color = RED
            else:
                record.budget_fields_color = False

    @api.depends('partner_id', 'project_id')
    def _compute_task_domain(self):
        for rec in self:
            task_id_domain = [
                ('stage_id.is_closed_type', '=', False),
                ('stage_id.is_canceled_type', '=', False)]
            if rec.partner_id:
                task_id_domain += [('partner_id', '=', rec.partner_id.id)]
            if rec.project_id:
                task_id_domain += [('project_id', '=', rec.project_id.id)]
            rec.task_id_domain = json.dumps(task_id_domain)

    @api.depends('partner_id', 'project_id')
    def _compute_project_domain(self):
        for rec in self:
            project_id_domain = []
            if rec.partner_id:
                # allow projects for selected client and projects shared across all clients
                project_id_domain = [
                    '|',
                    ('partner_id', '=', rec.partner_id.id),
                    ('partner_id', '=', False)
                ]
            rec.project_id_domain = json.dumps(project_id_domain)

    @api.depends('pk_action')
    def _compute_uranos_action(self):
        for record in self:
            record.uranos_action_id = self.env['uranos.action'].search([('pk_action', '=', record.pk_action)], limit=1)

    @api.depends('uranos_action_id.write_date', 'write_date')
    def _compute_uranos_changes(self):
        for record in self:
            if not record.uranos_action_id:
                record._compute_uranos_action()
            if not record.uranos_action_id:
                record.uranos_changes = _('Action entry not found')
                record.has_changes = False
                continue
            change_list = []
            uranos_action_id = record.uranos_action_id
            if record.name != uranos_action_id.name:
                change_list.append((_('Name'), uranos_action_id.name, record.name))
            if record.description != uranos_action_id.description:
                change_list.append((_('Description'), uranos_action_id.description, record.description))
            if record.internal_comment != uranos_action_id.internal_comment:
                change_list.append((_('Internal Comment'), uranos_action_id.internal_comment, record.internal_comment))
            if record.date != uranos_action_id.date_start_event:
                change_list.append((_('Date'), uranos_action_id.date_start_event, record.date))
            if record.start_time != uranos_action_id.time_start_event:
                change_list.append((_('Start'), uranos_action_id.time_start_event, record.start_time))
            if record.end_time != uranos_action_id.time_end_event:
                change_list.append((_('End'), uranos_action_id.time_end_event, record.end_time))
            billing_minute = uranos_action_id.billing_id.billing_time
            if record.duration_minute != billing_minute:
                change_list.append((_('Duration'), self.convert_minute2char(billing_minute), record.duration_time))
            status = uranos_action_id.status.lower()
            if record.state != status:
                change_list.append((_('Status'), uranos_action_id.status, record.state))
            if record.pk_event != uranos_action_id.pk_event:
                change_list.append((_('Event'), uranos_action_id.pk_event, record.pk_event))
            record.uranos_changes = '\n'.join('{}: {} → {}'.format(a, b or '', c or '') for a, b, c in change_list)
            record.has_changes = bool(change_list)
            # explain some failures
            if not uranos_action_id.billing_id:
                record.uranos_changes += _('\n(Billing entry not Found)')

    @api.depends('start_minute')
    def _compute_start_time(self):
        for record in self:
            record.start_time = self.convert_minute2char(record.start_minute)

    @api.depends('end_minute')
    def _compute_end_time(self):
        for record in self:
            record.end_time = self.convert_minute2char(record.end_minute)

    @api.depends('duration_minute')
    def _compute_duration_time(self):
        for record in self:
            record.duration_time = self.convert_minute2char(record.duration_minute)

    @api.depends('event_start_minute')
    def _compute_time_start_on_site(self):
        for record in self:
            record.time_start_on_site = self.convert_minute2char(record.event_start_minute)

    @api.depends('event_end_minute')
    def _compute_time_end_on_site(self):
        for record in self:
            record.time_end_on_site = self.convert_minute2char(record.event_end_minute)

    def _compute_actual_duration_color(self):
        NO_COLOR = 'rgba(0, 0, 0, 0)'
        RED = 'rgba(255, 0, 0, 0.5)'
        ORANGE = 'rgba(255, 117, 24, 0.5)'
        YELLOW = 'rgba(255, 255, 0, 0.5)'

        for record in self:
            if not record.task_id.planned_hours:
                record.actual_duration_color = NO_COLOR
            else:
                ratio = record.task_id.actual_duration / record.task_id.planned_hours
                if ratio > 1.0:
                    record.actual_duration_color = RED
                elif ratio >= 0.95:
                    record.actual_duration_color = ORANGE
                elif ratio >= 0.8:
                    record.actual_duration_color = YELLOW
                else:
                    record.actual_duration_color = NO_COLOR

    @api.onchange('start_time')
    def _onchange_start_time(self):
        for record in self:
            if record.start_time == '=':
                record.start_minute = self.calculate_now()
            else:
                record.start_minute = self.convert_char2minute(record.start_time)

    @api.onchange('end_time')
    def _onchange_end_time(self):
        for record in self:
            if record.end_time == '=':
                record.end_minute = self.calculate_now()
            else:
                record.end_minute = self.convert_char2minute(record.end_time)

    @api.onchange('time_start_on_site')
    def _onchange_time_start_on_site(self):
        for record in self:
            if record.time_start_on_site == '=':
                record.event_start_minute = self.calculate_now()
            else:
                record.event_start_minute = self.convert_char2minute(record.time_start_on_site)
            record.update_event_duration()

    @api.onchange('time_end_on_site')
    def _onchange_time_end_on_site(self):
        for record in self:
            if record.time_end_on_site == '=':
                record.event_end_minute = self.calculate_now()
            else:
                record.event_end_minute = self.convert_char2minute(record.time_end_on_site)
            record.update_event_duration()

    def update_event_duration(self):
        for record in self:
            duration_minutes = self.event_end_minute - self.event_start_minute
            duration_minutes -= self.event_id._calculate_nested_minutes()
            self.event_duration_minute = duration_minutes

    def calculate_duration_hole(self):
        for record in self:
            hole = record.end_minute - record.start_minute

            ts_blocks = record.env['microcom.timesheet'].search([
                ('user_id', '=', record.user_id.id),
                ('date', '=', record.date),
                ('start_minute', '>=', record.start_minute),
                ('start_minute', '<=', record.end_minute),
                ('end_minute', '>=', record.start_minute),
                ('end_minute', '<=', record.end_minute)
            ])

            for ts_block in ts_blocks:
                if ts_block.pk_event != record.pk_event:
                    hole -= ts_block.duration_minute

            return hole

    def get_default_billing_code(self, task_id=False):
        if task_id:
            project_id = task_id.project_id
            partner_id = task_id.partner_id
            followup_id = task_id.get_followup_id(self.env.user)
            user_id = self.env.user
        else:
            project_id = self.project_id
            partner_id = self.partner_id
            followup_id = self.followup_id
            user_id = self.user_id or self.env.user

        if followup_id and followup_id.billing_code_id:
            return followup_id.billing_code_id

        employee = self.env['hr.employee'].search([('user_id', '=', user_id.id)], limit=1)
        employee_rates = employee.client_billing_rate
        customer = partner_id

        if employee:
            employee_billing_rate = employee.travel_billing_code_id if self.has_transport_info else employee.billing_code_id
            project_billing_rate = project_id and employee_rates.filtered(lambda r: r.project_id == project_id)[:1]
            customer_billing_rates = customer and employee_rates.filtered(
                lambda r: r.partner_id == customer and not r.project_id)[:1]

            if self.has_transport_info:
                billing_rate = ((project_billing_rate and project_billing_rate.travel_billing_code_id) or
                                (customer_billing_rates and customer_billing_rates.travel_billing_code_id) or
                                employee_billing_rate)
            else:
                billing_rate = ((project_billing_rate and project_billing_rate.billing_code_id) or
                                (customer_billing_rates and customer_billing_rates.billing_code_id) or
                                employee_billing_rate)

            if billing_rate:
                return billing_rate
        return False

    @api.onchange('followup_id', 'user_id', 'project_id', 'partner_id')
    def onchange_user_project(self):
        self.billing_code_id = self.get_default_billing_code()

    @api.onchange('duration_time')
    def _onchange_duration_time(self):
        for record in self:
            if record.duration_time == '=':
                record.duration_minute = record.end_minute - record.start_minute
            elif record.duration_time in ('-', '=='):
                record.duration_minute = record.calculate_duration_hole()
            else:
                record.duration_minute = self.convert_char2minute(record.duration_time)

    @api.depends('overlap_minute')
    def _compute_overlap_colors(self):
        for record in self:
            if record.overlap_minute == 0:
                record.overlap_fg_color = False
                record.overlap_bg_color = False
            elif record.overlap_minute > 0:
                # excess is red
                record.overlap_fg_color = False
                record.overlap_bg_color = 'rgba(255,0,0,0.2)'
            elif record.overlap_minute < 0:
                # missing is yellow
                record.overlap_fg_color = False
                record.overlap_bg_color = 'rgba(255,255,0,0.3)'

    @api.onchange('partner_id', 'project_id')
    def _onchange_partner_id(self):
        self.ensure_one()
        #
        # cleanup
        if self.partner_id and self.project_id:
            # match behavior of _compute_project_domain()
            # allow projects for selected client and projects shared across all clients
            if self.project_id.partner_id and self.project_id.partner_id != self.partner_id:
                self.project_id = False
        if self.partner_id and self.partner_id != self.task_id.partner_id:
            self.task_id = False
        if self.project_id and self.project_id != self.task_id.project_id:
            self.task_id = False

    # Todo replace select_followup by task.get_followup_id and verify if billing_ocde_id is correctly set.
    def select_followup(self, task=None):
        open_followups = (task or self.task_id).followup_ids.filtered(lambda x: x.state == 'open')
        # use billing code from open followup of user, if any
        user_billed_followups = open_followups.filtered(lambda x: x.user_id == self.user_id and x.billing_code_id)
        if user_billed_followups:
            self.billing_code_id = user_billed_followups[0].billing_code_id
        #
        best_followup_ids = open_followups.filtered(lambda x: x.user_id == self.user_id)
        if not best_followup_ids:
            best_followup_ids = open_followups.filtered(lambda x: x.is_main)
        if best_followup_ids:
            self.followup_id = best_followup_ids[0]

    def _select_best_budget_id(self, budget_line_id):
        # s'il y a 1 ligne, elle est automaiquement choisi.
        # S'il n'y a qu'une seule ligne pour le user, elle aest automaquement choisi
        # S'il n'y a qu'une ligne pour ce user et cette étape, la choisir automatiquement.
        # S'il n'y a qu'une ligne pour l'étape, la choisir automatiquement.
        # Sinon ne rien choisir.
        if len(budget_line_id) == 1:
            return budget_line_id
        else:
            employee = self.env['hr.employee'].search([('user_id', '=', self.user_id.id)])
            if employee:
                budget_line_id_emp = budget_line_id.filtered(lambda x: employee.id in x.employee_ids.ids)
                if len(budget_line_id_emp) == 1:
                    return budget_line_id_emp
                else:
                    budget_line_id_emp_stage = budget_line_id_emp.filtered(lambda x: self.task_id.stage_id.id in x.stage_ids.ids)
                    if len(budget_line_id_emp_stage) == 1:
                        return budget_line_id_emp_stage
                    else:
                        budget_line_id_stage = budget_line_id.filtered(lambda x: self.task_id.stage_id.id in x.stage_ids.ids)
                        if len(budget_line_id_stage) == 1:
                            return budget_line_id_stage
                        else:
                            return False
            else:
                return False

    @api.onchange('task_id')
    def _onchange_task_id(self):
        self.ensure_one()
        if self.task_id:
            self.partner_id = self.task_id.partner_id
            self.project_id = self.task_id.project_id
            self.select_followup()
            # budget_line_id = self.task_id.budget_line_ids
            self.budget_line_id = self._select_best_budget_id(self.task_id.budget_line_ids)


    def write_ts_dict(self, ts_dict):
        for k in ('user_id', 'partner_id', 'task_id', 'billing_code_id'):
            if k in ts_dict:
                ts_dict[k] = ts_dict[k].id
        self.write(ts_dict)

    def is_in_ts_admin(self):
        ts_admin_rights = 'uranos_ts.group_uranos_ts_admin,uranos_ts.group_uranos_approval'
        return self.env.context.get('timesheet_admin') and self.user_has_groups(ts_admin_rights)

    def update_ts(self, vals, old_vals=None):
        """ any write will synchronize both ways
        non-concurrent changes are pulled from TS
        local changes are pushed to TS
        """
        #
        self = self.sudo()
        creating = not self.pk_action
        if not (self.user_id and self.task_id):
            # record is incomplete, do nothing
            if not self.task_id and not creating:
                raise ValidationError(_('Task cannot be empty.'))
            return
        if not TS_COLUMNS.intersection(vals.keys()):
            if not TS_TRAVEL_COLUMNS.intersection(vals.keys()):
                # no change to push to MSSQL
                return
        # check if the partner or the user's partner are linked to pk_contact
        if not self.task_id.partner_id.pk_contact:
            raise ValidationError(_('The task customer is not linked to Timesheet.'))
        if not self.user_id.partner_id.pk_contact:
            raise ValidationError(_('The employee is not linked to Timesheet.'))

        #
        def present(key, ts, old, new):
            if key in ('start_minute', 'end_minute', 'duration_minute'):
                return (key, self.convert_minute2char(old), self.convert_minute2char(new),
                        self.convert_minute2char(ts))
            else:
                return (key, ts, old, new)

        #
        # block recursive calls while cursor is open
        if 'open_ts_cursor' in self.env.context:
            return
        # access TS/MSSQL
        with open_ts_cursor(self) as cursor:
            if not cursor:
                # TODO tag as dirty
                return
            self = self.with_context(open_ts_cursor=cursor)

            changing_event_from_odoo = 'event_id' in (old_vals or {}) and old_vals['event_id'] != self.event_id
            event = self.event_id or self.env['microcom.timesheet.event'].search([('pk_event', '=', self.pk_event)],
                                                                                 limit=1)

            if creating:
                pk_event = event.pk_event if event else None
                if not self.task_id.request_pk:
                    # create both request/event/followup in TS/MSSQL
                    self.pk_action, self.pk_event = create_request_inner(self.task_id, cursor, pk_event)
                else:
                    # create an event in TS/MSSQL
                    self.pk_action, self.pk_event = create_action_inner(self.task_id, cursor, pk_event=pk_event)

            ts_dict = pull_ts_from_event(self, cursor, self.pk_action)

            # attempting to make sure there is an event in odoo with the correct pk_event
            if not (event and event.pk_event == ts_dict['pk_event']):

                # if event's pk_event is different from ts_dict['pk_event']
                # it might be that we are changing it from odoo or that it changed from uranos
                if event and event.pk_event != ts_dict['pk_event']:
                    if not changing_event_from_odoo:
                        # we always to take the event related to the pk_event from uranos
                        # because it may have been changed from uranos
                        event = self.env['microcom.timesheet.event'].search([('pk_event', '=', ts_dict['pk_event'])],
                                                                            limit=1)

                # if event is just not set we just search one with ts_dict['pk_event'] or create one
                if not event:
                    event = self._find_or_create_event(ts_dict['pk_event'])

            if self.event_id != event:
                self.event_id = event

            # create a travel expense in TS/MSSQL if it does not exist
            if event.has_transport_info and not event.pk_travel_expense:
                pk_travel_expense = create_travel_expense(
                    cursor,
                    event.pk_event,
                    event.start_address,
                    event.destination_address,
                    event.return_address,
                    event.start_km,
                    event.return_km
                )
                event.pk_travel_expense = pk_travel_expense
            # update is done through push_event_to_ts()

            request_change = False
            task_id = self.env['project.task'].browse(vals.get('task_id')).exists()
            if 'task_id' in vals and not creating:
                request_change = task_id.request_pk != ts_dict['pk_request']
                if request_change:
                    if not self.is_in_ts_admin():
                        raise ValidationError(_(
                            'You cannot modify a task linked to timesheet, you must create a new timesheet entry'
                        ))
                    old_task = old_vals['task_id']
                    if old_task and not self.search_count([('task_id', '=', old_task.id)]):
                        raise ValidationError(
                            _('There should remain at least 1 timesheet record on task %s') % (old_task.name,))

            if old_vals and not creating:
                # updating an existing record, check if TS made a change to the same field
                both_changed = {k for k in ts_dict if k in old_vals}
                # fields not to check when changing the request (task)
                request_change_excluded_fields = ['partner_id', 'task_id', 'project_id'] if request_change else []
                collisions = [
                    present(k, ts_dict[k], old_vals[k], self[k])
                    for k in both_changed
                    if old_vals[k] != ts_dict[k] and self[k] != ts_dict[k] and k not in request_change_excluded_fields
                ]
                if collisions:
                    raise ValidationError(
                        _('Some fields were modified from Timesheet, synchronize before changing them.\n(%s)')
                        % ', '.join(a for a, b, c, d in collisions))
                    # raise ValidationError(
                    #     _('Different changes were done from Timesheet:\n%s') % '\n'.join(
                    #         '{}: {} ≠ {} → {}'.format(a, b, c, d)
                    #         for a, b, c, d in collisions))
            # update from TS/MSSQL
            # since TS and Odoo are synchronized until a change is made in either,
            # assume all TS values a good except those just changed
            ts_vals = set(ts_dict) - set(vals)
            if creating:
                # when creating, those TS values are wrong, ignore them
                ts_vals -= set([
                    # date / start_minute are set to now() during creation,
                    # name should convert back correctly
                    # others are not set at creation
                    'date', 'start_minute', 'end_minute', 'duration_minute',
                    'name', 'description', 'internal_comment', 'billing_code_id',
                ])
            changed_ts_dict = {k: ts_dict[k] for k in ts_vals}
            self.write_ts_dict(changed_ts_dict)
            #
            # synchronize records in both DB
            push_event_to_ts(self, cursor)
            # free followups are attached to this event
            if not self.env.context.get('skip_create_ts_followup'):
                for followup in self.task_id.followup_ids.filtered(lambda x: not x.pk_followup):
                    # deadlock if quickTS entry is not explicitly created
                    pk_action = self.pk_action or self._select_microcom_timesheet().pk_action
                    followup.pk_followup = create_ts_followup(followup, pk_action)

            # change the followup if the task was changed
            # and make sure that the right followup is set if creating new ts record
            if request_change or creating:
                followup = self.env['project.task.followup'].sudo().browse(vals.get('followup_id')).exists()
                if followup.task_id != task_id:
                    self.select_followup(task=task_id)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if not self.env.context.get('nocreate_ts'):
            for record, vals in zip(res, vals_list):
                record.update_ts(vals)
                record.with_context(updating_overlap=True).analyze_many_days()
                if not record.followup_id:
                    record.select_followup()
        return res

    def write(self, vals):
        old_vals = {k: self[k] for k in vals if k != 'pk_event'}
        old_date = self.date
        res = super().write(vals)
        if not self.env.context.get('nocreate_ts'):
            # immediate update
            if not self.env.context.get('updating_overlap'):
                if set(vals).intersection({'date', 'user_id', 'start_minute', 'end_minute', 'duration_minute'}):
                    self.with_context(updating_overlap=True).analyze_many_days(old_date=old_date)
            if not self.env.context.get('apply_patch') and not self.env.context.get('updating_overlap'):
                self.update_ts(vals, old_vals)

        # if has_transport_info changes on une timesheet record, apply it to siblings timesheet records
        if 'has_transport_info' in vals and not self.env.context.get('propagate_changes'):
            for timesheet_record in self:
                value = timesheet_record.has_transport_info
                # setting the value to current_timesheet + siblings
                for ts in (timesheet_record.event_id.timesheet_ids - self).with_context(propagate_changes=True):
                    # setting apply_patch=True, updating_overlap=True in context to avoid sync operations
                    ts.with_context(apply_patch=True, updating_overlap=True).has_transport_info = value
        return res

    def unlink(self):
        if any(self.mapped('pk_action')):
            raise UserError(_("This timesheet record is already linked in uranos; It can't be deleted"))
        return super(Timesheet, self).unlink()

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """
        overriding to automatically pass in context all necessary timesheet fields
        when clicking on quick create shortcut button
        """
        arch, view = super()._get_view(view_id, view_type, **options)
        quick_create_action = self.env.ref('microcom_ts.quick_ts_create_action', raise_if_not_found=False)
        if not quick_create_action:
            return arch, view

        if view_type == 'tree':
            TIMESHEET_FIELDS = ['event_id', 'start_time', 'end_time', 'date', 'start_minute', 'end_minute']
            FIELDS_IN_VIEW = [field.get('name') for field in arch.findall('./field')]
            quick_create_button = arch.xpath(f"./button[@name={quick_create_action.id}]")
            if quick_create_button:
                quick_create_button = quick_create_button[0]
                context = ",".join(
                    f"'default_{field}':{field}" for field in TIMESHEET_FIELDS if field in FIELDS_IN_VIEW)
                context = "{" + context + "}"
                quick_create_button.set('context', context)
        return arch, view

    def full_ts_quick_create(self):
        action = self.button_view_ts()
        context = action.get('context') or {}
        FIELDS = ['start_time', 'end_time', 'date', 'start_minute', 'end_minute', 'duration_time']
        context.update(**{f'default_{field}': self[field] for field in FIELDS})
        context.update(default_event_id=self.event_id.id)
        action.update(res_id=False, context=context)
        return action

    def synchronize_from_ts_inner(self, cursor):
        for record in self.sudo():
            ts_dict = pull_ts_from_event(self, cursor, record.pk_action)
            if not ts_dict:
                raise ValidationError(_('No event entry found for action %d') % record.pk_action)
            if record.pk_event != ts_dict['pk_event']:
                ts_dict['event_id'] = record._find_or_create_event(ts_dict['pk_event']).id
            record.write_ts_dict(ts_dict)
            # sync travel expense (fixing bug)
            push_event_to_ts(record, cursor)

    def _find_or_create_event(self, pk_event, force_create=False):
        self.ensure_one()
        event = None
        if not force_create:
            event = self.env['microcom.timesheet.event'].search([('pk_event', '=', pk_event)], limit=1)
        if force_create or not event:
            event = self.env['microcom.timesheet.event'].create({
                'pk_event': pk_event,
                'name': '{} - {} - {}'.format(self.partner_id.display_name or "", str(self.date), pk_event),
                'start_date': self.date,
                'start_minute': 0,
                'user_id': self.user_id.id
            })
        return event

    def compute_is_first_of_day(self):
        for record in self:
            # Prendre la première entrée ouverte (Car il y a un filtre sur les entrées fermés par défaut.
            # S'il n'y a aucune entrée ouverte, prendre la 1ier entré sans condition de state.
            first = record.env['microcom.timesheet'].search([
                ('date', '=', record.date),
                ('user_id', '=', record.user_id.id),
                ('state', '=', 'open')], limit=1)
            if not first:
                first = record.env['microcom.timesheet'].search([
                    ('date', '=', record.date),
                    ('user_id', '=', record.user_id.id)], limit=1)

            record.is_first_of_day = record == first

    def button_do_nothing(self):
        pass

    def button_update_day(self):
        self.import_day(self.date, self.user_id)

    def button_synchronize(self):
        """ update record from TS/MSSQL, synchronize_timesheet_action will call with a recordset
        """
        timesheet_to_sync = self.filtered(lambda x: x.pk_action)
        if not timesheet_to_sync:
            raise UserError(_('No entry linked to TS'))
        with open_ts_cursor(self) as cursor:
            if not cursor:
                raise ValidationError(_('TS is not connected'))
            timesheet_to_sync = timesheet_to_sync.with_context(open_ts_cursor=cursor)
            timesheet_to_sync.synchronize_from_ts_inner(cursor)

    def synchronize_all(self, max_update=100):
        """ Nightly synchronize all stale timesheet date"""
        timesheets_to_sync = self.search([('final_state', '=', False), ('pk_action', '!=', False)])
        count = 0

        for timesheet_to_sync in timesheets_to_sync:
            try:
                if timesheet_to_sync.uranos_changes != '':
                    timesheet_to_sync.button_synchronize()
                    count += 1
                if timesheet_to_sync.state in ('billed', 'cancelled'):
                    # No more automatic synchronize if final_state is true
                    timesheet_to_sync.final_state = True
                if count > max_update:
                    self._cr.commit()
                    count = 0
            except Exception as ex:
                _logger.exception("Failed to synchronize timesheet # %d, error : %s" % (timesheet_to_sync.id, ex))

    def button_view_ts(self):
        self.ensure_one()
        return {
            'name': _('Timesheet'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'microcom.timesheet',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': self.id,
        }

    def close_request_button(self):
        wiz = self.env['microcom.timesheet.close.request'].create({
            'mode': 'close',
            'task_id': self.task_id.id,
            'microcom_timesheet_id': self.id,
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
        wiz = self.env['microcom.timesheet.close.request'].create({
            'mode': 'open',
            'task_id': self.task_id.id,
            'microcom_timesheet_id': self.id,
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

    def button_import_day(self):
        self.import_day(self.date, self.user_id)

    def import_day(self, date, user_id):
        """ find all TS events on the same day, update/create
        """
        if not (date and user_id):
            raise UserError(_('Date and employee must be set'))
        if not user_id.pk_contact:
            raise UserError(_('Employee is not in TS'))
        with open_ts_cursor(self) as cursor:
            if not cursor:
                raise ValidationError(_('TS is not connected'))
            self = self.with_context(open_ts_cursor=cursor)
            action_set = get_pk_action_for_date_user(self, cursor, date, user_id.pk_contact)
            #
            # update known
            known_entries = self.search([('pk_action', 'in', list(action_set))])
            known_entries.synchronize_from_ts_inner(cursor)
            #
            # create missing
            missing_list = action_set - set(known_entries.mapped('pk_action'))
            for pk_action in missing_list:
                # delay call to update_ts() until task_id is created from request_id
                missing_entry = self.env['microcom.timesheet'].with_context(nocreate_ts=True).create({
                    'pk_action': pk_action
                })
                missing_entry.with_context(nocreate_ts=False).synchronize_from_ts_inner(cursor)
                # adjust Odoo-only fields
                missing_entry.project_id = missing_entry.task_id.project_id

    @api.model
    def _patch_pk_events(self, cleanup=False):
        """
        This pulls pk_event information from uranos.action and generates then assigns
        microcom.timesheet.event records to their corresponding timesheet records
        :param cleanup: if set to True, event records will be generated for all timehseets, Otherwise
            records will only be generated for timesheet missing event records
        :return: None
        """

        # loading all pk_event from existing actions
        # PS: we are only need pk_action and pk_event, so we load only those for optimisation
        pk_action_event_map = {
            action['pk_action']: action['pk_event']
            for action in self.env['uranos.action'].search_read(
                domain=[('pk_action', '!=', False)],
                fields=['pk_action', 'pk_event']
            )
        }

        # search all timesheet records if in cleanup mode
        # else we only search those missing event record
        ts_search_domain = [('pk_action', '!=', False)]
        if not cleanup:
            ts_search_domain.append(('event_id', '=', False))

        created_event_map = dict()
        for ts in self.env['microcom.timesheet'].search(ts_search_domain).with_context(apply_patch=True):
            pk_event = pk_action_event_map.get(ts.pk_action)
            if not pk_event:
                _logger.warning(f"Could not find pk_event for action {ts.pk_action}(Timesheet ID {ts.id})")
                continue

            event = created_event_map.get(pk_event)
            if not event:
                # creating a new event with the pk_event of the ts.pk_action
                event = ts._find_or_create_event(pk_event, force_create=True)
                created_event_map[pk_event] = event
            try:
                ts.write({'event_id': event.id})
            except Exception as e:
                _logger.exception(f"Failed to patch event_id on timesheet ID {ts.id}", e)

    def button_analyze_day(self):
        self.analyze_many_days()

    def analyze_many_days(self, old_date=None):
        """ divide recordset into separate processing groups
        """
        # clear incomplete records
        for record in self.filtered(lambda x: not x.date):
            record.overlap = False
            record.overlap_minute = 0
        # process each date/employee separately
        # will fail if work overlaps midnight
        batch_set = set(self.filtered(lambda x: x.date).mapped(lambda x: (x.date, x.user_id)))
        if old_date:
            batch_set |= set(self.mapped(lambda x: (old_date, x.user_id)))
        while batch_set:
            date, user_id = batch_set.pop()
            records = self.search([
                ('date', '=', date),
                ('user_id', '=', user_id.id)])
            records.analyze_one_day()

    def block_iterate(self):
        """ iterate over blocks of overlapping entries
        accumulate overlapping entries in a single recordset
        and release it when next entry is separate
        """
        end_minute = None
        block_records = None
        # TODO check sorted
        active_records = self.filtered(
            lambda x: x.start_minute and x.end_minute and x.duration_minute)
        for record in active_records:
            if not block_records:
                # once on loop entry
                end_minute = record.end_minute
                block_records = record
            elif record.start_minute < end_minute:
                # overlap, extend current block
                end_minute = max(end_minute, record.end_minute)
                block_records += record
            else:
                # separate, release held block and start a new one
                yield block_records
                end_minute = record.end_minute
                block_records = record
        if block_records:
            # always true unless filtered is empty
            yield block_records

    def start_end_iterate(self):
        """ iterate over entries, returning the next start/end to occur
        yields:
            :param active_records: entries in current timeslice
            :param next_record: entry being added/removed from actives
            :param next_minute: end of next timeslice
            :param previous_minute: end of current timeslice
            :param when: which end of the next_record we are processing

        """
        start_records = self.sorted('start_minute')
        end_records = self.sorted('end_minute')
        active_records = self.env['microcom.timesheet']
        previous_minute = start_records[0].start_minute
        # start_records will be empty when we exit this loop
        # because time_constrains() method forces end_minute > start_minute
        while end_records:
            # records are sorted, only check the first one of each recordset
            # once all start times have been consumed, there is only end times left
            if start_records and start_records[0].start_minute < end_records[0].end_minute:
                next_record = start_records[0]
                #
                next_minute = next_record.start_minute
                start_records -= next_record
                yield active_records, next_record, next_minute, previous_minute, 'start_date'
                active_records += next_record
                previous_minute = next_minute
            else:
                next_record = end_records[0]
                next_minute = next_record.end_minute
                end_records -= next_record
                yield active_records, next_record, next_minute, previous_minute, 'end_date'
                active_records -= next_record
                previous_minute = next_minute

    def analyze_one_day(self):
        """
        """

        def annotate_record(next_record, duration_left):
            # record is done processing
            # bottle should be empty
            # if some duration is left in the "bottle", duration is too high
            # if "bottle" is more than empty, some timeslice is short on duration
            next_record = next_record.sudo()
            next_record.overlap_minute = duration_left
            if duration_left > 0:
                # duration declared is too high
                next_record.overlap = 'overflow'
            elif duration_left < 0:
                # duration declared leaves time unaccounted for
                next_record.overlap = 'underflow'
            else:
                next_record.overlap = 'full'

        # records are considered "bottles" containing an amount of liquid time
        # bottles may be partially filled (1 hour assigned out of a 2 hour event)
        # records start/end divide the block into timeslices
        # we fill each timeslice from early to last using those bottles
        # we first empty the first-to-end because we want to empty a bottle before its last timeslice
        # empty bottle can go negative with non-existent time to inform user of missing amount
        #
        # clear incomplete records
        invalid_records = self.filtered(lambda x: not (x.start_minute and x.end_minute and x.duration_minute))
        for record in invalid_records:
            record.overlap = False
            record.overlap_minute = 0
        # update filled records
        valid_records = self.filtered(lambda x: x.start_minute and x.end_minute and x.duration_minute)
        for records in valid_records.sorted('start_minute').block_iterate():
            if len(records) == 1:
                consumed_time = records.end_minute - records.start_minute
                annotate_record(records, records.duration_minute - consumed_time)
                if records.overlap == 'full':
                    records.overlap = 'single'
                continue
            # process is done with exact minutes
            duration_left_dict = {record: record.duration_minute for record in records}
            for active_records, next_record, next_minute, previous_minute, when in records.start_end_iterate():
                time_to_distribute = next_minute - previous_minute
                if time_to_distribute == 0:
                    if when == 'end_date':
                        annotate_record(next_record, duration_left_dict[next_record])
                    continue
                active_records = active_records.sorted('end_minute')
                # pour time from bottles
                for record in active_records:
                    consumed_time = min(time_to_distribute, duration_left_dict[record])
                    if consumed_time > 0:
                        duration_left_dict[record] -= consumed_time
                        time_to_distribute -= consumed_time
                    if time_to_distribute <= 0:
                        break
                if time_to_distribute > 0:
                    # time underflow: all bottles are empty
                    # start pouring into negative until maximum possible
                    for record in active_records:
                        allowed_time = record.end_minute - record.start_minute
                        allowed_time -= record.duration_minute
                        consumed_time = min(time_to_distribute, allowed_time)
                        if consumed_time > 0:
                            duration_left_dict[record] -= consumed_time
                            time_to_distribute -= consumed_time
                        if time_to_distribute <= 0:
                            break
                if when == 'end_date':
                    annotate_record(next_record, duration_left_dict[next_record])
            #
            # records.overlap = 'weft'
        pass

    def action_merge_events(self):
        """
        Merges events from multiple timesheet into one
        :return:
        """
        if len(self) < 2:
            raise UserError(_("Choose multiple entries to merge"))

        event_ids = self.mapped('event_id').sorted('start_minute')
        if not event_ids:
            raise UserError(_('No selected timesheet entry is linked to event info. Synchronize and retry'))
        if len(set(event_ids.mapped('start_date'))) > 1:
            raise UserError(_('You cannot merge events from different days'))

        if len(set(event_ids.filtered_domain([('pk_travel_expense', '>', 0)]).mapped('pk_travel_expense'))) > 1:
            raise UserError(_('Events with different travel expenses cannot be merged'))

        start_minute, end_minute = min(self.mapped('start_minute')), max(self.mapped('end_minute'))
        # finding the earliest start time and the latest end time
        ev_start_minute, ev_end_minute = min(event_ids.mapped('start_minute')), max(event_ids.mapped('end_minute'))
        # save the start and end times on one event
        event = event_ids[0]
        event.write(dict(start_minute=ev_start_minute, end_minute=ev_end_minute))
        # assign that event to all the timesheet entries
        for timesheet in self:
            timesheet.write(dict(
                event_id=event.id,
                start_minute=start_minute,
                end_minute=end_minute
            ))

        # delete the remaining events
        events_to_remove = event_ids - event
        if events_to_remove:
            with open_ts_cursor(self) as cursor:
                for pk_event in set(events_to_remove.mapped('pk_event')):
                    delete_uranos_event(cursor, pk_event)
            events_to_remove.unlink()

    def by_event(self):
        """
        returns a generator of tuples: event_id, and recordset of timehseet of the event
        :return:
        """
        for event in self.mapped('event_id'):
            yield event, self.filtered(lambda ts: ts.event_id == event)
        without_event = self.filtered(lambda ts: not ts.event_id)
        if without_event:
            yield False, without_event

    def action_change_task(self):
        # Making sure that all the selected ts records have the same task
        if len(self.mapped('task_id')) > 1:
            raise UserError(_('Please select records of the same task'))

        return {
            'name': _('Change Timesheet Tasks'),
            'type': 'ir.actions.act_window',
            'res_model': 'microcom.timesheet.task.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': dict(default_timesheet_ids=self.ids, default_task_id=self[0].task_id.id)
        }

    def _change_task(self, task):
        self._check_admin()
        ts_records_to_change = self.with_context(timesheet_admin=True).filtered_domain([('task_id', '!=', task.id)])

        # making sure there will remain at least 1 ts record for each task after the change
        for task_to_change in ts_records_to_change.mapped('task_id'):
            # count the number of ts records that will remain for this task after we change the selected records
            remaining_after_change = self.search_count([
                ('task_id', '=', task_to_change.id),
                ('id', 'not in', ts_records_to_change.ids)])
            # raising a warning if there won't remain any record for the given task
            if not remaining_after_change:
                raise UserError(
                    _('There should remain at least 1 timesheet record on task %s') % (task_to_change.name,))

        for timesheet in ts_records_to_change:
            timesheet.write(dict(task_id=task.id, partner_id=task.partner_id.id, project_id=task.project_id.id))
            if timesheet.followup_id:
                timesheet.followup_id.task_id = task
                update_followup(timesheet.followup_id.with_context(no_progression=True), pk_action)


    def action_close_timesheet(self):
        # select timesheet plus all others from same event
        timesheets_records = self + self.mapped('event_id.timesheet_ids')
        valid_ts_records = self.env['microcom.timesheet']

        # validate timesheet records by batch of event
        for event, ts_recordset in timesheets_records.by_event():
            # all timesheet records for each event group must be valid else that event cant be closed
            if ts_recordset._check_closable(raise_if_invalid=False)[0]:
                valid_ts_records |= ts_recordset

        invalid_ts_records = timesheets_records - valid_ts_records
        # closing and synchronizing the valid timesheet records
        if valid_ts_records:
            uranos_action = valid_ts_records.mapped('uranos_action_id')
            unlinked_ts_record = self.env['microcom.timesheet']
            if len(valid_ts_records) != len(uranos_action):
                for valid_ts_record in valid_ts_records:
                    if not valid_ts_record.mapped('uranos_action_id'):
                        unlinked_ts_record |= valid_ts_record

            if uranos_action or unlinked_ts_record:
                uranos_action.close_works(unlinked_pk_action=unlinked_ts_record.mapped('pk_action'))
                for valid_ts_record in valid_ts_records:
                    valid_ts_record.state = 'closed'

        # raise validation error for invalid timesheet records
        if invalid_ts_records:
            valid, error_msg = invalid_ts_records._check_closable(raise_if_invalid=False)
            # raise a warning if no timesheet record got closed
            # else notify about invalid record without blocking the screen refresh
            if not valid_ts_records:
                raise ValidationError(_('Timesheet cannot be closed : \n%s') % error_msg)
            else:
                message = _("Timesheet closing error: %s") % error_msg
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': message,
                        'type': 'danger',
                        'sticky': True,
                    }
                }

    def _check_closable(self, raise_if_invalid=True):
        def _raise_error(error_message):
            if raise_if_invalid:
                raise ValidationError(error_message)
            return False, error_message

        for record in self:
            if record.task_id.budget_line_ids and not record.budget_line_id:
                record.budget_line_id = record._select_best_budget_id(record.task_id.budget_line_ids)
                if not record.budget_line_id:
                    return _raise_error(_("A budget line must be selected!"))

            if not record.pk_event:
                return _raise_error(_("you cannot close a timesheet with no linked event"))

            if record.action_status and record.action_status != 'Open':
                return _raise_error(_("timesheet can be closed only when the action status is Open"))

            if not record.task_id:
                return _raise_error(_("the timesheet must be linked to as task"))

            if not record.start_minute or not record.end_minute:
                return _raise_error(_("start and/or end time info must be set"))

            if not record.billing_code_id:
                return _raise_error(_("a billing code must be set"))

            if not record.followup_id:
                # Aller chercher les Follows déjà dans Timesheet (Pour vieux Task)
                record.task_id.button_synchronize_followup()
                # Selectionner le même FU que dans Timesheet.
                if record.uranos_action_id and record.uranos_action_id.followup_ids:
                    record.followup_id = self.followup_id.search([
                        ('pk_followup', '=', record.uranos_action_id.followup_ids[0].pk_followup)])
                if not record.followup_id:
                    # Sinon, en selectionner 1 par défaut.
                    record.select_followup()
                if not record.followup_id:
                    return _raise_error(_("a followup must be set"))

            if record.event_id.has_transport_info and record.event_id.pk_travel_expense:
                # TODO use _check_transportation_info() instead of duplicate code
                travel_expense_fields = ['start_address',
                                         'destination_address',
                                         'return_address',
                                         'start_minute',
                                         'end_minute',
                                         'duration_minute']
                all_fields_are_set = all([record.event_id[f] for f in travel_expense_fields])
                if not all_fields_are_set:
                    return _raise_error(_("travel expense info are not complete"))

            # km numbers for the entire trip should be set if requesting for transportation refund
            if record.request_km_refund and not(record.start_km or record.return_km):
                return _raise_error(_("Km number should be set for the entire trip when requesting for refund"))

            if not record.task_id.planned_hours:
                if not (record.task_id.no_budget_required or record.task_id.project_id.no_budget_required):
                    return _raise_error(_("You must ask/set a budget on the task."))

        return True, None

    def action_open_timesheet(self):
        # select timesheet plus all others from same event
        timesheets = self + self.mapped('event_id.timesheet_ids')
        valid_ts_records = timesheets.filtered_domain([('action_status', '=', 'Closed')])
        invalid_ts_records = timesheets - valid_ts_records

        if valid_ts_records:
            valid_ts_records.mapped('uranos_action_id').open_works()
            for valid_ts_record in valid_ts_records:
                valid_ts_record.state = 'open'

        if invalid_ts_records:
            # raise a warning if no timesheet record got re-opened
            # else notify about invalid record without blocking the screen refresh
            error_msg = _('Only closed timesheet records can be re-opened')
            if not valid_ts_records:
                raise UserError(error_msg)
            else:
                message = _("Timesheet opening error: %s") % error_msg
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': message,
                        'type': 'danger',
                        'sticky': True,
                    }
                }

    def button_clear_travel_expense(self):
        self.ensure_one()
        if not self.event_id:
            return
        if self.event_id.pk_travel_expense:
            with open_ts_cursor(self) as cursor:
                delete_travel_expense(cursor, self.event_id.pk_travel_expense)
        travel_expense_fields = [
            'pk_travel_expense', 'start_minute', 'end_minute', 'duration_minute',
            'start_address', 'destination_address', 'return_address', 'start_km', 'return_km',
            'request_km_refund', 'has_transport_info'
        ]
        self.event_id.write(dict.fromkeys(travel_expense_fields, False))

    def action_supervise_timesheet(self):
        self._check_admin()
        self.mapped('uranos_action_id').action_supervise_timesheet()
        for timesheet in self:
            timesheet.write(dict(state='supervised'))

    def _check_admin(self):
        """access rights check method for protecting admin-related actions"""
        ts_admin_rights = 'uranos_ts.group_uranos_ts_admin,uranos_ts.group_uranos_approval'
        if not self.user_has_groups(ts_admin_rights):
            raise UserError(_('Only admins or supervisors can perform this action'))

    def _get_transportation_fields(self):
        return ['start_address', 'destination_address', 'return_address',
                'start_minute', 'end_minute',
        ]

    @api.onchange('start_address', 'destination_address', 'return_address')
    def _onchange_transportation_fields(self):
        transport_fields = self._get_transportation_fields()
        for record in self:
            record.has_transport_info = all([record[fname] for fname in transport_fields])

    @api.constrains('has_transport_info')
    def _check_transportation_info(self):
        transport_fields = self._get_transportation_fields()
        for record in self.filtered('has_transport_info'):
            if not all ([record[fname] for fname in transport_fields]):
                raise ValidationError(_('Transportation info are not correctly set'))


class TimesheetBilling(models.Model):
    _name = "microcom.timesheet.billing"
    _description = "billing codes from MSSQL/TypeBilling table"

    name = fields.Char('Billing Code', required=True)
    pk_typebilling = fields.Integer(string='Pk_TypeBilling', copy=False)
    type = fields.Selection([('to_bill', 'Facturable'), ('no_bill', 'Non-facturable'), ('travel', 'Déplacement')],
                            'Type')
    sale_price = fields.Float('Sale price')
    group_id = fields.Many2one('microcom.timesheet.billing.group', 'Billing Group')
    letter = fields.Char(compute='_compute_billing_letter', store=True)

    @api.depends('name')
    def _compute_billing_letter(self):
        for record in self:
            record.letter = record.name[0]

    def _patch_billing_types(self):
        with open_ts_cursor(self) as cursor:
            sql = """
                SELECT TypeBilling.PK_Type as TypeBillingID, TypeWork.Name as WorkCode, TypeRate.Name as RateCode
                FROM TypeBilling
                Left Join TypeWork on TypeWork.PK_Type = TypeBilling.WorkCodeID
                Left Join TypeRate on TypeRate.PK_Type = TypeBilling.RateCodeID
            """
            cursor.execute(sql)
            for found in cursor.fetchall():
                billing_pk = found['TypeBillingID']
                billing_name = found['WorkCode'] + found['RateCode']
                # billing mapping
                billing_code_id = self.env['microcom.timesheet.billing'].search(
                    [('pk_typebilling', '=', billing_pk)])
                if not billing_code_id:
                    billing_code_id = self.env['microcom.timesheet.billing'].create({
                        'name': billing_name,
                        'pk_typebilling': billing_pk,
                    })
                else:
                    billing_code_id.name = billing_name


class TimesheetBillingGroup(models.Model):
    _name = "microcom.timesheet.billing.group"
    _description = "Billing group"

    name = fields.Char('Name')


class TimesheetEvent(models.Model):
    _name = "microcom.timesheet.event"
    _inherit = 'microcom.timesheet.calculations.mixin'
    _description = "Microcom Events"
    _rec_name = 'name'

    name = fields.Char('Event', required=True)
    start_date = fields.Date('Start Date')
    start_minute = fields.Integer(default=0, string="Event Start Minute")
    end_minute = fields.Integer(default=0, string="Event End Minute")
    duration_minute = fields.Integer(compute='_compute_duration_minute', store=True)
    start_address = fields.Selection(ADDRESS_SELECTION, string='Start Address')
    destination_address = fields.Selection(ADDRESS_SELECTION, string='Destination Address')
    return_address = fields.Selection(ADDRESS_SELECTION, string='Return Address')
    start_km = fields.Float('Start Kilometers')
    return_km = fields.Float('Return Kilometers')
    request_km_refund = fields.Boolean('Request KM refund')
    has_transport_info = fields.Boolean('Transportation')
    pk_travel_expense = fields.Integer(string='Pk_TravelExpense', copy=False)
    pk_event = fields.Integer(string='Pk_Event', copy=False)
    user_id = fields.Many2one('res.users', string='User')
    pk_contact = fields.Integer(string='Pk_Contact', related='user_id.id', copy=False)
    line_bg_color = fields.Char('Event Color', compute='_compute_line_bg_color', store=True)
    line_label_color = fields.Char('Label Color')
    timesheet_ids = fields.One2many('microcom.timesheet', 'event_id', string='Timesheets')

    @api.depends('start_minute', 'end_minute')
    def _compute_duration_minute(self):
        for event in self:
            duration_minutes = event.end_minute - event.start_minute
            duration_minutes -= event._calculate_nested_minutes()
            event.duration_minute = duration_minutes

    def _calculate_nested_minutes(self):
        """ calculate concurrent ts entries duration
        only uses nested entries
        ignore partially overlapping ones, as they could be wholly outside
        This does not update for later adjustments
        """
        if not self:
            return 0

        ts_of_day_on_other_events = self.env['microcom.timesheet'].search([
            ('user_id', '=', self.user_id.id),
            ('start_date', '=', self.start_date),
            ('event_id', '!=', self.id),
            ('start_minute', '>=', self.start_minute),
            ('end_minute', '<=', self.end_minute),
        ])
        nested_minutes = sum(ts_of_day_on_other_events.mapped('duration_minute'))
        return nested_minutes

    @api.depends('timesheet_ids')
    def _compute_line_bg_color(self):
        no_color = 'rgba(0, 0, 0, 0.0)'
        for record in self:
            # we are colorizing only if the event is associated to many timesheet
            if len(record.timesheet_ids) > 1:
                if not record.line_bg_color or record.line_bg_color == no_color:
                    color1, color2, color3 = random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
                    # making sure the color is never white; this might not happen that often but it can
                    while (color1, color2, color3) == (255, 255, 255):
                        color1, color2, color3 = random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
                    record.line_bg_color = 'rgba({}, {}, {}, 0.3)'.format(color1, color2, color3)
            else:
                record.line_bg_color = no_color

    def write(self, vals):
        return super().write(vals)
