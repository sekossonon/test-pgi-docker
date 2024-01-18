# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Timesheet(models.Model):
    _inherit = 'microcom.timesheet'

    rsde_lines = fields.One2many('microcom.rsde', 'timesheet_id', 'Research And Development Line')

    def action_show_rsde(self):
        """ edit rsde of entry
        if non-existent, defaults to the same incertitude
        """
        # should be unique
        self_rsde = self.rsde_lines
        # copy source if missing
        source_rsde = self_rsde or self.env['microcom.rsde'].search([('task_id', '=', self.task_id.id)], limit=1)
        wiz_id = self.env['rsde.wizard'].create({
            # taken from self, will be False if non-existent
            'rsde_id': self_rsde.id,
            'rsde_work_description': self_rsde.rsde_work_id.description,
            'rsde_obstacle_description': self_rsde.rsde_obstacle_id.description,
            'rsde_conclusion_description': self_rsde.rsde_conclusion_id.description,
            # copied from previous rsde if missing
            'tag_ids': source_rsde.tag_ids.ids,
            'incertitude_id': source_rsde.incertitude_id.id,
            'idea_or_hypothesis_id': source_rsde.idea_or_hypothesis_id.id,
            # external data
            'timesheet_id': self.id,
            'task_id': self.task_id.id,
        })
        return {
            'name': 'R&D',
            'view_mode': 'form',
            'res_model': 'rsde.wizard',
            'res_id': wiz_id.id,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }
