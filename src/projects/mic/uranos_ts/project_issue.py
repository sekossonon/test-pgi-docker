# coding: utf-8
from contextlib import contextmanager
import logging
import pymssql
import pytz
import re
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .res_config import get_connection_kwargs

_logger = logging.getLogger(__name__)

# change to MSSQL tables
"""
alter table Request
add projectOdooID int,
projectName nvarchar(max)
"""

# selon la table Type de TS, 0 = undefined et 1-5 correspondent aux spare-extreme
TASK_TO_PK_TYPE = {
    False: False,
    '0': False,
    '1': '0',
    '2': '1',
    '3': '2',
    '4': '3',
    '5': '4',
}

ADDRESSES_PK_MAP = {
    'residence': 1591,
    'customer': 1592,
    'office': 1593
}

ADDRESSES_TYPE_MAP = {
    'residence': 1,
    'customer': 3,
    'office': 2
}


def null2none(value):
    # convert null/None to null/False
    if value is False:
        return None
    return value


def fix_gremlins(text):
    if not text:
        return False
    # MSSQL adds garbage \ufeff
    while len(text) and ord(text[0]) > 64000:
        text = text[1:]
    while len(text) and text[-1] == '\n':
        text = text[:-1]
    return text


@contextmanager
def open_ts_cursor(record, recursive_check=True):
    # if recursive_check and record.env.context.get('open_ts_cursor'):
    #     raise ValidationError(_('recursive connection to MSSQL'))
    connection_kwargs = get_connection_kwargs(record)
    if connection_kwargs:
        try:
            with pymssql.connect(**connection_kwargs) as conn:
                cursor = conn.cursor()
                yield cursor
                conn.commit()
        except (UserError, ValidationError):
            raise
        except Exception as ex:
            raise UserError(ex)
    else:
        yield False


def get_new_id(cursor):
    cursor.execute("Select SCOPE_IDENTITY() as ident")
    ident = cursor.fetchone()

    return int(ident['ident'])


def get_event_from_uranos(task, cursor):
    uid = task.env.context.get('uid') or task._uid
    pk_contact = task.env['res.users'].browse(uid).partner_id.pk_contact

    cursor.execute("SELECT PK_Event, PK_Request, PK_Action FROM dbo.request r"
                   " JOIN dbo.action a ON r.PK_Request = a.RequestID"
                   " JOIN dbo.event e ON e.PK_Event = a.EventID"
                   " WHERE PK_Request = %d and employee_ContactID = %d and (a.status = 0 or a.status is null) "
                   " Order by e.DateStartEvent DESC, e.TimeStartEvent DESC",
                   (task.request_pk, pk_contact))

    return cursor.fetchone()


def get_followup_from_uranos(task, cursor, pk_action):
    '''
     Cette fonction retourne le follow-up associé à une request s'il n'y en a qu'un associé à l'employé
     Ou s'il n'y en a qu'un sur la request.
    '''
    uid = task.env.context.get('uid') or task._uid
    pk_contact = task.env['res.users'].browse(uid).partner_id.pk_contact

    # TypeStatus table has Open = 2
    cursor.execute("SELECT PK_FollowUp FROM dbo.FollowUp f"
                   " JOIN dbo.request r ON r.PK_Request = f.RequestID"
                   " JOIN dbo.action a ON a.RequestID = r.PK_Request"
                   " JOIN dbo.R_MultiContact_FollowUP m ON m.FollowUpID = f.PK_FollowUp"
                   " WHERE a.PK_action = %d and m.Employee_ContactID = %d and f.status = 2 "
                   " Group by PK_FollowUP ", (pk_action, pk_contact))

    request_followup = cursor.fetchall()

    if len(request_followup) == 1:
        return request_followup[0]["PK_FollowUp"]
    else:
        if len(request_followup) == 0:
            cursor.execute("SELECT PK_FollowUp FROM dbo.FollowUp f"
                           " JOIN dbo.request r ON r.PK_Request = f.RequestID"
                           " JOIN dbo.action a ON a.RequestID = r.PK_Request"
                           " JOIN dbo.R_MultiContact_FollowUP m ON m.FollowUpID = f.PK_FollowUp"
                           " WHERE a.PK_action = %d and f.status = 2 "
                           " Group by PK_FollowUP ", pk_action)

            request_followup = cursor.fetchall()

            if len(request_followup) == 1:
                return request_followup[0]["PK_FollowUp"]

    return False


def open_close_followup_from_uranos(cursor, pk_followup, action='close', task=False, pk_action=False):
    if not task and not pk_action:
        raise ValidationError("Task or pk_action required to close followup")
    if not pk_action:
        # must have a quickTS entry and not create in MSSQL only
        raise ValidationError("pk_action required to close followup now")

    if action == 'close':
        db_action = 'F'
        status = 0
    elif action == 'open':
        db_action = 'O'
        status = 2

    if task and not pk_action:
        event = get_event_from_uranos(task, cursor)
        if event:
            pk_action = event['PK_Action']
        else:
            pk_action, _ = create_action_inner(task, cursor, create_fua=False, billing_time_zero=True)

    # create fua entry
    add_progression_to_followup(cursor, pk_followup, pk_action, db_action)

    cursor.execute("UPDATE dbo.FollowUp"
                   " SET status = %d"
                   " WHERE PK_FollowUp = %d",
                   (status, pk_followup))


