# -*- coding: utf-8 -*-
{
    'name': "Microcom TS",

    'summary': """
        Ajout de menu pour gérer Timesheet
    """,
    'description': """
    """,
    'category': 'Project',
    'version': '16.0.1.2.0',
    'author': 'Microcom',
    'website': 'http://www.microcom.ca/',

    'depends': [
        'base',
        'crnd_web_tree_colored_field',
        'hr',
        'project',
        'uranos_ts',
        'web_domain_field',
    ],

    'data': [
        'data/cron.xml',
        'security/microcom_ts_security.xml',
        'security/ir.model.access.csv',
        'views/timesheet_views.xml',
        'views/project_task_views.xml',
        'views/uranos_view.xml',
        'wizards/synchronize_views.xml',
        'wizards/timesheet_action_views.xml',
        # depends on timesheet action
        'views/followup_views.xml',
        'views/employee_views.xml',
        'views/res_config_settings_views.xml',
        'views/project_task_type_views.xml',
        'views/res_partner_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # templates js
            'microcom_ts/static/src/**/*.js',
            'microcom_ts/static/src/**/**/*',
        ],
    },
    'demo': [
    ],
    'license': 'AGPL-3'
}
