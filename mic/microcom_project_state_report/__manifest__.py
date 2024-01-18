# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Project State
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################
{
    'name': 'Microcom project state report',
    'summary': 'Project state report',
    'description': """Project monitoring""",
    'version': '16.0.0.3',
    'category': 'Project',
    'sequence': 35,
    'license': 'OPL-1',
    'author': 'Microcom',
    'website': 'https://www.microcom.ca',
    'depends': [
        'project',
        'web'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/project_state_view.xml',
        'views/project_project_state_view.xml',
        'views/menus.xml'
    ],
    'assets': {
        'web.assets_backend': [
            '/microcom_project_state_report/static/src/**/*.xml',
            '/microcom_project_state_report/static/src/**/*.js',
            '/microcom_project_state_report/static/src/**/*.scss',
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
