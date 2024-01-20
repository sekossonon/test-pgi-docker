import logging
import pymssql
import pytz
from datetime import datetime, timedelta

from odoo import tools
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .res_config import get_connection_kwargs

_logger = logging.getLogger(__name__)

# Odoo gets slow if too many records are written at once, we do batch commits
MAX_LINES = 100
MAX_LINES_TO_UPDATE = 2000


def minutes_to_time(minutes, separator=':'):
    hours, minutes = divmod(minutes, 60)
    return str(hours) + separator + str(minutes).zfill(2)


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


class UranosImport(models.Model):
    _name = "uranos.import"
    _description = "Uranos Import"

    import_start_date = fields.Datetime('Import Start Date')
    import_end_date = fields.Datetime('Import End Date')
    last_pk_billing = fields.Integer('Last PK_Billing')
    import_batch = fields.Boolean('Batch')

    @api.model
    def importRequest(self, cursor, start_date, end_date, logs=False):
        import_count = 0
        nb_records_processed = 0

        sql_select_count = "Select Count(*) as nb_record"

        sql_select_columns = ("SELECT Pk_Request, Customer_contactID, TypePriority.Name as type_priority, TypeRisk.Name as type_risk,"
                              " Case Status when 0 then 'Closed' when 1 then 'Cancel' else 'Open' End as Status,"
                              " Request.Name as Name, SUBSTRING(Description, 1, 2000) as Description,"
                              " SUBSTRING(InternalComment, 1, 2000) AS InternalComment, Correction,"
                              " projectOdooID, projectName")

        sql_from_string = (" From Request"
                           " Left Join TypePriority on TypePriority.PK_Type = Request.TypePriorityID"
                           " Left JOin TypeRisk on TypeRisk.PK_Type = Request.TypeRiskID")

        if start_date:
            sql_condition = (" WHERE LastUpdateDate is not null and LastUpdateDate > '%s' and LastUpdateDate <= '%s'" %
                             (start_date, end_date))
        else:
            sql_condition = (" WHERE LastUpdateDate is null or LastUpdateDate <= '%s'" %
                             (end_date,))

        sql_order_by = " ORDER BY Pk_Request "

        cursor.execute(sql_select_count + sql_from_string + sql_condition)
        nb_records = cursor.fetchone()['nb_record']
        if logs:
            _logger.warning("Nb Request = %d" % nb_records)

        cursor.execute(sql_select_columns + sql_from_string + sql_condition + sql_order_by)
        request = cursor.fetchone()

        while request:
            contact = self.env['res.partner'].with_context(active_test=False).search([('pk_contact', '=', request['Customer_contactID'])])
            if len(contact) == 1:
                partner_id = contact.id
            else:
                partner_id = False
            vals = {'pk_request': request['Pk_Request'],
                    'partner_id': partner_id,
                    'type_priority': request['type_priority'],
                    'type_risk': request['type_risk'],
                    'status': request['Status'],
                    'name': request['Name'],
                    'description': request['Description'],
                    'internal_comment': request['InternalComment'],
                    'correction': request['Correction'],
                    'project_ts': request['projectOdooID'],
                    'project_name': request['projectName']}

            uranos_request = self.env['uranos.request'].search([['pk_request', '=', request['Pk_Request']]])

            try:
                if uranos_request:
                    uranos_request.write(vals)
                else:
                    uranos_request.create(vals)
            except Exception as ex:
                ir_model_data = self.env['ir.model.data']
                template_id = ir_model_data.get_object_reference('uranos_ts', 'email_template_error')[1]
                error_to_print = 'Request: ' + str(ex) + ':' + str(vals)
                self.generate_and_send_email(error_to_print, template_id)

            import_count += 1
            nb_records_processed += 1
            if import_count >= MAX_LINES:
                if logs:
                    _logger.warning("Requests processed: %d, last Pk_Request = %d" %
                                    (nb_records_processed, request['Pk_Request']))
                # print('request:' + str(request['Pk_Request']))
                self._cr.commit()
                import_count = 0

            request = cursor.fetchone()

        if nb_records != nb_records_processed:
            print('There is a problem with the import, all Request records have not been processed')
            # raise ValidationError(_('There is a problem with the import, all Request records have not been processed'))

    @api.model
    def importEvent(self, cursor, start_date, end_date, logs=False):
        import_count = 0
        nb_records_processed = 0
        dirty_set = set()

        sql_select_count = "Select Count(*) as nb_record"

        sql_select_columns = (
            "SELECT Pk_Event, Employee_ContactID, Customer_ContactID, DateStartEvent, DateEndEvent, "
            "       TimeStartEvent, TimeEndEvent, AdjustTime, AdjustReason, "
            "       Case State when 0 Then 'Active' when 1 Then 'Canceled' End as State, "
            "       paymentMethod")

        sql_from = (" From Event"
                    " Join RoleEmployee r on r.ContactID = Event.Employee_ContactID")

        if start_date:
            sql_where = (" WHERE LastUpdateDate is not null and LastUpdateDate > '%s' and LastUpdateDate <= '%s'" %
                         (start_date, end_date))
        else:
            sql_where = (" WHERE (LastUpdateDate is null or LastUpdateDate <= '%s')" %
                         (end_date,))

        sql_order_by = " ORDER BY Pk_Event "

        cursor.execute(sql_select_count + sql_from + sql_where)
        nb_records = cursor.fetchone()['nb_record']
        if logs:
            _logger.warning("Nb Event = %d" % nb_records)

        cursor.execute(sql_select_columns + sql_from + sql_where + sql_order_by)
        event = cursor.fetchone()

        while event:

            employee_id = False
            customer_id = False

            if event['Employee_ContactID']:
                employee = self.env['res.partner'].with_context(active_test=False).search([('pk_contact', '=', event['Employee_ContactID'])])
                if employee:
                    employee_id = employee.id

            if event['Customer_ContactID']:
                Customer = self.env['res.partner'].with_context(active_test=False).search([('pk_contact', '=', event['Customer_ContactID'])])
                if Customer:
                    customer_id = Customer.id

            vals = {'pk_event': event['Pk_Event'],
                    'employee_partner_id': employee_id,
                    'customer_partner_id': customer_id,
                    'date_start_event': event['DateStartEvent'],
                    'date_end_event': event['DateEndEvent'],
                    'time_start_event': event['TimeStartEvent'],
                    'time_end_event': event['TimeEndEvent'],
                    'adjust_time': event['AdjustTime'],
                    'adjust_reason': event['AdjustReason'],
                    'state': event['State'],
                    'payment_method': event['paymentMethod']}

            uranos_event = self.env['uranos.event'].search([['pk_event', '=', event['Pk_Event']]])

            # If there is a change in the event times or dates, we add the tuple {partner, date/time value} to the dirty
            # set and in the case of the dates we also add the old date to the dirty set
            try:
                if uranos_event:
                    if employee_id:
                        new_start_date = event['DateStartEvent'].date() if event['DateStartEvent'] else False
                        new_end_date = event['DateEndEvent'].date() if event['DateEndEvent'] else False

                        if any([uranos_event.date_start_event, new_start_date]) and uranos_event.date_start_event != new_start_date:
                            if uranos_event.date_start_event:
                                dirty_set.add((employee_id, uranos_event.date_start_event))
                            if new_start_date:
                                dirty_set.add((employee_id, new_start_date))

                        if any([uranos_event.date_end_event, new_end_date]) and uranos_event.date_end_event != new_end_date:
                            dirty_set.add((employee_id, new_start_date))

                        if uranos_event.time_start_event != event['TimeStartEvent']:
                            dirty_set.add((employee_id, new_start_date))
                        if uranos_event.time_end_event != event['TimeEndEvent']:
                            dirty_set.add((employee_id, new_start_date))
                    uranos_event.write(vals)
                else:
                    uranos_event = uranos_event.create(vals)
                    dirty_set.add((uranos_event.employee_partner_id.id, uranos_event.date_start_event))
            except Exception as ex:
                ir_model_data = self.env['ir.model.data']
                template_id = ir_model_data.get_object_reference('uranos_ts', 'email_template_error')[1]
                error_to_print = 'Event: ' + str(ex) + ':' + str(vals)
                self.generate_and_send_email(error_to_print, template_id)

            import_count += 1
            nb_records_processed += 1
            if import_count >= MAX_LINES:
                if logs:
                    _logger.warning("Events processed: %d, last Pk_Event = %d" %
                                    (nb_records_processed, event['Pk_Event']))
                # print('Event:' + str(event['Pk_Event']))
                self._cr.commit()
                import_count = 0

            event = cursor.fetchone()

        if nb_records != nb_records_processed:
            print('There is a problem with the import, all Event records have not been processed')
            # raise ValidationError(_('There is a problem with the import, all Event records have not been processed'))
        return dirty_set

    @api.model
    def generate_and_send_email(self, error_to_print, template_id):
        # Note: the email will also be sent to Odoo 9 default users: "Template User" and "Demo Portal User"
        send_partners_ids = [user.partner_id for user in self.env['res.users'].search([('email', '=', 'el@microcom.ca')])]
        email_template_id = self.env['mail.template'].with_context(error_to_print=error_to_print,
                                                                   email_to=send_partners_ids[0].id,
                                                                   email_from=send_partners_ids[0].company_id.email,
                                                                   lang=send_partners_ids[0].lang).browse(template_id)
        msg_ids = []

        for partner in send_partners_ids:
            msg_ids.append(email_template_id.send_mail(partner.id))

    @api.model
    def importBilling(self, cursor, start_date, end_date, last_pk_billing, batch_update=False, logs=False):
        dirty_billings = self.env['uranos.billing']
        import_count = 0
        nb_records_processed = 0

        sql_select_count = "Select Count(*) as nb_record"

        sql_select_columns = (
            "Select Pk_Billing, TypeWork.Name + TypeRate.Name as BillingType, payRateWork, BillingRate, BillingTime, "
            " FactorBillRate, FactorPayRate, InvoiceNum, StatementID, BillingTimeReel, InvoiceDate, RoundingSales, RoundingPay,"
            " TypeWork.Type as WorkType, TypeWork.Name as WorkName, TypeRate.Name as RateName"
        )

        sql_from = (
            " From Billing"
            " Left Join TypeBilling on TypeBilling.PK_Type = TypeBillingID"
            " Left Join TypeWork on TypeWork.PK_Type = TypeBilling.WorkCodeID"
            " Left Join TypeRate on TypeRate.PK_Type = TypeBilling.RateCodeID"
        )

        if batch_update:
            if start_date:
                sql_where = (" WHERE LastBatchUpdateDate is not null and LastBatchUpdateDate > '%s' and LastBatchUpdateDate <= '%s'" %
                             (start_date, end_date))
            else:
                sql_where = (" WHERE (LastBatchUpdateDate is null or LastBatchUpdateDate <= '%s')" %
                             (end_date,))
        else:
            if start_date:
                sql_where = (" WHERE LastUpdateDate is not null and LastUpdateDate > '%s' and LastUpdateDate <= '%s'" %
                             (start_date, end_date))
            else:
                sql_where = (" WHERE (LastUpdateDate is null or LastUpdateDate <= '%s')" %
                             (end_date,))

        if last_pk_billing:
            sql_where = ("%s AND PK_Billing >= %d ") % (sql_where, last_pk_billing)

        sql_order_by = " ORDER BY Pk_Billing "

        cursor.execute(sql_select_count + sql_from + sql_where)
        nb_records = cursor.fetchone()['nb_record']
        if logs:
            _logger.warning("Nb Billing = %d" % nb_records)

        cursor.execute(sql_select_columns + sql_from + sql_where + sql_order_by)
        billings = cursor.fetchall()
        if logs:
            _logger.warning("Billing SELECT done")

        for billing in billings:
            vals = {'pk_billing': billing['Pk_Billing'],
                    'billing_type': billing['BillingType'],
                    'pay_rate_work': billing['payRateWork'],
                    'billing_rate': billing['BillingRate'],
                    'billing_time': billing['BillingTime'],
                    'factor_bill_rate': billing['FactorBillRate'],
                    'factor_pay_rate': billing['FactorPayRate'],
                    'invoice_num': billing['InvoiceNum'],
                    'statement_id': billing['StatementID'],
                    'billing_time_reel': billing['BillingTimeReel'],
                    'invoice_date': billing['InvoiceDate'],
                    'rounding_sales': billing['RoundingSales'],
                    'rounding_pay': billing['RoundingPay'],
                    'work_type': billing['WorkType'],
                    'work_name': billing['WorkName'],
                    'rate_name': billing['RateName']}

            uranos_billing = self.env['uranos.billing'].search([['pk_billing', '=', billing['Pk_Billing']]])

            # If there is a change in the event times or dates, we add the tuple {partner, date/time value} to the dirty
            # set

            try:
                if uranos_billing:
                    if uranos_billing.billing_time != billing['BillingTime']:
                        dirty_billings += uranos_billing
                    uranos_billing.write(vals)
                else:
                    uranos_billing = uranos_billing.create(vals)
                    if uranos_billing.billing_time:
                        dirty_billings += uranos_billing
            except Exception as ex:
                if logs:
                    _logger.warning("Billing exception, generating email")
                ir_model_data = self.env['ir.model.data']
                template_id = ir_model_data.get_object_reference('uranos_ts', 'email_template_error')[1]
                error_to_print = 'Billing : ' + str(ex) + ':' + str(vals)
                self.generate_and_send_email(error_to_print, template_id)

            import_count += 1
            nb_records_processed += 1
            if import_count >= MAX_LINES:
                if logs:
                    _logger.warning("Billings processed: %d, last Pk_Billing = %d" %
                                    (nb_records_processed, billing['Pk_Billing']))
                self._cr.commit()
                import_count = 0

            if nb_records_processed >= MAX_LINES_TO_UPDATE:
                return dirty_billings, billing['Pk_Billing']

        if nb_records != nb_records_processed:
            print('There is a problem with the import, all Billing records have not been processed')
            # raise ValidationError(_('There is a problem with the import, all Billing records have not been processed'))

        return dirty_billings, False

    @api.model
    def importFollowup(self, cursor, start_date, end_date, logs=False):
        import_count = 0
        nb_records_processed = 0

        sql_select_count = "Select Count(*) as nb_record"

        sql_select_columns = (
            "Select PK_FollowUp, ActionID, FollowUp.Name as Name, SUBSTRING(Description, 1, 2000) As Description, "
            "       SUBSTRING(InternalComment, 1, 2000) As InternalComment, DateDue, TimeDue, DurationMax, "
            "       ts.name as followup_status, RequestID, tw1.Name + tr1.Name as DefaultBilling, BudgetMin, BudgetMax, tw2.Name + tr2.Name as BudgetBilling, "
            "       tw1.name as DefaultWork, tr1.name as DefaultRate, tw2.name as BudgetWork, tr2.name as BudgetRate "
        )

        sql_from = (
            " From FollowUp"
            " Left Join TypeBilling tb1 on tb1.PK_Type = DefaultBillingID"
            " Left Join TypeWork tw1 on tw1.PK_Type = tb1.WorkCodeID"
            " Left Join TypeRate tr1 on tr1.PK_Type = tb1.RateCodeID"
            " Left Join TypeBilling tb2 on tb2.PK_Type = BudgetBillingID"
            " Left Join TypeWork tw2 on tw2.PK_Type = tb1.WorkCodeID"
            " Left Join TypeRate tr2 on tr2.PK_Type = tb1.RateCodeID"
            " Left Join TypeStatus ts on ts.PK_Type = FollowUp.Status"
        )

        if start_date:
            sql_where = (" WHERE LastUpdateDate is not null and LastUpdateDate > '%s' and LastUpdateDate <= '%s'" %
                         (start_date, end_date))
        else:
            sql_where = (" WHERE (LastUpdateDate is null or LastUpdateDate <= '%s')" %
                         (end_date,))

        sql_order_by = " ORDER BY Pk_FollowUp "

        cursor.execute(sql_select_count + sql_from + sql_where)
        nb_records = cursor.fetchone()['nb_record']
        if logs:
            _logger.warning("Nb FollowUp = %d" % nb_records)

        cursor.execute(sql_select_columns + sql_from + sql_where + sql_order_by)
        follow_up = cursor.fetchone()

        while follow_up:
            action_id = False
            request_id = False

            action = self.env['uranos.action'].search([('pk_action', '=', follow_up['ActionID'])])
            if action:
                action_id = action.id

            request = self.env['uranos.request'].search([('pk_request', '=', follow_up['RequestID'])])
            if request:
                request_id = request.id

            vals = {'pk_followup': follow_up['PK_FollowUp'],
                    'action_id': action_id,
                    'name': follow_up['Name'],
                    'description': follow_up['Description'],
                    'internal_comment': follow_up['InternalComment'],
                    'date_due': follow_up['DateDue'],
                    'time_due': follow_up['TimeDue'],
                    'duration_max': follow_up['DurationMax'],
                    'status': follow_up['followup_status'],
                    'request_id': request_id,
                    'default_billing': follow_up['DefaultBilling'],
                    'budget_min': follow_up['BudgetMin'],
                    'budget_max': follow_up['BudgetMax'],
                    'budget_billing': follow_up['BudgetBilling'],
                    'default_work': follow_up['DefaultWork'],
                    'default_rate': follow_up['DefaultRate'],
                    'budget_work': follow_up['BudgetWork'],
                    'budget_rate': follow_up['BudgetRate']}

            uranos_followup = self.env['uranos.followup'].search([['pk_followup', '=', follow_up['PK_FollowUp']]])

            try:
                if uranos_followup:
                    uranos_followup.write(vals)
                else:
                    uranos_followup_id = uranos_followup.create(vals)
                    task_followup_id = self.env['project.task.followup'].search([('pk_followup', '=', follow_up['PK_FollowUp'])])
                    if task_followup_id:
                        task_followup_id.uranos_followup_id = uranos_followup_id
            except Exception as ex:
                ir_model_data = self.env['ir.model.data']
                template_id = ir_model_data.get_object_reference('uranos_ts', 'email_template_error')[1]
                error_to_print = 'Followup : ' + str(ex) + ':' + str(vals)
                self.generate_and_send_email(error_to_print, template_id)

            import_count += 1
            nb_records_processed += 1
            if import_count >= MAX_LINES:
                if logs:
                    _logger.warning("Followups processed: %d, last PK_FollowUp = %d" %
                                    (nb_records_processed, follow_up['PK_FollowUp']))
                # print('followup:' + str(follow_up['PK_FollowUp']))
                self._cr.commit()
                import_count = 0

            follow_up = cursor.fetchone()

        if nb_records != nb_records_processed:
            print('There is a problem with the import, all Followup records have not been processed')
            # raise ValidationError(_('There is a problem with the import, all Billing records have not been processed'))

    @api.model
    def importFollowupAction(self, cursor, start_date, end_date, first_fua=None, last_fua=None, logs=False):
        import_count = 0
        nb_records_processed = 0

        sql_select_count = "Select Count(*) as nb_record"

        sql_select_columns = (
            "Select PK_FollowUpEvent, FollowUpID, ActionID, Action, Duration, Remaining "
        )

        sql_from = (
            " From R_MultiProvenanceFollowUp_MultiDestinationAction "
        )

        if first_fua is not None and last_fua is not None:
            sql_where = (" WHERE LastUpdateDate is null and PK_FollowUpEvent > %d and PK_FollowUpEvent <= %d" %
                         (first_fua, last_fua))
        elif start_date:
            sql_where = (" WHERE LastUpdateDate is not null and LastUpdateDate > '%s' and LastUpdateDate <= '%s'" %
                         (start_date, end_date))
        else:
            sql_where = (" WHERE (LastUpdateDate is null or LastUpdateDate <= '%s')" %
                         (end_date,))

        sql_order_by = " ORDER BY PK_FollowUpEvent, FollowUpID "

        cursor.execute(sql_select_count + sql_from + sql_where)
        nb_records = cursor.fetchone()['nb_record']
        if logs:
            _logger.warning("Nb fua = %d" % nb_records)

        cursor.execute(sql_select_columns + sql_from + sql_where + sql_order_by)
        action_followup = cursor.fetchone()

        while action_followup:
            followup_id = False
            action_id = False

            followup = self.env['uranos.followup'].search([('pk_followup', '=', action_followup['FollowUpID'])])
            if followup:
                followup_id = followup.id

            action = self.env['uranos.action'].search([('pk_action', '=', action_followup['ActionID'])])
            if action:
                action_id = action.id

            vals = {
                'pk_followup_event': action_followup['PK_FollowUpEvent'],
                'followup_id': followup_id,
                'action_id': action_id,
                'action_code': action_followup['Action'],
                'duration': action_followup['Duration'],
                'remaining': action_followup['Remaining']
            }

            uranos_followup_contact = self.env['uranos.followup.action'].search([
                ('pk_followup_event', '=', vals['pk_followup_event'])])

            try:
                if uranos_followup_contact:
                    uranos_followup_contact.write(vals)
                else:
                    uranos_followup_contact.create(vals)
            except Exception as ex:
                ir_model_data = self.env['ir.model.data']
                template_id = ir_model_data.get_object_reference('uranos_ts', 'email_template_error')[1]
                error_to_print = 'Folowup_action : ' + str(ex) + ':' + str(vals)
                self.generate_and_send_email(error_to_print, template_id)

            import_count += 1
            nb_records_processed += 1
            if import_count >= MAX_LINES or (first_fua is not None and last_fua is not None):
                if logs:
                    _logger.warning("Fuas processed: %d, last FollowUpID = %d" %
                                    (nb_records_processed, action_followup['FollowUpID']))
                # print('followup_Action:' + str(action_followup['FollowUpID']))
                self._cr.commit()
                import_count = 0

            action_followup = cursor.fetchone()

        if nb_records != nb_records_processed:
            print('There is a problem with the import, all FollowupAction records have not been processed')
            # raise ValidationError(_('There is a problem with the import, all Billing records have not been processed'))

    @api.model
    def importFollowupContact(self, cursor, start_date, end_date, logs=False):
        import_count = 0
        nb_records_processed = 0

        sql_select_count = "Select Count(*) as nb_record"

        sql_select_columns = (
            "Select FollowUpID, Employee_ContactID, Accepted, EventID, Sent "
        )

        sql_from = (
            " From R_MultiContact_FollowUp"
        )

        if start_date:
            sql_where = (" WHERE LastUpdateDate is not null and LastUpdateDate > '%s' and LastUpdateDate <= '%s'" %
                         (start_date, end_date))
        else:
            sql_where = (" WHERE (LastUpdateDate is null or LastUpdateDate <= '%s')" %
                         (end_date,))

        sql_order_by = " ORDER BY FollowUpID, Employee_ContactID "

        cursor.execute(sql_select_count + sql_from + sql_where)
        nb_records = cursor.fetchone()['nb_record']
        if logs:
            _logger.warning("Nb cfu = %d" % nb_records)

        cursor.execute(sql_select_columns + sql_from + sql_where + sql_order_by)
        contact_follow_up = cursor.fetchone()

        while contact_follow_up:
            followup_id = False
            partner_id = False
            event_id = False

            followup = self.env['uranos.followup'].search([('pk_followup', '=', contact_follow_up['FollowUpID'])])
            if followup:
                followup_id = followup.id

            contact = self.env['res.partner'].with_context(active_test=False).search([('pk_contact', '=', contact_follow_up['Employee_ContactID'])], limit=1)
            if contact:
                partner_id = contact.id

            event = self.env['uranos.event'].search([('pk_event', '=', contact_follow_up['EventID'])])
            if event:
                event_id = event.id

            vals = {'followup_id': followup_id,
                    'employee_contact_id': partner_id,
                    'accepted': contact_follow_up['Accepted'],
                    'event_id': event_id,
                    'sent': contact_follow_up['Sent']}

            uranos_followup_contact = self.env['uranos.followup.contact'].search([('followup_id', '=', followup_id),
                                                                                  ('employee_contact_id', '=', partner_id)])
            try:
                if uranos_followup_contact:
                    uranos_followup_contact.write(vals)
                else:
                    uranos_followup_contact.create(vals)
            except Exception as ex:
                ir_model_data = self.env['ir.model.data']
                template_id = ir_model_data.get_object_reference('uranos_ts', 'email_template_error')[1]
                error_to_print = 'FU Contact : ' + str(ex) + ':' + str(vals)
                self.generate_and_send_email(error_to_print, template_id)

            import_count += 1
            nb_records_processed += 1
            if import_count >= MAX_LINES:
                if logs:
                    _logger.warning("Fucontacts processed: %d, last FollowUpID = %d" %
                                    (nb_records_processed, contact_follow_up['FollowUpID']))
                # print('followup_Contact:' + str(contact_follow_up['FollowUpID']))
                self._cr.commit()
                import_count = 0

            contact_follow_up = cursor.fetchone()

        if nb_records != nb_records_processed:
            print('There is a problem with the import, all FollowupContact records have not been processed')
            # raise ValidationError(_('There is a problem with the import, all Billing records have not been processed'))

    @api.model
    def deleteFollowupContact(self, cursor):
        sql_select_columns = (
            "Select FollowUpID, Employee_ContactID, Accepted, EventID, Sent "
        )

        sql_from = (
            " From Z_MultiContact_FollowUp_Deleted"
        )

        sql_order_by = " ORDER BY FollowUpID, Employee_ContactID "

        cursor.execute(sql_select_columns + sql_from + sql_order_by)
        deleted_contact_follow_up = cursor.fetchone()

        while deleted_contact_follow_up:
            # Vérifier que le lien contact Followup n'a pas été recréé après le delete.
            sql_select_follow_up = ("Select FollowUpID, Employee_ContactID")
            sql_from_Follow_up = (" From R_MultiContact_FollowUp")
            sql_where_Follow_up = (" Where FollowUpID = %s and Employee_ContactID = %s" %
                                   (deleted_contact_follow_up['FollowUpID'], deleted_contact_follow_up['Employee_ContactID']))

            connection_kwargs = get_connection_kwargs(self)

            contact_follow_up = None
            if connection_kwargs:
                with pymssql.connect(**connection_kwargs) as conn:
                    cursor2 = conn.cursor()
                    cursor2.execute(sql_select_follow_up + sql_from_Follow_up + sql_where_Follow_up)
                    contact_follow_up = cursor2.fetchone()
                    cursor2.close()

            if not contact_follow_up:
                followup_id = False
                partner_id = False
                followup = self.env['uranos.followup'].search([('pk_followup', '=', deleted_contact_follow_up['FollowUpID'])])
                if followup:
                    followup_id = followup.id

                contact = self.env['res.partner'].with_context(active_test=False).search(
                    [('pk_contact', '=', deleted_contact_follow_up['Employee_ContactID'])])
                if contact:
                    partner_id = contact.id

                # sinon detruire le lien et l'entré dans l'historique
                odoo_contact_follow_up = self.env['uranos.followup.contact'].search([('followup_id', '=', followup_id),
                                                                                     ('employee_contact_id', '=', partner_id)])

                for odoo_cfu in odoo_contact_follow_up:
                    odoo_cfu.unlink()
                followup._calculate_employee()

            sql_delete = ("Delete From Z_MultiContact_FollowUp_Deleted")

            if connection_kwargs:
                # try:
                with pymssql.connect(**connection_kwargs) as conn2:
                    cursor3 = conn2.cursor()
                    cursor3.execute(sql_delete + sql_where_Follow_up)
                    conn2.commit()

            self._cr.commit()
            deleted_contact_follow_up = cursor.fetchone()

    @api.model
    def importAction(self, cursor, start_date, end_date, logs=False):
        import_count = 0
        nb_records_processed = 0

        sql_select_count = "Select Count(*) as nb_record"

        sql_select_columns = (
            "SELECT Pk_Action, EventID, RequestID, BillingID, Name, SUBSTRING(Description, 1, 2000) as Description, "
            "       SUBSTRING(InternalComment, 1, 2000) AS InternalComment, DetailAction, "
            "       Case Status when 1 then 'Closed' when 2 then 'Supervised' when 3 then 'Corrected' when 4 then 'Billed' else 'Open' End as Status,"
            "       Case State when 0  then 'Active' when 1 then 'Canceled' End as State"
        )

        sql_from = " From Action"

        if start_date:
            sql_where = (" WHERE LastUpdateDate is not null and LastUpdateDate > '%s' and LastUpdateDate <= '%s'" %
                         (start_date, end_date))
        else:
            sql_where = (" WHERE (LastUpdateDate is null or LastUpdateDate <= '%s')" %
                         (end_date,))

        sql_order_by = " ORDER BY Pk_Action "

        cursor.execute(sql_select_count + sql_from + sql_where)
        nb_records = cursor.fetchone()['nb_record']
        if logs:
            _logger.warning("Nb Action = %d" % nb_records)
            # _logger.warning(sql_select_columns + sql_from + sql_where + sql_order_by)

        cursor.execute(sql_select_columns + sql_from + sql_where + sql_order_by)
        action = cursor.fetchone()

        while action:
            event_id = False
            request_id = False
            billing_id = False

            event = self.env['uranos.event'].search([('pk_event', '=', action['EventID'])])
            if event:
                event_id = event.id

            request = self.env['uranos.request'].search([('pk_request', '=', action['RequestID'])])
            if request:
                request_id = request.id

            billing = self.env['uranos.billing'].search([('pk_billing', '=', action['BillingID'])])
            if billing:
                billing_id = billing.id

            vals = {'pk_action': action['Pk_Action'],
                    'event_id': event_id,
                    'request_id': request_id,
                    'billing_id': billing_id,
                    'name': action['Name'],
                    'description': action['Description'],
                    'internal_comment': action['InternalComment'],
                    'status': action['Status'],
                    'state': action['State']}

            uranos_action = self.env['uranos.action'].search([['pk_action', '=', action['Pk_Action']]])

            # if logs:
            #     _logger.warning(vals)
            try:
                if uranos_action:
                    uranos_action.write(vals)
                else:
                    uranos_action.create(vals)
            except Exception as ex:
                ir_model_data = self.env['ir.model.data']
                template_id = ir_model_data.get_object_reference('uranos_ts', 'email_template_error')[1]
                error_to_print = 'Action : ' + str(ex) + ':' + str(vals)
                self.generate_and_send_email(error_to_print, template_id)

            import_count += 1
            nb_records_processed += 1
            if import_count >= MAX_LINES:
                if logs:
                    _logger.warning("Pk_Actions processed: %d, last Pk_Action = %d" %
                                    (nb_records_processed, action['Pk_Action']))
                # print('action:' + str(action['Pk_Action']))
                self._cr.commit()
                import_count = 0

            action = cursor.fetchone()
            # if logs:
            #     _logger.warning(action)

        if nb_records != nb_records_processed:
            print('There is a problem with the import, all Action records have not been processed')
            # raise ValidationError(_('There is a problem with the import, all Action records have not been processed'))

    @api.model
    def fixBillingAction(self):
        # Fix probleme with cost time.
        actions = self.env['uranos.action'].search([])

        for action in actions:
           action._calculate_date_start_event()  # TODO:MIGRATION: doesn't exist
           # action._calculate_billing_time_reel()
           # action._calculate_cost_bm()

    @api.model
    def importInitialFuAction(self):
        last_fua = self.env['uranos.followup.action'].search([], limit=1, order='pk_followup_event desc')
        first_fua = last_fua.pk_followup_event or 0

        connection_kwargs = get_connection_kwargs(self)
        if connection_kwargs:
            # try:
            with pymssql.connect(**connection_kwargs) as conn:
                cursor = conn.cursor()

                for _i in range(100):
                    last_fua = first_fua + 100
                    self.importFollowupAction(cursor, None, None, first_fua=first_fua, last_fua=last_fua)
                    first_fua = last_fua

    def link_project_task_to_uranos_request(self):
        task_not_linked = self.env['project.task'].search([
            ('request_pk', '!=', False),
            ('uranos_request_id', '=', False)])

        for task in task_not_linked:
            request = self.env['uranos.request'].search([('pk_request', '=', task.request_pk)])
            if request:
                task.uranos_request_id = request

    @api.model
    def importUranosData(self, hours=0, days=1, logs=False):
        # these variables are for update the colors in the case of the second is because I need the partner_id in the
        # billing, so I need to taking it in the event
        dirty_billings = self.env['uranos.billing']
        dirty_set = set()
        last_imports = self.env['uranos.import'].search([('import_batch', '=', False)], limit=1, order='id desc')
        if last_imports.last_pk_billing:
            start_date = last_imports.import_start_date
            end_date = last_imports.import_end_date
            last_pk_billing = last_imports.last_pk_billing
        else:
            start_date = last_imports.import_end_date if last_imports else None
            last_pk_billing = False
        if logs:
            _logger.warning("last import: %s", start_date)

        connection_kwargs = get_connection_kwargs(self)

        if connection_kwargs:
            try:
                with pymssql.connect(**connection_kwargs) as conn:
                    cursor = conn.cursor()

                    # S'il y a un last_pk_billing, c'est que l'import des billings n'était pas terminé. (Il y en avait trop)
                    # Donc, on garde les même start_date et end_date, on skip importRequest et importEvent et
                    # on continu l'import des billings.
                    if last_pk_billing:
                        small_step_date = end_date
                    else:
                        cursor.execute("SELECT CURRENT_TIMESTAMP as CurrentDate")
                        end_date = cursor.fetchone()['CurrentDate'].replace(microsecond=0)

                        if start_date:
                            small_step_date = start_date + timedelta(hours=hours, days=days)
                            if small_step_date < end_date:
                                end_date = small_step_date
                                if logs:
                                    _logger.warning("importing max days until %s", end_date)

                        self.importRequest(cursor, start_date, end_date, logs=logs)
                        if logs:
                            _logger.warning("End Request")
                        dirty_set = self.importEvent(cursor, start_date, end_date, logs=logs)
                        if logs:
                            _logger.warning("End Event")

                    dirty_billings, pk_billing = self.importBilling(cursor, start_date, end_date, last_pk_billing, logs=logs)
                    # S'il y a un pk_billing, c'est que l'import des billings n'était pas terminé. (Il y en avait trop)
                    # Donc on saute les dernièrs imports afin de faire le commit et de reprendre le processus.
                    if not pk_billing:
                        if logs:
                            _logger.warning("End Billing")

                        self.importAction(cursor, start_date, end_date, logs=logs)
                        if logs:
                            _logger.warning("End Action")
                        self.importFollowup(cursor, start_date, end_date, logs=logs)
                        if logs:
                            _logger.warning("End FollowUp")
                        self.importFollowupAction(cursor, start_date, end_date, logs=logs)
                        if logs:
                            _logger.warning("End FU Action")
                        self.importFollowupContact(cursor, start_date, end_date, logs=logs)
                        if logs:
                            _logger.warning("End FU Contact")
                        self.link_project_task_to_uranos_request()
                        if logs:
                            _logger.warning("End Link Project Task")
                        if end_date != small_step_date:
                            self.deleteFollowupContact(cursor)

                    self.env['uranos.import'].create({'import_start_date': start_date,
                                                      'import_end_date': end_date,
                                                      'last_pk_billing': pk_billing})

            except Exception as ex:
                _logger.error(ex)

            # update colors
            # I create a set and storage the partner_id and value of the date in order
            # to make the for only once
            for billing in dirty_billings:
                for action in self.env['uranos.action'].search([('billing_id', '=', billing.id)]):
                    date = action.date_start_event
                    partner = action.employee_partner_id
                    dirty_set.add((partner.id, date))

            for partner_id, date in dirty_set:
                records = self.env['uranos.action'].search([
                    ('date_start_event', '=', date),
                    ('employee_partner_id', '=', partner_id)])
                records.analyze_one_day()

    @api.model
    def importUranosBatchData(self, hours=0, days=1, logs=False):
        last_imports = self.env['uranos.import'].search([('import_batch', '=', True)], limit=1, order='id desc')
        start_date = last_imports.import_end_date if last_imports else None
        if logs:
            _logger.warning("last import: %s", start_date)

        connection_kwargs = get_connection_kwargs(self)

        if connection_kwargs:
            try:
                with pymssql.connect(**connection_kwargs) as conn:
                    cursor = conn.cursor()

                    cursor.execute("SELECT CURRENT_TIMESTAMP as CurrentDate")
                    end_date = cursor.fetchone()['CurrentDate'].replace(microsecond=0)

                    if start_date:
                        small_step_date = fields.Datetime.from_string(start_date) + timedelta(hours=hours,
                                                                                              days=days)
                        if small_step_date < end_date:
                            end_date = small_step_date
                            if logs:
                                _logger.warning("importing max days until %s", end_date)

                    self.importBilling(cursor, start_date, end_date, False, logs=logs, batch_update=True)
                    if logs:
                        _logger.warning("End Billing")

                    self.env['uranos.import'].create({'import_start_date': start_date,
                                                      'import_end_date': end_date,
                                                      'import_batch': True})

            except Exception as ex:
                _logger.error(ex)


