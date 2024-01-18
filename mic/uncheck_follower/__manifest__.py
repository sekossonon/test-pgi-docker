# -*- coding: utf-8 -*-

{
    'name': 'Uncheck Follower',
    'category': 'Mail',
    'summary': 'This module sets default checkbox false when user clicks on New message button.',
    'website': 'https://microcom.ca/en',
    'version': '11.0',
    'license': 'AGPL-3',
    'description': """
Internal Messages
=================
This module only targets followers when user clicks on New message button.
Extra partners are unchecked by default.
        """,
    'author': 'Microcom',
    'depends': ['base', 'mail', 'web'],
    'data': [
    ],
    'js': [],
    'qweb': [],
    'installable': True,
    'application': False,
    'assets': {
        'mail.assets_messaging': [
            'uncheck_follower/static/src/models/*.js',
        ],
    },

}
