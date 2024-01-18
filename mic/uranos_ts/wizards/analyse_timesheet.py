# -*- coding: utf-8 -*-
from odoo import fields, models


class SynchronizeTimesheetDay(models.TransientModel):
    _name = 'uranos.timesheet.analyse'
    _description = 'Synchronize Timesheet'

    # Todo add type Day, Person, Department.
    to_analyse = fields.Selection([('all', 'All (Open and Close)')], 'Element To Analyse', default='all')

    def analyse_timesheet(self):
        if self.to_analyse == 'all':
            self.env['uranos.action'].analyse_timesheet_to_supervise()
