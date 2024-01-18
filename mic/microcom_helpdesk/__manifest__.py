# -*- encoding: utf-8 -*-
{
    'name': 'Microcom Helpdesk',
    'version': '16.0.1',
    'category': 'Project Management',
    'author': 'Microcom',
    'license': 'AGPL-3',
    'summary': 'Helpdesk for Microcom',
    'description': """
Microcom Helpdesk

""",
    'depends': [
        'microcom_tasks',
        'partner_contact_department',
        'project_agile',
        'project_task_default_stage',
        'microcom_ts',
        'web_domain_field'
    ],
    'data': [
        'data/data.xml',
        'security/ir.model.access.csv',
        'views/project_view.xml',
        # in project view exist reference to mailbox view
        'views/mailbox_view.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
