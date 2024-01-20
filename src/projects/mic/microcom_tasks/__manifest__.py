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
    'name': 'Microcom tasks',
    'version': '16.0.1.2.0',
    'category': 'Project Management',
    'author': 'Microcom',
    'summary': 'Customized listview for tasks',
    'description': """
Microcom tasks
==============
*Adds "Planned" field for Tasks, on Form view

*Adds stars to Priority field (now has 5) which are: Nice to Have, Low, Normal, High, Very High

*Adds a customized listview for tasks in "Project Management" module:

ID | Project | Task Title | Priority | Stage | State (is "Kanban State") | Planned | Assigned to | Creation Date

**************************************************************************************

*Ajoute le champ "Planifié" pour les Tâches, dans la vue Formulaire

*Ajoute des étoiles au champ Priorité (en a maintenant 5) qui sont: À temps perdu, Basse, Normal, Urgent, Urgence extrême

*Ajoute une vue "liste" personnalisée des tâches dans le module "Gestion de projets":

ID | Projet | Titre de la tâche | Priorité | Étape | État (est "État Kanban") | Planifié | Assigné à | Date de création
""",
    'depends': [
        'web',
        'base',
        'base_setup',
        'project',
    ],
    'data': [
        'data/scheduler_data.xml',
        'security/project_security.xml',
        'security/ir.model.access.csv',
        'views/project_view.xml',
        'views/task_process_view.xml',
    ],
    'post_init_hook': '_set_microcom_sequence',
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
    'assets': {
        'web.assets_backend': [
            'microcom_tasks/static/src/**/*',
        ],
    },
    'license': 'AGPL-3'
}
