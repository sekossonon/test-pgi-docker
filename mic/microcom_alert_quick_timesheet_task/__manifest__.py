# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Alert quick timesheet task
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################
{
    'name': 'Microcom Alert Quick Timesheet Task',
    'summary': 'Alert Quick Timesheet Task',
    'description': """The goal is to know that the task has already been completed by another user.""",
    'version': '16.0.0.3',
    'category': 'Project',
    'sequence': 35,
    'license': 'OPL-1',
    'author': 'Microcom',
    'website': 'https://www.microcom.ca',
    'depends': [
        'microcom_ts',
        'microcom_helpdesk'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings.xml',
        'views/project_project_view.xml',
        'views/microcom_timesheet_view.xml',
        'views/microcom_timesheet_history_view.xml'
    ],
    'assets': {
        'web._assets_primary_variables': [
            (
                'after',
                'web/static/src/scss/primary_variables.scss',
                'microcom_alert_quick_timesheet_task/static/src/colors.scss'
            ),
        ],
        'web.assets_backend': [
            'microcom_alert_quick_timesheet_task/static/src/**/*',

        ],
        'web.assets_frontend': [],
    },

    'images': [
        'static/description/banner.png',
    ],
    'external_dependencies': {
        'python': [],
    },
    'pre_init_hook': 'pre_init_check',

    'installable': True,
    'application': False,
    'auto_install': False
}
