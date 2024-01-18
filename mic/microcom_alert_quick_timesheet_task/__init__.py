# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Alert quick timesheet task
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################

def pre_init_check(cr):
    from odoo.service import common
    from odoo.exceptions import Warning
    version_info = common.exp_version()
    server_serie = version_info.get('server_serie')
    if server_serie != '16.0':
        raise Warning(
            'Module support Odoo series 16.0 found {}.'.format(server_serie))
    return True

from . import models