def close_all_followup_from_uranos(cursor, pk_request, pk_action):
    # from TypeStatus table : [(0, 'Closed'), (1, 'Cancelled'), (2, 'Open')]
    cursor.execute("SELECT PK_FollowUp FROM dbo.FollowUp"
                   " WHERE RequestID = %d and Status = 2", pk_request)
    fu_list = [record['PK_FollowUp'] for record in cursor.fetchall()]
    for pk_followup in fu_list:
        open_close_followup_from_uranos(cursor, pk_followup, pk_action=pk_action, action='close')


def create_uranos_request(task, cursor):
    priority = TASK_TO_PK_TYPE[task.priority_microcom]
    customer_id = task.partner_id.pk_contact or task.project_id.partner_id.pk_contact
    # TODO: MIGRATION: confirm if obsolete
    # if task.project_id.code:
    #     name = '{code} - o{id}t - {name}'.format(code=task.project_id.code, id=task.id, name=task.name or '')
    # else:
    name = 'o{id}t - {name}'.format(id=task.id, name=task.name or '')
    description = null2none(task.customer_description)

    if priority:
        # write TypePriorityID as string, cannot write null string (?)
        cursor.execute(
            "INSERT INTO dbo.Request (Customer_ContactID, TypePriorityID, TypeRiskID,"
            "Status, Name, Description, taskOdooID, projectOdooID, projectName) "
            "Values (%d, %s, 1, 2, %s, %s, %d, %d, %s)",
            (customer_id, priority, name, description, task.id,
             null2none(task.project_id.id), null2none(task.project_id.name)))
    else:
        cursor.execute(
            "INSERT INTO dbo.Request (Customer_ContactID, TypeRiskID,"
            "Status, Name, Description, taskOdooID, projectOdooID, projectName) "
            " Values (%d, 1, 2, %s, %s, %d, %d, %s)",
            (customer_id, name, description, task.id,
             null2none(task.project_id.id), null2none(task.project_id.name)))

    return get_new_id(cursor)


def update_partner_uranos_request(task, cursor):
    customer_id = task.partner_id.pk_contact or task.project_id.partner_id.pk_contact
    cursor.execute("UPDATE dbo.Request SET Customer_ContactID = %d WHERE PK_Request = %d",
                   (customer_id, task.request_pk))


def change_action_request(pk_action, pk_request, cursor):
    cursor.execute("UPDATE dbo.action SET RequestID = %d WHERE PK_Action = %d ", (pk_request, pk_action))


def get_current_time_in_minute(task):
    # datetime in local timezone
    tz_name = task._context.get('tz') or task.env.user.tz or 'UTC'
    context_tz = pytz.timezone(tz_name)
    cur_date = datetime.now(context_tz)
    hour = cur_date.hour
    minute = cur_date.minute

    return hour * 60 + minute


def create_uranos_event(task, cursor, billing_time_zero=False):
    customer_id = task.partner_id.pk_contact or task.project_id.partner_id.pk_contact
    uid = task.env.context.get('uid') or task._uid
    user_id = task.env['res.users'].browse(uid).partner_id.pk_contact
    cur_date = datetime.now()
    timeInMinute = get_current_time_in_minute(task)

    if billing_time_zero:
        # Set start time and end time to the same value.
        cursor.execute("insert into dbo.Event (Employee_ContactID, Customer_ContactID, DAteStartEvent, "
                       "TimeStartEvent, TimeEndEvent, State) Values (%d, %d, %s, %d, %d, 0)",
                       (user_id, customer_id, cur_date.strftime("%Y-%m-%d"), timeInMinute, timeInMinute))
    else:
        cursor.execute("insert into dbo.Event (Employee_ContactID, Customer_ContactID, DAteStartEvent, "
                       "TimeStartEvent, State) Values (%d, %d, %s, %d, 0)",
                       (user_id, customer_id, cur_date.strftime("%Y-%m-%d"), timeInMinute))

    return get_new_id(cursor)


def delete_uranos_event(cursor, pk_event):
    cursor.execute("DELETE FROM dbo.R_MultiEvent_TypeEvent WHERE EventID = %d", (pk_event))
    cursor.execute("DELETE FROM dbo.TravelExpense WHERE EventID = %d", (pk_event))
    cursor.execute("DELETE FROM dbo.Event WHERE PK_Event = %d", (pk_event))


def delete_travel_expense(cursor, pk_travel_expense):
    cursor.execute("DELETE FROM dbo.TravelExpense WHERE PK_TravelExpense = %d", (pk_travel_expense))


