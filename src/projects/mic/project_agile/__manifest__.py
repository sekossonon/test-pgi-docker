# -*- coding: utf-8 -*-
{
    'name': "Project Agile",

    'summary': """
        Ajout de menu pour le suivie de projet en mode Agile
    """,
    'description': """
        Ajout de menu pour le suivi de projet en mode Agile
        - Ajout de la gestion des sprints
        - Ajout de l'assignation des tâches à différent usagers pour chaque sprint.
        - Ajout d'un log pour le daily pour suivre l'avacement des tâches.

    """,
    'category': 'Project',
    'version': '16.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'Microcom',
    'website': 'http://www.microcom.ca/',

    'depends': [
        'base',
        'microcom_tasks',
        'project',
    ],

    'data': [
        'security/ir.model.access.csv',
        'data/daily_cron.xml',
        'data/sprint_data.xml',
        'views/daily_views.xml',
        'views/project_views.xml',
    ],

    'demo': [
    ],
}