class UranosRequest(models.Model):
    _name = "uranos.request"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Uranos Request"
    _order = "partner_id, name"

    pk_request = fields.Integer(string='Pk_Request', index=True, readonly=True, group_operator=None)
    partner_id = fields.Many2one('res.partner', string='customer', readonly=True)
    type_priority = fields.Char(string='Priority', readonly=True)
    type_risk = fields.Char(string='Risk', readonly=True)
    status = fields.Char(string='Status', readonly=True)
    name = fields.Char(string='Name', readonly=True)
    description = fields.Text(string='Description', readonly=True)
    internal_comment = fields.Text(string='Internal Comment', readonly=True)
    correction = fields.Integer('Correction')
    followup_ids = fields.One2many('uranos.followup', 'request_id', string='Follow up')
    action_ids = fields.One2many('uranos.action', 'request_id', string='Actions')
    task_id = fields.One2many('project.task', 'uranos_request_id', string='Task')
    project_id = fields.Many2one(related='task_id.project_id', store=True)
    project_category_id = fields.Many2one(related='task_id.project_id.project_category_id', store=True)
    client_category_id = fields.Many2one(related='partner_id.client_category_id', store=True)
    project_ts = fields.Integer(string='Project ID', readonly=True, group_operator=None)
    project_name = fields.Char(string='Project Name', readonly=True)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('pk_request', operator, name)]
        pos = self.search(domain + args, limit=limit)
        return pos.name_get()