def create_uranos_billing(cursor):
    cursor.execute("insert into dbo.Billing (TypeBillingID) Values (null)")

    return get_new_id(cursor)


def create_travel_expense(cursor, pk_event, start_address, destination_address, return_address,
                          start_km, return_km):
    """
    This method create a Travel Expense in Uranos from Odoo. It's called from microcom_ts
    return: the PK of the created Travel Expense
    """

    cursor.execute(
        """
        INSERT INTO dbo.TravelExpense(
            EventID, 
            AddressStartID, 
            TypeStart,
            AddressReturnID,
            TypeReturn, 
            AddressDestinationID, 
            StartKilometres, 
            ReturnKilometres
        ) VALUES (%d, %d, %d, %d, %d, %d, %d, %d)""",
        (
            pk_event,
            ADDRESSES_PK_MAP.get(start_address),
            ADDRESSES_TYPE_MAP.get(start_address),
            ADDRESSES_PK_MAP.get(return_address),
            ADDRESSES_TYPE_MAP.get(return_address),
            ADDRESSES_PK_MAP.get(destination_address),
            start_km,
            return_km
        )
    )
    return get_new_id(cursor)


def create_uranos_action(task, cursor, pk_request, pk_event, pk_billing, action_msg=None):
    if action_msg is None:
        action_msg = _('Action créée depuis Odoo')
    # action_msg = action_msg.encode('utf-16', errors='replace')
    cursor.execute("insert into dbo.Action (EventID, RequestID, BillingID, Name, State, DetailAction) "
                   "Values (%d, %d, %d, %s, 0, %s)",
                   (pk_event, pk_request, pk_billing, action_msg, 'N-%s' % (
                       task.partner_id.ref or task.project_id.partner_id.ref,)))

    return get_new_id(cursor)


def create_uranos_followup(followup, pk_action, cursor):
    """ This function is called from microcom_ts
    """

    cursor.execute(
        "INSERT INTO dbo.FollowUp (ActionID, Name, Description, DateDue, TimeDue, Status, RequestID, DurationOdoo) "
        "Values (%d, %s, %s, %s, %s, %d, %d, %d)",
        (pk_action, followup.name or None, followup.description or None, followup.date_deadline,
         followup.deadline_minute, 2, followup.task_id.request_pk, followup.duration_minute)
    )

    pk_followup = get_new_id(cursor)

    cursor.execute(
        "INSERT INTO dbo.R_MultiContact_FollowUp (FollowUpID, Employee_ContactID, Sent) "
        "Values (%d, %d, 0)",
        (pk_followup, followup.user_id.pk_contact)
    )
    add_progression_to_followup(cursor, pk_followup, pk_action, 'N')

    return pk_followup


def update_uranos_followup_contact(followup, cursor):
    # Verifier si le contact est déjà présent sur le Followup
    cursor.execute(
        "SELECT FollowUpID, Employee_ContactID "
        "FROM R_MultiContact_FollowUp "
        "WHERE FollowUpID = %d and Employee_ContactID = %d ",
        (followup.pk_followup, followup.user_id.pk_contact)
    )
    followup_contact = cursor.fetchone()

    if not followup_contact:
        # On prends pour acquis qu'il n'y a qu'un seul employée par followup.
        # On efface tous les contacts de ce followup et on ajoute le nouveau contact.
        cursor.execute(
            "DELETE FROM R_MultiContact_FollowUp "
            "WHERE FollowUpID = %d",
            followup.pk_followup
        )

        cursor.execute(
            "INSERT INTO dbo.R_MultiContact_FollowUp (FollowUpID, Employee_ContactID, Sent) "
            "Values (%d, %d, 0)",
            (followup.pk_followup, followup.user_id.pk_contact)
        )


def update_uranos_followup(followup, cursor):
    """ This function is called from microcom_ts
        """
    # if billing_code_id is not set, force 0-value into null
    # now moving followup to current request
    cursor.execute("""
        Update dbo.FollowUp
            set name = %s,
            description = %s,
            DateDue = %s,
            TimeDue = %d,
            DefaultBillingID = NULLIF(%d, 0),
            DurationOdoo = %d,
            RequestID = %d
        Where PK_Followup = %d""",
                   (followup.name or '', followup.description or '', followup.date_deadline,
                    followup.deadline_minute, followup.billing_code_id.pk_typebilling, followup.duration_minute,
                    followup.task_id.request_pk,
                    followup.pk_followup)
                   )

    update_uranos_followup_contact(followup, cursor)


def add_progression_to_followup(cursor, PK_FollowUp, PK_Action, action):
    cursor.execute(
        "insert into dbo.R_MultiProvenanceFollowUp_MultiDestinationAction (FollowUpID, ActionID, Action, Sent) "
        "Values (%d, %d, %s, 0)", (PK_FollowUp, PK_Action, action))

    return get_new_id(cursor)


