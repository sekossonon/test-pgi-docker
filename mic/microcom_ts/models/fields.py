# -*- coding: utf-8 -*-

from odoo import api, models


class MinuteTimeConverter(models.AbstractModel):
    """ ``minute_time`` converter, to display integral minutes as
    human-readable time spans (e.g. 90 as "01:30").

    Can be used on any numerical field.
    """
    _name = 'ir.qweb.field.minute_time'
    _description = 'minute_time converter, to display integral minutes as human-readable'
    _inherit = 'ir.qweb.field'

    @api.model
    def value_to_html(self, value, options):
        hours, minutes = divmod(abs(value), 60)
        minutes = round(minutes)
        if minutes == 60:
            minutes = 0
            hours += 1
        if value < 0:
            return '-%02d:%02d' % (hours, minutes)
        return '%02d:%02d' % (hours, minutes)