class UranosEvent(models.Model):
    _name = "uranos.event"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Uranos Event"
    _order = "date_start_event, time_start_event, time_end_event desc"

    pk_event = fields.Integer(string='Pk_Event', index=True, readonly=True)
    employee_partner_id = fields.Many2one('res.partner', string='Employee', readonly=True)
    customer_partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    date_start_event = fields.Date('Date Start')
    date_end_event = fields.Date('Date End')
    time_start_event = fields.Integer(string='Start Time', readonly=True)
    time_end_event = fields.Integer(string='End Time', readonly=True)
    adjust_time = fields.Integer(string='Adjust Time', readonly=True)
    adjust_reason = fields.Char(string='Adjust reason', readonly=True)
    state = fields.Char(string='Status', readonly=True)
    payment_method = fields.Integer(string='Payment method', readonly=True)


class UranosBilling(models.Model):
    _name = "uranos.billing"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Uranos Billing"
    _order = "pk_billing"

    pk_billing = fields.Integer(string='Pk_billing', index=True, readonly=True)
    billing_type = fields.Char(string='Type', readonly=True)
    pay_rate_work = fields.Float('Pay Rate Work', groups='uranos_ts.group_uranos_ts_admin')
    billing_rate = fields.Float(string='Billing Rate', readonly=True, groups='uranos_ts.group_uranos_ts_admin')
    billing_time = fields.Integer(string='Billing Time', readonly=True)
    factor_bill_rate = fields.Float(string='FactorBillRate', readonly=True)
    factor_pay_rate = fields.Float(string='FactorPayRate', readonly=True)
    invoice_num = fields.Char(string='Invoice Number', readonly=True)
    statement_id = fields.Char(string='Statement', readonly=True)
    billing_time_reel = fields.Integer(string='Billing Time Reel', readonly=True)
    invoice_date = fields.Date('Invoice Date', readonly=True)
    rounding_sales = fields.Float('Rounding sale', readonly=True, groups='uranos_ts.group_uranos_ts_admin')
    rounding_pay = fields.Float('Rounding pay', readonly=True, groups='uranos_ts.group_uranos_ts_admin')
    work_type = fields.Integer(string='Type Work', readonly=True)
    work_name = fields.Char(string='Work name', readonly=True)
    rate_name = fields.Char(string='Rate name', readonly=True)