def create_request(task):
    connection_kwargs = get_connection_kwargs(task)
    if connection_kwargs:
        try:
            with pymssql.connect(**connection_kwargs) as conn:
                cursor = conn.cursor()

                if task.request_pk == 0:
                    if (task.partner_id or (task.project_id and task.project_id.partner_id)):
                        # Add new request, event, billing and action to uranos/timsheet
                        pk_request = create_uranos_request(task, cursor)
                        pk_event = create_uranos_event(task, cursor)
                        pk_billing = create_uranos_billing(cursor)
                        action_msg = _('Requête créée depuis Odoo')
                        create_uranos_action(task, cursor, pk_request, pk_event, pk_billing, action_msg=action_msg)
                        task.with_context(open_ts_cursor=cursor).request_pk = pk_request
                        conn.commit()
                    else:
                        raise UserError(_('Project/customer or contact required'))

        except Exception as ex:
            raise UserError(ex)


def create_request_inner(task, cursor, pk_event):
    if task.request_pk == 0:
        if task.partner_id or (task.project_id and task.project_id.partner_id):
            # Add new request, event, billing and action to uranos/timsheet
            pk_request = create_uranos_request(task, cursor)
            if not pk_event:
                pk_event = create_uranos_event(task, cursor)

            pk_billing = create_uranos_billing(cursor)
            action_msg = _('Requête créée depuis Odoo')
            pk_action = create_uranos_action(task, cursor, pk_request, pk_event, pk_billing, action_msg=action_msg)
            task.with_context(pk_action=pk_action).request_pk = pk_request
            return pk_action, pk_event
        else:
            raise UserError(_('Project/customer or contact required'))
    return None, None


def close_request(task, pk_action):
    # sanity check
    if task.request_pk == 0:
        raise UserError(_('No request associated'))
    if not pk_action:
        raise UserError(_('No action associated'))
    cursor = task.env.context.get('open_ts_cursor')
    if cursor:
        close_request_inner(task, cursor, pk_action)
    else:
        try:
            with open_ts_cursor(task) as cursor:
                if cursor is None:
                    # TODO tag as dirty
                    return
                close_request_inner(task, cursor, pk_action)
        except Exception as ex:
            raise UserError(ex)


def close_request_inner(task, cursor, pk_action):
    # followup are closed through an action
    pk_request = task.request_pk
    # if not pk_action:
    #     pk_event = create_uranos_event(task, cursor)
    #     pk_billing = create_uranos_billing(cursor)
    #     action_msg = _('Requête fermée depuis Odoo')
    #     pk_action = create_uranos_action(task, cursor, pk_request, pk_event, pk_billing, action_msg=action_msg)
    close_all_followup_from_uranos(cursor, pk_request, pk_action)

    # close request
    cursor.execute("UPDATE dbo.Request SET status = 0 WHERE PK_Request = %s", (pk_request,))


def reopen_request(task, pk_action):
    # sanity check
    if task.request_pk == 0:
        raise UserError(_('No request associated'))
    if not pk_action:
        raise UserError(_('No action associated'))
    cursor = task.env.context.get('open_ts_cursor')
    if cursor:
        reopen_request_inner(task, cursor, pk_action)
    else:
        try:
            with open_ts_cursor(task) as cursor:
                if cursor is None:
                    # TODO tag as dirty
                    return
                reopen_request_inner(task, cursor, pk_action)
        except Exception as ex:
            raise UserError(ex)


def reopen_request_inner(task, cursor, pk_action):
    # followup are closed through an action
    pk_request = task.request_pk

    # open request
    cursor.execute("UPDATE dbo.Request SET status = 2 WHERE PK_Request = %s", (pk_request,))


def open_close_followup(pk_followup, task=False, pk_action=False, action='close'):
    if not task and not pk_action:
        raise ValidationError("Task or pk_action required to close followup")

    connection_kwargs = get_connection_kwargs(task)
    if connection_kwargs:
        try:
            with pymssql.connect(**connection_kwargs) as conn:
                cursor = conn.cursor()
                open_close_followup_from_uranos(cursor, pk_followup, task=task, pk_action=pk_action, action=action)
                conn.commit()

        except Exception as ex:
            raise UserError(ex)


def unassign_request(task):
    task.request_pk = 0


def get_create_open_event(cursor, task_id):
    event = get_event_from_uranos(task_id, cursor)
    if event:
        pk_action = event['PK_Action']
    else:
        # Add new event to create or update followup
        pk_action, _ = create_action_inner(task_id, cursor, billing_time_zero=True)
    return pk_action


def create_event(task):
    connection_kwargs = get_connection_kwargs(task)
    if connection_kwargs:
        try:
            with pymssql.connect(**connection_kwargs) as conn:
                cursor = conn.cursor()
                event = get_event_from_uranos(task, cursor)
                timeInMinute = get_current_time_in_minute(task)

                if event:
                    cursor.execute(
                        "update event set timeEndEvent = %d where PK_event = %d" % (timeInMinute, event["PK_Event"]))
                else:
                    create_action_inner(task, cursor)

                conn.commit()

        except Exception as ex:
            raise UserError(ex)


