# -*- coding: utf-8 -*-

from random import randint
from odoo import models, fields, api, _


class UncertaintyOrInnovation(models.Model):
    _name = 'uncertainty.or.innovation'
    _inherit = 'mail.thread'

    name = fields.Char('Uncertainty or innovation', required=True)
    tag_ids = fields.Many2many('uncertainty.or.innovation.tags', string="Tag uncertainty or innovation")
    hypothesis_lines = fields.One2many('idea.hypothesis', 'incertitude_id', 'Idee or Hypothese')
    details = fields.Text("Details of idea or hypothesis")


class UncertaintyOrInnovationTags(models.Model):
    _name = "uncertainty.or.innovation.tags"
    _description = "Uncertainty or innovation Tags"

    def _default_color(self):
        return randint(1, 11)

    name = fields.Char('Name', required=True)
    color = fields.Integer('Color', default=_default_color)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "A tag with the same name already exists."),
    ]


class IdeaOrHypothesis(models.Model):
    _name = 'idea.hypothesis'
    _inherit = 'mail.thread'
    _rec_name = 'name'

    name = fields.Char(string="Name", required=True, )
    work_or_progres_lines = fields.One2many('rsde.work', 'idea_or_hypothesis_id', string="Work or progress line", )
    obstacle_or_accomplishment_lines = fields.One2many('rsde.obstacle', 'idea_or_hypothesis_id', string="Obstacle or accomplishment line", )
    conclusion_learning_reuse_lines = fields.One2many('rsde.conclusion', 'idea_or_hypothesis_id', string='Conclusion, learning, reuse line')
    summary = fields.Text('Details of idea or hypothesis')
    conclusion = fields.Text('Summary or final conclusion')
    incertitude_id = fields.Many2one('uncertainty.or.innovation', 'Uncertainty or innovation', ondelete='restrict')
