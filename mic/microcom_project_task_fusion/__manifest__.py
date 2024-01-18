# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Project Task Fusion
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################
{
    'name': 'microcom project task fusion',
    'summary': 'Project tasks fusion',
    'description': """This module allows you to merge one or more tasks""",
    'version': '15.0.0.1',
    'category': 'Project',
    'sequence': 35,
    'license': 'OPL-1',
    'author': 'Microcom',
    'website': 'https://www.microcom.ca',
    'depends': [
        'project',
        'uranos_ts'
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/project_task_fusion_wizard.xml',
        'views/project_task_view.xml',
    ],
    'assets': {
        'web.assets_backend': [],
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
