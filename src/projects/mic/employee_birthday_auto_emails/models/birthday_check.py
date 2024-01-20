# -*- coding: utf-8 -*-
import calendar
from datetime import datetime

from odoo import api, models, _


class Partner(models.Model):
    _inherit = "hr.employee"

    @api.model
    def cron_employee_birthday_reminder(self):
        template_id = self.env.ref('employee_birthday_auto_emails.email_template_birthday')
        today = datetime.now()
        celebrated_partners = self.get_partners_celebrated_for_date(today)
        if celebrated_partners:
            self.generate_and_send_email(celebrated_partners, template_id)
        return True

    @api.model
    def get_partners_celebrated_for_date(self, date):
        # slice date string to keep 'mm-dd'
        start = date.isoformat()[5:10]

        if start == '02-28' and not calendar.isleap(date.year):
            domain = ['|',
                      ('birthday', 'like', start),
                      ('birthday', 'like', '02-29')]
        else:
            domain = [('birthday', 'like', start)]
        domain.extend([('active', '=', True)])
        result = self.env['hr.employee'].search(domain)
        return result

    @api.model
    def generate_and_send_email(self, celebrated_partners, template_id):
        # code for find all the employees with an active user_id
        active_employees_ids = self.env['hr.employee'].search([('active', '=', True)])
        celebrated_employees = _(' et ').join(employee.name for employee in celebrated_partners)
        email_template_id = template_id.with_context(celebrated_employees=celebrated_employees).browse(template_id.id)
        for employee in active_employees_ids:
            email_template_id.send_mail(employee.id)