def create_action_inner(task, cursor, create_fua=True, billing_time_zero=False, pk_event=False):
    if not pk_event:
        pk_event = create_uranos_event(task, cursor, billing_time_zero=billing_time_zero)
    pk_billing = create_uranos_billing(cursor)
    action_msg = _('Evénement créé depuis Odoo')
    pk_action = create_uranos_action(task, cursor, task.request_pk, pk_event, pk_billing, action_msg=action_msg)
    pk_followup = get_followup_from_uranos(task, cursor, pk_action)
    if pk_followup and create_fua:
        add_progression_to_followup(cursor, pk_followup, pk_action, 'P')
    return pk_action, pk_event


def is_request_closed(task):
    connection_kwargs = get_connection_kwargs(task)
    if connection_kwargs:
        try:
            with pymssql.connect(**connection_kwargs) as conn:
                cursor = conn.cursor()
                return is_request_closed_inner(task, cursor)

        except Exception as ex:
            raise UserError(ex)
    else:
        return True


def is_request_closed_inner(task, cursor):
    cursor.execute("Select status from dbo.Request where PK_Request = %s", (task.request_pk,))
    status = cursor.fetchone()

    if status and (status['status'] == 0 or status['status'] == 1):
        return True
    else:
        return False


# --------------------------------------------------------------------------------


def pull_ts_from_request(self, cursor, pk_request):
    """ read MSSQL fields that have an impact on quickTS
    """
    assert cursor

    def fix_null(text):
        # convert null/None to null/False
        if text is None:
            return False
        # MSSQL gremlin
        while text and len(text) and ord(text[0]) > 64000:
            text = text[1:]
        return text

    sql = """
        SELECT r.Name, r.Description, r.InternalComment
        FROM [Request] r
        WHERE PK_Request = %d
    """
    sql_args = (pk_request,)
    cursor.execute(sql, sql_args)
    found = cursor.fetchone()
    if not found:
        return {}
    # truncate 'o99t - '
    name = found['Name']
    if name:
        name = re.sub(r'.*o\d+t - ', '', name)
    # do round trip same as description_as_text
    description = fix_gremlins(found['Description'])
    return {
        # returns None for null, expects False
        'name': fix_null(name),
        # conversion is necessary or compare will fail (removes starting whitespace)
        'customer_description': fix_null(description),
        'internal_comment_ts': fix_null(found['InternalComment']),
    }


def push_request_to_ts(self, cursor):
    assert cursor

    # add TS prefix
    name = self.name
    if name:
        name = 'o{}t - {}'.format(self.id, name)
    priority = TASK_TO_PK_TYPE[self.priority_microcom]
    # Request
    sql = """
        UPDATE [Request]
        SET Name = %s,
            Description = %s,
            InternalComment = %s,
            projectOdooID = %d,
            projectName = %s,
            TypePriorityID = %s
        WHERE PK_Request = %d
    """
    sql_args = (
        null2none(name),
        null2none(self.customer_description),
        null2none(self.internal_comment_ts),
        null2none(self.project_id.id),
        null2none(self.project_id.name),
        null2none(priority),
        self.request_pk)
    cursor.execute(sql, sql_args)


# --------------------------------------------------------------------------------


class Task(models.Model):
    _inherit = "project.task"

    request_pk = fields.Integer('Uranos Request PK', copy=False)
    uranos_request_id = fields.Many2one('uranos.request', string='Uranos Request ID', copy=False)
    uranos_status = fields.Char(string='Request Status', compute='_compute_actual_duration',
                                groups='uranos_ts.group_uranos_ts,uranos_ts.group_uranos_ts_admin')
    actual_duration = fields.Float('Total', compute='_compute_actual_duration',
                                   groups='uranos_ts.group_uranos_ts,uranos_ts.group_uranos_ts_admin')
    action_ids = fields.One2many('uranos.action', string='Actions', compute='_compute_action_ids')
    internal_comment_ts = fields.Text(string='Internal Comment TS')
    uranos_changes = fields.Text('Changes', compute='_compute_uranos_changes')
    has_changes = fields.Boolean('Has Changes', compute='_compute_uranos_changes')
    show_timesheet = fields.Boolean('Show Timesheet', related='project_id.show_timesheet')
    customer_description = fields.Text()
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda x: x.env.user)
    # 15909
    customer_linked_task = fields.Boolean(
        string='Customer Linked task',
        compute='_customer_linked_task'
    )
    actual_sale = fields.Float('Sales', compute='_compute_actual_sale',
                               groups='uranos_ts.group_uranos_ts_admin')

    # 15908
    def merge_tasks(self, task_ids):
        for task in task_ids:
            if task == self:
                continue
            connection_kwargs = get_connection_kwargs(task)
            if connection_kwargs:
                try:
                    # /!\ DANGER /!\ using out-of-module fields from microcom_ts /!\ DANGER /!\
                    #
                    with pymssql.connect(**connection_kwargs) as conn:
                        cursor = conn.cursor()
                        #
                        for followup in task.followup_ids:
                            followup.task_id = self
                            followup.is_main = False
                            update_uranos_followup(followup, cursor)
                        #
                        for pk_action in task.microcom_timesheet_ids.mapped('pk_action'):
                            change_action_request(pk_action, self.request_pk, cursor)
                        #
                        conn.commit()
                        for rec in task.microcom_timesheet_ids:
                            rec.synchronize_from_ts_inner(cursor)

                except (UserError, ValidationError):
                    raise
                except Exception as ex:
                    raise UserError(ex)

            # TODO when MSSQL is not active, followup.task_id are not moved (because destructive)
            if task.customer_description:
                customer_description = '[%s:] %s' % (task.name, task.customer_description)
                self.customer_description = (self.customer_description or '') + '\n' + customer_description
            if task.description:
                task_description = '[%s:] %s' % (task.name, task.description)
                self.description = (self.description or '') + '\n' + task_description
            if task.internal_comment_ts:
                internal_comment_ts = '[%s:] %s' % (task.name, task.internal_comment_ts)
                self.internal_comment_ts = (self.internal_comment_ts or '') + '\n' + internal_comment_ts

            # close_request_button
            task.with_context(no_create_timesheet=True).close_request_button()
        return True

    # 15909
    def set_change_partner_ts(self):
        for task in self:
            microcom_timesheet_ids = task.microcom_timesheet_ids
            """We need to control billed tasks"""
            if any(ts.state == 'billed' for ts in microcom_timesheet_ids):
                raise UserError(_("This customer has already been invoiced"))
            #
            connection_kwargs = get_connection_kwargs(task)
            if connection_kwargs:
                try:
                    with pymssql.connect(**connection_kwargs) as conn:
                        cursor = conn.cursor()
                        update_partner_uranos_request(task, cursor)
                        conn.commit()
                        for rec in microcom_timesheet_ids:
                            rec.synchronize_from_ts_inner(cursor)
                except (UserError, ValidationError):
                    raise
                except Exception as ex:
                    raise UserError(ex)

    # 15909
    @api.depends('action_ids')
    def _customer_linked_task(self):
        for rec in self:
            if rec.request_pk:
                # if any(ts for ts in rec.action_ids):
                if self.env.user.has_group('uranos_ts.group_uranos_approval'):
                    rec.customer_linked_task = True
                else:
                    rec.customer_linked_task = False
            else:
                rec.customer_linked_task = True

    @api.onchange('user_id')
    def _onchange_user_id(self):
        """
        make sure the task responsible is added as assignee for consistency
        """
        for task in self:
            if task.user_id:
                task.user_ids |= task.user_id

    @api.onchange('user_ids')
    def _onchange_user_ids(self):
        for task in self:
            if task.user_ids and not task.user_id:
                task.user_id = task.user_ids[0]

    @api.depends('uranos_request_id.write_date', 'write_date')
    def _compute_uranos_changes(self):
        for record in self:
            if not record.uranos_request_id:
                record.uranos_changes = _('Request entry not found')
                record.has_changes = False
                continue
            change_list = []
            uranos_request_id = record.uranos_request_id
            # remove prefix
            name_ts = fix_gremlins(uranos_request_id.name)
            if name_ts:
                name_ts = re.sub(r'.*o\d+t - ', '', name_ts)
            if record.name != name_ts:
                change_list.append((_('Name'), name_ts, record.name))
            description_ts = fix_gremlins(uranos_request_id.description)
            if record.customer_description != description_ts:
                change_list.append((_('Description'), description_ts, record.customer_description))
            # False stored as empty string
            internal_comment_ts = fix_gremlins(uranos_request_id.internal_comment)
            if record.internal_comment_ts != internal_comment_ts:
                change_list.append(
                    (_('Internal Comment'), internal_comment_ts, record.internal_comment_ts))
            record.uranos_changes = '\n'.join('{}: {} → {}'.format(a, b or '', c or '') for a, b, c in change_list)
            record.has_changes = bool(change_list)

    @api.depends('uranos_request_id.followup_ids', 'uranos_request_id.followup_ids.actual_duration',
                 'uranos_request_id.status')
    def _compute_actual_duration(self):
        for record in self:
            if record.uranos_request_id:
                record.uranos_status = record.uranos_request_id.status
                record.actual_duration = sum(record.uranos_request_id.action_ids.mapped('billing_time'))
            else:
                record.uranos_status = None
                record.actual_duration = 0

    @api.depends('uranos_request_id.action_ids.billing_amount')
    def _compute_actual_sale(self):
        for record in self:
            if record.uranos_request_id:
                record.actual_sale = sum(record.uranos_request_id.action_ids.mapped('billing_amount'))
            else:
                record.actual_sale = 0

    @api.depends('uranos_request_id.action_ids.date_time_start_event',
                 'uranos_request_id.action_ids.billing_time')
    def _compute_action_ids(self):
        """ find Actions linked to current task
        Display is limited to own actions unless user has admin rights
        """
        for record in self:
            # TODO fix rights/domain to refactor as straight related='uranos_request_id.action_ids'
            if record.uranos_request_id:
                record.action_ids = record.uranos_request_id.action_ids
            # elif record.uranos_request_id:
            #     user_partner_id = self.env.user.partner_id
            #     action_ids = record.uranos_request_id.action_ids.filtered(
            #         lambda action: action.event_id.employee_partner_id == user_partner_id)
            #     record.action_ids = action_ids
            else:
                record.action_ids = False

    def update_ts_task(self, vals, old_vals=None):
        """ any write will synchronize both ways
        non-concurrent changes are pulled from TS
        local changes are pushed to TS
        """

        """
        def replace_description(vals):
            # Replace description by customer_description.
            # For Uranos we used customer_description as description.
            if 'description' in vals:
                vals.pop('description')
            if 'customer_description' in vals:
                vals['description'] = vals['customer_description']
                vals.pop('customer_description')
            return vals

        vals = replace_description(vals)
        old_vals = replace_description(old_vals)
        """

        if not self.request_pk and self.uranos_request_id.pk_request:
            # can complete record
            self.request_pk = self.uranos_request_id.pk_request
        if not self.request_pk:
            # record is incomplete, do nothing
            return
        #
        # skip unless affecting TS fields
        ts_vals = {k for k in vals if k in (
            'customer_description', 'internal_comment', 'name', 'priority_microcom', 'project_id'
        )}
        if not ts_vals:
            return

        #
        def present(key, ts, old, new):
            return key

        #
        # block recursive calls while cursor is open
        if 'open_ts_cursor' in self.env.context:
            return
        # access TS/MSSQL
        with open_ts_cursor(self) as cursor:
            if cursor is None:
                # TODO tag as dirty
                return
            self = self.with_context(open_ts_cursor=cursor)
            ts_dict = pull_ts_from_request(self, cursor, self.request_pk)
            if old_vals:
                # updating an existing record, check if TS made a change to the same field
                both_changed = {k for k in ts_dict if k in old_vals}
                collisions = [
                    present(k, ts_dict[k], old_vals[k], self[k])
                    for k in both_changed if old_vals[k] != ts_dict[k] and self[k] != ts_dict[k]]

                if collisions:
                    raise ValidationError(
                        _('Some fields were modified from Timesheet, synchronize before changing them.\n(%s)')
                        % ', '.join(collisions))
            # update from TS/MSSQL
            changed_ts_dict = {k: ts_dict[k] for k in ts_dict if k not in vals}
            self.write(changed_ts_dict)
            #
            # synchronize records in both DB
            push_request_to_ts(self, cursor)

    @api.model_create_multi
    def create(self, vals_list):
        # TODO:MIGRATION
        res = super().create(vals_list)
        for record, vals in zip(res, vals_list):
            record.update_ts_task(vals)
        return res

    def write(self, vals):
        #
        for rec in self:
            old_vals = {k: rec[k] for k in vals}
        res = super().write(vals)
        for rec in self:
            rec.update_ts_task(vals, old_vals)
            # 15909
            if vals.get('partner_id'):
                rec.set_change_partner_ts()
        return res

    def unassign_request_button(self):
        for record in self:
            unassign_request(record)

    def create_event_button(self):
        for record in self:
            create_event(record)

    def button_do_nothing(self):
        pass

    def button_synchronize(self):
        for record in self:
            with open_ts_cursor(record) as cursor:
                if cursor is None:
                    raise ValidationError(_('TS is not connected'))
                ts_dict = pull_ts_from_request(record, cursor, record.request_pk)
                if not ts_dict:
                    raise ValidationError(_('No entry found'))

                record.with_context(open_ts_cursor=cursor).write(ts_dict)

    def action_assign_to_me(self):
        # TODO:MIGRATION:NEW: set current user id as task responsible if not set
        res = super(Task, self).action_assign_to_me()
        for task in self.filtered(lambda t: not t.user_id):
            task.user_id = self.env.user
        return res

    @api.model
    def patch_ts_project(self):
        requests = self.env['uranos.request'].search([
            ('task_id', '!=', False),
            ('project_ts', '=', False),
        ], order='pk_request desc', limit=10000)
        tasks = requests.mapped('task_id')
        if not tasks:
            _logger.warning("no task to patch")
            return
        _logger.warning("patching from %d" % tasks[0].request_pk)
        with open_ts_cursor(self) as cursor:
            if cursor is None:
                # TODO tag as dirty
                return
            for task in tasks:
                cursor.execute("""
                    UPDATE Request
                    set projectOdooID = %d,
                        projectName = %s
                    where PK_Request = %d
                """, (task.project_id.id, task.project_id.name, task.request_pk))
        _logger.warning("patched down to %d" % task.request_pk)


