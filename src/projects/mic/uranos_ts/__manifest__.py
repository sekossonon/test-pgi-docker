# -*- encoding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution
#    This module copyright (C) 2015 Microcom#    #
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': 'Lien Uranos-timesheet',
    'version': '16.0.1.1.0',
    'category': 'Partner Management',
    'description': """
Lien entre Uranos-Timesheet et Odoo
===================================
Permet de lier ou créer un request dans Timesheet en utilisant Odoo.

- Si le nom de la request commence par le Id odoo ou o + id Odoo, la request est liée.
  Sinon on crée une nouvelle request.
- Il est également possible de délier la request via Odoo.

Before installing this module, make sure that you have pymssql installed, sudo easy_install pymssql shoud do the trick
    """,
    'author': 'Microcom',
    'images': [],
    'depends': [
        'microcom_contact',
        'microcom_tasks',
        'partner_contact_department',
        'partner_customer_supplier',
        'project',
        'project_agile',
    ],
    'demo': [],
    'test': [],
    'data': [
        'security/uranos_ts_security.xml',
        'security/ir.model.access.csv',
        'data/email_template_view.xml',
        'data/scheduler_data.xml',
        'views/microcom_config_settings_view.xml',
        'views/project_issue_view.xml',
        'views/project_project_view.xml',
        'views/uranos_view.xml',
        'wizards/analyse_timesheet.xml',
        'wizards/project_task_fusion_wizard.xml',
        'views/project_task_view.xml',

    ],
    'auto_install': False,
    'installable': True,
    'license': 'AGPL-3'
}
