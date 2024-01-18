# -*- coding: utf-8 -*-

import calendar
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class Partner(models.Model):
    _inherit = "res.partner"

    hire_date = fields.Date(string='Hire Date')

    @api.model
    def cron_employee_work_anniversary_reminder(self):
        template_id = self.env.ref(
            "work_anniversary_auto_emails.email_template_work_anniversary")
        in_a_month = datetime.now() + timedelta(days=30)
        celebrated_users = get_users_celebrated_for_date(self, in_a_month)

        if len(celebrated_users) > 0:
            generate_and_send_email(self, celebrated_users, in_a_month.year,
                                    template_id[0])

        return True


def get_users_celebrated_for_date(self, date):
    # slice date string to keep '-mm-dd'
    start = date.isoformat()[4:10]
    if start == '-02-28' and not calendar.isleap(date.year):
        domain = ['|', ('hire_date', 'like', start),
                  ('hire_date', 'like', '-02-29')]
    else:
        domain = [('hire_date', 'like', start)]
    return self.env['res.partner'].search(domain).mapped('user_ids')


def generate_and_send_email(self, celebrated_users, year, template_id):
    params = self.env['ir.config_parameter'].sudo()
    email_to_employees = params.get_param('work_anniversary.emails')
    if not email_to_employees:
        raise UserError(_("You must enter at least one e-mail address in Work Anniversary settings!"))

    hire_info = [_("{name} (date d'embauche: {hire_date}, {seniority} ans)").
                 format(name=user.name, hire_date=user.hire_date,
                        seniority=(year - int(user.hire_date[0:4])))
                 for user in celebrated_users]
    celebrated_employees_and_hire_info = ' et '.join(hire_info)
    celebrated_employees = ' et '.join(user.name for user in celebrated_users)
    email_template_id = self.env['mail.template'].with_context(
        celebrated_employees_and_hire_infos=celebrated_employees_and_hire_info,
        celebrated_employees=celebrated_employees,
        email_to=email_to_employees).browse(template_id)
    email_template_id.send_mail(celebrated_users[0].id)