# class ProjectIssue(models.Model):
#     _inherit = "project.issue"
#
#     request_pk = fields.Integer('Uranos Request ID')
#
#
#     def create_request_button(self):
#         create_request(self, 'issueOdooID')
#
#
#     def unassign_request_button(self):
#         unassign_request(self, 'issueOdooID')


class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    is_closed_type = fields.Boolean('Closed type')
    is_canceled_type = fields.Boolean('Canceled type')


class ProjectSprint(models.Model):
    _inherit = "project.sprint"

    def find_employee_missing_actions(self, employee_partner_id):
        """ find Actions that should count in the current sprint but are not linked
        """
        self.ensure_one()
        if not (self.date_start and self.date_end):
            raise UserError(_('Start/End date required'))

        # find entries for the current period/user
        present_request_ids = self.sprint_line_ids.filtered(
            lambda x: x.user_id == self.env.user).mapped(
            lambda x: x.task_id.uranos_request_id)
        missing_action_ids = self.env['uranos.action'].search([
            ('employee_partner_id', '=', employee_partner_id.id),
            ('date_time_start_event', '>=', self.date_start),
            ('date_time_start_event', '<', self.date_end),
            ('request_id', 'not in', present_request_ids.ids),
        ])
        # remove not-paid codes J0, V0, Z0
        missing_action_ids = missing_action_ids.filtered(
            lambda x: x.billing_type and x.billing_type[-1:] != '0')

        return missing_action_ids

    def create_empty_task_entry(self, commit=False):
        """
        """
        empty_entry = self.sprint_line_ids.filtered(
            lambda x: x.user_id == self.env.user and not x.task_id)
        if not empty_entry:
            self.sprint_line_ids.create({
                'sprint_id': self.id,
                'task_id': False,
                'user_id': self.env.user.id,
                'added_later': self.added_later,
            })
            if commit:
                # hack - commit in case of raised UserError
                self.env.cr.commit()

    def add_missing_lines(self):
        """ create sprint lines to assign missing Actions
        """
        self.create_empty_task_entry(commit=True)
        #
        missing_action_ids = self.find_employee_missing_actions(self.env.user.partner_id)
        missing_task_ids = missing_action_ids.mapped(lambda x: x.request_id.task_id)
        if not missing_task_ids:
            raise UserError(_('No missing entries'))

        for task_id in missing_task_ids:
            self.sprint_line_ids.create({
                'sprint_id': self.id,
                'task_id': task_id.id,
                'user_id': self.env.user.id,
                'added_later': self.added_later,
            })


