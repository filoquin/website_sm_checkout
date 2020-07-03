# -*- coding: utf-8 -*-
{
    'name': "website small checkout",

    'summary': """
        Small checkout for website sale""",

    'description': """
        Website small checkout
        This module implemen small checkout
        city has  country and state
        vat number is DNI by defualt
    """,

    'author': "Sipecu",
    'website': "http://www.sipecu.com.ar",

    'category': 'website sale',
    'version': '0.1',

    'depends': [
        'base_address_city',
        'website_sale'
    ],

    'data': [
        'views/template_address.xml',
        'views/res_city.xml',
    ],
}
