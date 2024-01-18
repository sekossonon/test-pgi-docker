# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Project State
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################

from odoo import fields, models, api, _
from odoo.tools.misc import groupby as tools_groupby


class ProjectUpdate(models.Model):
    _inherit = 'project.update'

    active = fields.Boolean(
        default=True
    )


class ProjectState(models.Model):
    _name = 'microcom.project.state'
    _description = 'Microcom Project state'

    def _get_domain(self):
        company_id = self.env.company
        return [
            ('company_id', '=', company_id.id),
            ('display_in_project_status', '=', True)
        ]

    def get_project_state(self, domain):
        project_state = []
        self = self.sudo()
        domain += self._get_domain()
        #
        project_obj = self.env['project.project']
        read_fields = [
            'id',
            'name',
            'user_id',
            'partner_id',
            'last_update_status',
            'color',
            'date_start'
        ]
        #
        projects = project_obj.search(
            domain
        ).sorted(lambda m: m.partner_id and m.partner_id.name or m.name)
        project_state = projects.read(read_fields)
        return project_state

    @api.model
    def get_record_view(self, domain=False):
        project_state = self.get_project_state(domain)
        project_update = project_linked = False
        if project_state:
            result = self.get_project_update(project_state[0]['id'])
            project_linked = result['project_linked']
            project_update = result['project_update']
        res = {
            'project_state': project_state,
            'project_update': project_update,
            'project_linked': project_linked,
            'company_id': self.env.company.id
        }
        return res

    @api.model
    def get_project_update(self, project_id):
        OBJ = self.env['project.project']
        project_id = OBJ.browse(project_id)
        project_update_ids = project_id.mapped('update_ids')
        read_project_fields = [
            'id',
            'name',
            'partner_id'
        ]

        read_fields = [
            'id',
            'name',
            'date',
            'project_id'
        ]
        project_result = []
        for project in project_update_ids:
            project_result += project.read(read_fields)
        res = {
            'project_update': project_result,
            'project_linked': project_id.read(read_project_fields)
        }
        return res

    @api.model
    def archive_project_update(self, update_id):
        OBJ = self.env['project.update']
        OBJ.browse(update_id).active = False