class UranosAction(models.Model):
    _name = "uranos.action"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Uranos Work"
    _order = "event_id, request_id"

    BENIFIT_RATE = 1.5

    pk_action = fields.Integer(string='Pk_Action', index=True, readonly=True, group_operator=None)
    event_id = fields.Many2one('uranos.event', string='Event', readonly=True, group_operator=None)
    request_id = fields.Many2one('uranos.request', string='Request', readonly=True, group_operator=None)
    billing_id = fields.Many2one('uranos.billing', string='Billing', readonly=True, group_operator=None)
    name = fields.Char(string='Action Name', readonly=True)
    description = fields.Text(string='Action Description', readonly=True)
    internal_comment = fields.Text(string='Internal Comment', readonly=True)
    detail_action = fields.Char(string='Detail Action', readonly=True)
    # those 2 should be Selection()
    status = fields.Char(string='Status', readonly=True, help='Open/Closed/Supervised/Corrected/Billed')
    state = fields.Char(string='State', readonly=True, help="Active/Cancelled")
    task_id = fields.Many2one('project.task', string='Task', compute='_compute_task_id')
    project_id = fields.Many2one(related='request_id.project_id', store=True)
    # Those two are for add new filters and group by
    project_category_id = fields.Many2one(related='request_id.project_category_id', store=True)
    client_category_id = fields.Many2one(related='request_id.client_category_id', store=True)
    customer_partner_id = fields.Many2one('res.partner', 'Customer',
                                          readonly=True, related='request_id.partner_id', store=True)
    customer_ref = fields.Char('Code Customer', readonly=True, related='customer_partner_id.ref', store=True)
    pk_request = fields.Integer('Pk_Request', readonly=True, related='request_id.pk_request', store=True, group_operator=None)
    request_name = fields.Char('Request Name', readonly=True, related='request_id.name')
    request_description = fields.Text('Request Description', readonly=True, related='request_id.description')
    request_internal_comment = fields.Text('Request Internal Comment', readonly=True, related='request_id.internal_comment')
    request_status = fields.Char('Request Status', readonly=True, related='request_id.status')
    employee_partner_id = fields.Many2one(readonly=True, related='event_id.employee_partner_id', store=True)
    employee_department_id = fields.Many2one(readonly=True, related='employee_partner_id.department_id', store=True)
    employee_ref = fields.Char('Code Employee', readonly=True, related='employee_partner_id.ref', store=True)
    pk_event = fields.Integer('Pk_Event', readonly=True, related='event_id.pk_event')
    date_start_event = fields.Date('Start Date', readonly=True, related='event_id.date_start_event', store=True)
    time_start_event = fields.Char('Start Time', readonly=True, compute='_calculate_time_start_event')
    time_end_event = fields.Char('End Time', readonly=True, compute='_calculate_time_end_event')
    date_time_start_event = fields.Datetime('Start Date time', compute='_calculate_date_time_start_event', store=True)
    date_time_end_event = fields.Datetime('End Date time', compute='_calculate_date_time_end_event', store=True)
    fiscal_year = fields.Char('Fiscal Year', compute='_compute_fiscal_period', store=True)
    fiscal_quarter = fields.Char('Fiscal Quarter', compute='_compute_fiscal_period', store=True)
    billing_time_reel = fields.Float('Sale Hours', readonly=True, compute='_calculate_billing_time_reel', store=True)
    billing_rate = fields.Float(
        'Sale Rate', readonly=True, related='billing_id.billing_rate', store=True, group_operator="avg",
        groups='uranos_ts.group_uranos_ts_admin')
    billing_amount = fields.Float(
        'Sale $', readonly=True, compute='_calculate_billing_time_reel', store=True,
        groups='uranos_ts.group_uranos_ts_admin')
    billing_type = fields.Char('CF', readonly=True, related='billing_id.billing_type', store=True)
    billing_time = fields.Float('Cost Hours', readonly=True, compute='_calculate_billing_time', store=True)
    pay_rate_work = fields.Float('Cost Rate', readonly=True, related='billing_id.pay_rate_work', store=True,
                                 group_operator="avg", groups='uranos_ts.group_uranos_ts_admin')
    billing_cost = fields.Float('Cost $', readonly=True, compute='_calculate_billing_time', store=True,
                                groups='uranos_ts.group_uranos_ts_admin')
    billing_cost_bm = fields.Float('Cost+BM $', readonly=True, compute='_calculate_cost_bm', store=True,
                                   groups='uranos_ts.group_uranos_ts_admin')
    statement_id = fields.Char('Statement', readonly=True, related='billing_id.statement_id', store=True)
    work_name = fields.Char('Work Type Name', readonly=True, related='billing_id.work_name', store=True)
    rate_name = fields.Char('Rate Type Name', readonly=True, related='billing_id.rate_name')
    followup_ids = fields.One2many(string='Follow up', readonly=True, related='request_id.followup_ids')
    followup_action_ids = fields.One2many('uranos.followup.action', 'action_id', string='Actions', readonly=True)
    request_action_ids = fields.One2many(string='Request Actions', readonly=True, related='request_id.action_ids')
    profit = fields.Float('Profit', readonly=True, compute='_calculate_profit', store=True, groups='uranos_ts.group_uranos_ts_admin')
    total = fields.Char('Total', default='Total')

    # overlap color
    overlap = fields.Selection([
        ('single', 'Singleton'),
        ('full', 'Full'),
        ('overflow', 'Excess'),
        ('underflow', 'Short'),
        ('weft', 'Interrupted')
    ], string='Overlap')
    overlap_minute = fields.Float('Overlap Minutes')
    error_flag = fields.Selection([
        ('ok', 'Ok'),
        ('error', 'Error'),
        ('wrong_customer', 'Wrong customer'),
        ('wrong_request', 'Wrong request'),
        ('wrong_code', 'Wrong Billing Code'),
    ], default='ok')

    @api.depends('request_id')
    def _compute_task_id(self):
        for record in self:
            record.task_id = record.request_id.task_id

    @api.depends('event_id.time_start_event')
    def _calculate_time_start_event(self):
        for record in self:
            record.time_start_event = minutes_to_time(record.event_id.time_start_event)

    @api.depends('event_id.time_end_event')
    def _calculate_time_end_event(self):
        for record in self:
            record.time_end_event = minutes_to_time(record.event_id.time_end_event)

    @api.depends('event_id.time_start_event', 'event_id.date_start_event')
    def _calculate_date_time_start_event(self):
        for record in self:
            if record.event_id.date_start_event:
                date_start = fields.Datetime.from_string(record.event_id.date_start_event)
                date_start = date_start + timedelta(minutes=record.event_id.time_start_event or 0)
                user_tz = pytz.timezone(self.env.user.tz)
                record.date_time_start_event = tz_to_utc_naive_datetime(user_tz, date_start)
            else:
                record.date_time_start_event = False

    @api.depends('event_id.time_end_event', 'event_id.date_start_event')
    def _calculate_date_time_end_event(self):
        for record in self:
            if record.event_id.date_start_event:
                date_end = fields.Datetime.from_string(record.event_id.date_start_event)
                date_end = date_end + timedelta(minutes=record.event_id.time_end_event or 0)
                user_tz = pytz.timezone(self.env.user.tz)
                record.date_time_end_event = tz_to_utc_naive_datetime(user_tz, date_end)
            else:
                record.date_time_end_event = False

    @api.depends('date_start_event')
    def _compute_fiscal_period(self):
        for record in self:
            if record.event_id.date_start_event:
                start_date = record.event_id.date_start_event
                year = start_date.year
                month = start_date.month
                # avril is the last month of the fiscal year
                if month > 4:
                    year += 1
                record.fiscal_year = 'AVR {}'.format(year)
                record.fiscal_quarter = 'T{} AVR {}'.format((month + 2) // 3, year)

    @api.depends('billing_id.billing_time_reel', 'billing_id.billing_rate')
    def _calculate_billing_time_reel(self):
        for record in self:
            record.billing_time_reel = round((record.billing_id.billing_time_reel / 60) + 0.0000001, 2)
            record.billing_amount = round((record.billing_id.billing_time_reel / 60 * record.billing_rate) + 0.0000001, 2)

    @api.depends('billing_id.billing_time', 'billing_id.pay_rate_work')
    def _calculate_billing_time(self):
        for record in self:
            record.billing_time = round((record.billing_id.billing_time / 60) + 0.0000001, 2)
            record.billing_cost = round((record.billing_id.billing_time / 60 * record.pay_rate_work) + 0.0000001, 2)

    @api.depends('billing_id.billing_time', 'billing_id.pay_rate_work', 'billing_id.factor_pay_rate',
                 'billing_id.work_type', 'event_id.payment_method')
    def _calculate_cost_bm(self):
        for record in self:
            if record.billing_id.pay_rate_work and record.billing_id.billing_time:
                if record.event_id.payment_method != 2 and record.billing_id.work_type in (1, 2, 3):
                    record.billing_cost_bm = round((round((record.billing_id.billing_time/60 *
                                                           record.billing_id.pay_rate_work) + 0.0000001, 2) *
                                                    record.BENIFIT_RATE * record.billing_id.factor_pay_rate) + 0.0000001, 2)
                else:
                    record.billing_cost_bm = round((round((record.billing_id.billing_time / 60 *
                                                           record.billing_id.pay_rate_work) + 0.0000001, 2) *
                                                    record.billing_id.factor_pay_rate) + 0.0000001, 2)
            else:
                record.billing_cost_bm = 0

    @api.depends('billing_cost_bm', 'billing_amount')
    def _calculate_profit(self):
        for record in self:
            record.profit = record.billing_amount - record.billing_cost_bm

    def action_analyze_timesheet(self):
        self.sudo().analyze_many_days()

    def analyse_timesheet_to_supervise(self):
        uranos_action_ids = self.search([('status', 'in', ('Open', 'Close'))])
        uranos_action_ids.sudo().analyze_many_days()

    def action_supervise_timesheet(self):
        if self.filtered(lambda a: a.status == 'Open'):
            raise UserError(_("Some works are open, you cannot supervise open works."))
        if self.filtered(lambda a: a.status != 'Closed'):
            raise UserError(_("Some works are already supervised, you cannot supervise them."))

        self.supervise_works()

    def button_supervise_timesheet(self):
        self.supervise_works()

    def supervise_works(self):
        connection_kwargs = get_connection_kwargs(self)
        if connection_kwargs:
            try:
                with pymssql.connect(**connection_kwargs) as conn:
                    cursor = conn.cursor()
                    for action in self:
                        action.supervise_work(cursor)
                    conn.commit()
            except Exception as ex:
                raise UserError(ex)

    def supervise_work(self, cursor):
        cursor.execute("Exec SuperviseEvent %s", self.pk_event)
        self.sudo().write({
            'status': 'Supervised'
        })

    def button_close_timesheet(self):
        self.close_works()

    def close_works(self, unlinked_pk_action=[]):
        connection_kwargs = get_connection_kwargs(self)
        if connection_kwargs:
            try:
                with pymssql.connect(**connection_kwargs) as conn:
                    cursor = conn.cursor()
                    for action in self:
                        action.close_work(cursor)
                    for pk_action in unlinked_pk_action:
                        cursor.execute("""declare @EventID int
                                          set @EventID = (Select eventID from action where pk_action = %s)
                                          Exec CloseEvent  @EventID""", pk_action)
                    conn.commit()
            except Exception as ex:
                raise UserError(ex)

    def close_work(self, cursor):
        cursor.execute("Exec CloseEvent %s", self.pk_event)
        self.sudo().write({
            'status': 'Closed'
        })

    def button_open_timesheet(self):
        self.open_works()

    def open_works(self):
        connection_kwargs = get_connection_kwargs(self)
        if connection_kwargs:
            try:
                with pymssql.connect(**connection_kwargs) as conn:
                    cursor = conn.cursor()
                    for action in self:
                        action.open_work(cursor)
                    conn.commit()
            except Exception as ex:
                raise UserError(ex)

    def open_work(self, cursor):
        cursor.execute("Exec OpenEvent %s", self.pk_event)
        self.sudo().write({
            'status': 'Open'
        })

    def analyze_many_days(self):
        """ divide recordset into separate processing groups
        """
        # process each date/employee separately
        # will fail if work overlaps midnight
        batch_set = set(self.mapped(lambda x: (x.date_start_event, x.employee_partner_id)))
        while batch_set:
            date_start_event, employee_partner_id = batch_set.pop()
            records = self.search([
                ('date_start_event', '=', date_start_event),
                ('employee_partner_id', '=', employee_partner_id.id)])
            records.analyze_one_day()

    def block_iterate(self):
        """ iterate over blocks of overlapping entries
        accumulate overlapping entries in a single recordset
        and release it when next entry is separate
        """
        date_time_end_event = None
        block_records = None
        # TODO check sorted
        active_records = self.filtered(
            lambda x: x.date_time_start_event and x.date_time_end_event and x.billing_id.billing_time)
        for record in active_records:
            if not block_records:
                # once on loop entry
                date_time_end_event = record.date_time_end_event
                block_records = record
            elif record.date_time_start_event < date_time_end_event:
                # overlap, extend current block
                date_time_end_event = max(date_time_end_event, record.date_time_end_event)
                block_records += record
            else:
                # separate, release held block and start a new one
                yield block_records
                date_time_end_event = record.date_time_end_event
                block_records = record
        if block_records:
            # always true unless filtered is empty
            yield block_records

    def start_end_iterate(self):
        """ iterate over entries, returning the next start/end to occur
        yields:
            :param active_records: entries in current timeslice
            :param next_record: entry being added/removed from actives
            :param next_datetime: end of next timeslice
            :param previous_datetime: end of current timeslice
            :param when: which end of the next_record we are processing

        """
        start_records = self.sorted('date_time_start_event')
        end_records = self.sorted('date_time_end_event')
        active_records = self.env['uranos.action']
        # !! Odoo datetime are strings, not python datetime
        previous_datetime = fields.Datetime.from_string(start_records[0].date_time_start_event)
        # start_records will be empty when we exit this loop
        # because time_constrains() method forces date_time_end_event > date_time_start_event
        while end_records:
            # records are sorted, only check the first one of each recordset
            # once all start times have been consumed, there is only end times left
            if start_records and start_records[0].date_time_start_event < end_records[0].date_time_end_event:
                next_record = start_records[0]
                #
                next_datetime = fields.Datetime.from_string(next_record.date_time_start_event)
                start_records -= next_record
                yield active_records, next_record, next_datetime, previous_datetime, 'start_date'
                active_records += next_record
                previous_datetime = next_datetime
            else:
                next_record = end_records[0]
                next_datetime = fields.Datetime.from_string(next_record.date_time_end_event)
                end_records -= next_record
                yield active_records, next_record, next_datetime, previous_datetime, 'end_date'
                active_records -= next_record
                previous_datetime = next_datetime

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

        def date_to_minute(next_datetime, previous_datetime):
            # first test is datetime, next tests are str
            if type(next_datetime) == str:
                next_datetime = fields.Datetime.from_string(next_datetime)
            if type(previous_datetime) == str:
                previous_datetime = fields.Datetime.from_string(previous_datetime)
            return int((next_datetime - previous_datetime).total_seconds() / 60)

        def amount_to_minute(billing_time):
            # return round(billing_time * 60)
            return billing_time

        # records are considered "bottles" containing an amount of liquid time
        # bottles may be partially filled (1 hour assigned out of a 2 hour event)
        # records start/end divide the block into timeslices
        # we fill each timeslice from early to last using those bottles
        # we first empty the first-to-end because we want to empty a bottle before its last timeslice
        # empty bottle can go negative with non-existent time to inform user of missing amount
        #
        # ignore incomplete records
        valid_records = self.filtered(
            lambda x: x.date_time_start_event and x.date_time_end_event and x.billing_id.billing_time)
        for records in valid_records.sorted('date_time_start_event').block_iterate():
            if len(records) == 1:
                records.overlap_minute = 0
                records.overlap = 'single'
                continue
            # process is done with exact minutes
            duration_left_dict = {record: amount_to_minute(record.billing_id.billing_time) for record in records}
            for active_records, next_record, next_datetime, previous_datetime, when in records.start_end_iterate():
                # timedelta is converted to minutes
                time_to_distribute = date_to_minute(next_datetime, previous_datetime)
                if time_to_distribute == 0:
                    if when == 'end_date':
                        annotate_record(next_record, duration_left_dict[next_record])
                    continue
                active_records = active_records.sorted('date_time_end_event')
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
                        allowed_time = date_to_minute(record.date_time_end_event, record.date_time_start_event)
                        allowed_time -= amount_to_minute(record.billing_id.billing_time)
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

    def button_mark_error(self):
        self.ensure_one()
        # Todo Pop screen to select flag.
        if self.error_flag == 'ok':
            flag = 'error'
        else:
            flag = 'ok'
        self.sudo().write({
            'error_flag': flag
        })

    def button_unmark_error(self):
        self.button_mark_error()

    @api.model
    def _patch_fix_event_start_end_time(self, from_date='2023-04-28'):
        actions = self.env['uranos.action'].search([('create_date', '>=', from_date)])
        actions._calculate_date_time_start_event()
        actions._calculate_date_time_end_event()


class UranosFollowup(models.Model):
    _name = "uranos.followup"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Uranos Followup"
    _order = "date_due, time_due"

    pk_followup = fields.Integer(string='Pk_FollowUp', index=True, readonly=True, group_operator=None)
    action_id = fields.Many2one('uranos.action', string='Action', readonly=True, group_operator=None)
    name = fields.Char(string='Follow Up Name', readonly=True)
    description = fields.Text(string='Follow Up Description', readonly=True)
    internal_comment = fields.Text(string='Follow Up Internal Comment', readonly=True)
    date_due = fields.Date('Date Due', readonly=True)
    time_due = fields.Integer('Time Due (tech)', readonly=True)
    time_due_str = fields.Char('Time Due', readonly=True, compute='_calculate_time_due', store=True)
    duration_max = fields.Integer(readonly=True)
    duration_max_str = fields.Char('Budget', readonly=True, compute='_calculate_duration_max', store=True)
    status = fields.Char('Status', readonly=True)
    request_id = fields.Many2one('uranos.request', string='Request', readonly=True, group_operator=None)
    task_id = fields.Many2one('project.task', string='Task', compute='_compute_task_id')
    default_billing = fields.Char('Code', readonly=True)
    budget_min = fields.Integer('Min (tech)', readonly=True)
    budget_min_float = fields.Float('Min', compute='_calculate_budget_min')  # TODO:MIGRATION
    budget_max = fields.Integer('Max (tech)', readonly=True)
    budget_max_float = fields.Float('Max', readonly=True, compute='_calculate_budget_max')  # TODO:MIGRATION
    budget_billing = fields.Char('Valid', readonly=True)
    default_work = fields.Char('Default Work', readonly=True)
    default_rate = fields.Char('Default Rate', readonly=True)
    budget_work = fields.Char('Budget Work', readonly=True)
    budget_rate = fields.Char('Budget Rate', readonly=True)
    followup_contact_ids = fields.One2many('uranos.followup.contact', 'followup_id', string='Followup Employees', readonly=True)
    followup_action_ids = fields.One2many('uranos.followup.action', 'followup_id', string='Actions', readonly=True)
    employee_str = fields.Char('Employee', compute='_calculate_employee', readonly=True, store=True)
    customer_partner_id = fields.Many2one('res.partner', 'Customer',
                                          readonly=True, related='request_id.partner_id', store=True)
    request_pk = fields.Integer('Pk request', readonly=True, related='request_id.pk_request')
    request_name = fields.Char('Request Name', readonly=True, related='request_id.name')
    request_description = fields.Text('Request Description', readonly=True, related='request_id.description')
    request_internal_comment = fields.Text('Request Internal Comment', readonly=True,
                                           related='request_id.internal_comment')
    request_status = fields.Char('Request Status', readonly=True, related='request_id.status')
    action_ids = fields.One2many(string='Uranos Actions', readonly=True, related='request_id.action_ids')
    color = fields.Integer('Late', compute='_calculate_color')
    actual_duration = fields.Integer('Total Duration', compute='_compute_actual_duration', store=True)
    actual_duration_float = fields.Float('Total', compute='_compute_actual_duration_float', store=True)
    employe_ids = fields.One2many('res.partner', compute='_compute_employe_ids', search='_search_employe_ids')
    type_priority = fields.Char(related='request_id.type_priority', store=True)

    @api.depends('request_id')
    def _compute_task_id(self):
        for record in self:
            record.task_id = record.request_id.task_id

    @api.depends('followup_contact_ids')
    def _compute_employe_ids(self):
        for record in self:
            record.employe_ids = record.followup_contact_ids.mapped('employee_contact_id')

    def _search_employe_ids(self, operator, value):
        fu_contacts = self.env['uranos.followup.contact'].sudo().search(
            [('employee_contact_id', operator, value)])
        return [('id', 'in', fu_contacts.mapped('followup_id').ids)]

    @api.depends('time_due')
    def _calculate_time_due(self):
        for record in self:
            record.time_due_str = minutes_to_time(record.time_due)

    @api.depends('duration_max')
    def _calculate_duration_max(self):
        for record in self:
            record.duration_max_str = minutes_to_time(record.duration_max, separator='h')

    @api.depends('budget_min')
    def _calculate_budget_min(self):
        # TODO:MIGRATION
        for record in self:
            record.budget_min_float = float(record.budget_min)

    @api.depends('budget_max')
    def _calculate_budget_max(self):
        # TODO:MIGRATION
        for record in self:
            record.budget_max_float = float(record.budget_max)

    @api.depends('followup_contact_ids', 'followup_contact_ids.employee_contact_id')
    def _calculate_employee(self):
        for record in self:
            record.employee_str = ', '.join(
                [(fu_contact.employee_contact_id.ref or '?') for fu_contact in record.followup_contact_ids])

    def _calculate_color(self):
        user_tz = self.env.user.tz or pytz.utc
        now_local = datetime.now(pytz.timezone(user_tz))
        current_date = now_local.date()
        current_time = now_local.hour * 60 + now_local.minute
        for follow_up in self:
            if follow_up.status == 'Open':
                if follow_up.date_due > current_date:
                    # Green
                    follow_up.color = 10
                elif follow_up.date_due == current_date and follow_up.time_due >= current_time:
                    # Orange/Yellow
                    follow_up.color = 3
                else:
                    # Red
                    follow_up.color = 1
            else:
                follow_up.color = 0

    @api.depends('followup_action_ids.actual_duration')
    def _compute_actual_duration(self):
        for record in self:
            record.actual_duration = sum(record.followup_action_ids.mapped('actual_duration'))

    @api.depends('actual_duration')
    def _compute_actual_duration_float(self):
        for record in self:
            record.actual_duration_float = record.actual_duration / 60.0


class UranosFollowupContact(models.Model):
    _name = "uranos.followup.contact"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Uranos Followup Contact"
    _order = "followup_id"

    followup_id = fields.Many2one('uranos.followup', string='FollowUp', index=True, readonly=True)
    employee_contact_id = fields.Many2one('res.partner', string='Employee', index=True, readonly=True)
    accepted = fields.Integer('Accepted', readonly=True)
    event_id = fields.Many2one('uranos.event', string='Event', readonly=True)
    sent = fields.Boolean('Sent', readonly=True)


class UranosFollowupAction(models.Model):
    _name = "uranos.followup.action"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Uranos Followup Action"
    _order = "followup_id,action_id"

    pk_followup_event = fields.Integer(string='Pk_FollowupEvent', index=True, readonly=True, group_operator=None)
    followup_id = fields.Many2one('uranos.followup', string='Followup', index=True, readonly=True)
    action_id = fields.Many2one('uranos.action', string='Action', readonly=True, group_operator=None)
    action_code = fields.Char('Action Code', readonly=True)
    duration = fields.Integer('Duration', readonly=True)
    remaining = fields.Integer('Remaining', readonly=True)
    actual_duration = fields.Integer('Total', compute='_compute_actual_duration', store=True)

    @api.depends('duration', 'action_id.billing_id.billing_time')
    def _compute_actual_duration(self):
        for record in self:
            if record.duration:
                record.actual_duration = record.duration
            else:
                billing_id = record.action_id.billing_id
                fua_duration = sum(record.action_id.followup_action_ids.mapped('duration'))
                record.actual_duration = billing_id.billing_time - fua_duration

    def write(self, vals):
        super(UranosFollowupAction, self).write(vals)
        if 'duration' in vals:
            for record in self:
                record._compute_actual_duration()
        return True


class UranosReport(models.Model):
    _name = "uranos_ts.report"
    _description = "Uranos Timesheet Statistics"
    _auto = False
    _rec_name = 'date'
    _order = 'date desc'

    pk_request = fields.Integer('Pk request', readonly=True)
    request_name = fields.Char('Request Name', readonly=True)
    pk_action = fields.Integer('Pk action', readonly=True)
    action_name = fields.Char('Action Name', readonly=True)
    date = fields.Date('Event Date', readonly=True)
    customer_partner_id = fields.Many2one('res.partner', 'Customer', readonly=True)
    employee_partner_id = fields.Many2one('res.partner', 'Employee', readonly=True)
    work_name = fields.Char('Work Type', readonly=True)
    rate_name = fields.Char('Rate Type', readonly=True)
    billing_type = fields.Char('Billing Type', readonly=True)
    billing_time_reel = fields.Float('Sale hrs', readonly=True)
    billing_time = fields.Float('Cost hrs', readonly=True)
    billing_rate = fields.Float('Sale rate', readonly=True)
    pay_rate_work = fields.Float('Cost rate', readonly=True)
    billing_amount = fields.Float('Sale $', readonly=True)
    billing_cost_bm = fields.Float('Cost $', readonly=True)
    nbr = fields.Integer('# of Lines', readonly=True)
    status = fields.Char('Status', readonly=True)

    def _select(self):
        select_str = """
             SELECT min(a.id) as id,
                    r.pk_request as pk_request,
                    a.pk_action as pk_action,
                    r.name as request_name,
                    a.name as action_name,
                    e.date_start_event as date,
                    r.partner_id as customer_partner_id,
                    e.employee_partner_id,
                    b.work_name as work_name,
                    b.rate_name as rate_name,
                    b.billing_type as billing_type,
                    sum(b.billing_time_reel) as billing_time_reel,
                    sum(b.billing_time) as billing_time,
                    avg(b.billing_rate) as billing_rate,
                    avg(b.pay_rate_work) as pay_rate_work,
                    sum(b.billing_time_reel * b.billing_rate) as billing_amount,
                    sum(a.billing_cost_bm) as billing_cost_bm,
                    count(*) as nbr,
                    a."status" as status
        """
        return select_str

    def _from(self):
        from_str = """
                uranos_action a
                      join uranos_event e on (e.id = a.event_id)
                      join uranos_request r on (r.id = a.request_id)
                      join uranos_billing b on (b.id = a.billing_id)
        """
        return from_str

    def _group_by(self):
        group_by_str = """
            GROUP BY e.date_start_event,
                    r.pk_request,
                    a.pk_action,
                    r.name,
                    a.name,
                    e.date_start_event,
                    r.partner_id,
                    e.employee_partner_id,
                    a.status,
                    b.work_name,
                    b.rate_name,
                    b.billing_type
        """
        return group_by_str

    def init(self):
        # self._table = sale_report
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (
            %s
            FROM ( %s )
            %s
            )""" % (self._table, self._select(), self._from(), self._group_by()))