class ProjectSprintLine(models.Model):
    _inherit = "project.sprint.line"

    # field must be stored to be used in <progressbar sum_field=""/>
    uranos_real_hours = fields.Float('TS hours', compute='_compute_uranos_real_hours', store=True)
    total_real_hours = fields.Float('Total real hours', compute='_compute_uranos_real_hours', store=True)
    own_action_ids = fields.One2many('uranos.action', string='Actions', compute='_compute_action_ids')
    any_action_ids = fields.One2many('uranos.action', string='Any Actions', compute='_compute_action_ids')

    @api.depends('task_id.uranos_request_id.action_ids.date_time_start_event',
                 'task_id.uranos_request_id.action_ids.billing_time',
                 'sprint_id.date_start', 'sprint_id.date_end', 'real_hours',
                 'user_id')
    def _compute_uranos_real_hours(self):
        for record in self:
            # remove not-paid codes J0, V0, Z0
            paid_action_ids = record.any_action_ids.filtered(
                lambda x: x.billing_type and x.billing_type[-1:] != '0')
            record.uranos_real_hours = sum(paid_action_ids.mapped('billing_time'))
            record.total_real_hours = record.real_hours + record.uranos_real_hours

    @api.depends('task_id.uranos_request_id.action_ids.date_time_start_event',
                 'task_id.uranos_request_id.action_ids.billing_time',
                 'sprint_id.date_start', 'sprint_id.date_end',
                 'user_id')
    def _compute_action_ids(self):
        """ find Actions that should count in the current sprint
        Display is limited to own actions unless user has admin rights
        """
        for record in self:
            # access any user data
            any_action_ids = False
            date_start = record.sprint_id.date_start
            date_end = record.sprint_id.date_end
            if date_start and date_end:
                if not record.task_id:
                    # accumulate all non-assigned requests
                    any_action_ids = record.sprint_id.find_employee_missing_actions(record.user_id.partner_id)
                elif record.task_id.uranos_request_id:
                    any_action_ids = record.task_id.uranos_request_id.action_ids.filtered(
                        lambda action: date_start <= action.date_time_start_event < date_end and
                                       record.user_id.partner_id == action.event_id.employee_partner_id)
            # access any user data, needs admin rights
            record.any_action_ids = any_action_ids
            # access own data
            if self.env.user == record.user_id:
                record.own_action_ids = any_action_ids
            else:
                record.own_action_ids = False


class ProjectCategory(models.Model):
    _name = 'project.microcom.category'
    _description = 'Project Category'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')
