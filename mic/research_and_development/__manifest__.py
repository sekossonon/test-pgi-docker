# -*- coding: utf-8 -*-
{
    'name': "Research and Development",

    'summary': """
    """,
    'description': """

    """,
    'category': 'Project',
    'version': '16.0.2.0.0',
    'author': 'Microcom',
    'website': 'http://www.microcom.ca/',

    'depends': [
        'base',
        'microcom_tasks',  # explicit for group_project_supervisor
        'microcom_ts',
        'web_domain_field',
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/project_views.xml',
        'views/research_and_development.xml',
        'views/timesheet_views.xml',
        'views/uncertainty_or_innovation_view.xml',
        'wizards/research_development_wizard_views.xml',
    ],

    'demo': [
    ],
}
