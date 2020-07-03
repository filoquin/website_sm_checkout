# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class City(models.Model):
    _name = 'res.city'
    _inherit = ['res.city', 'website.published.mixin', 'website.multi.mixin']

    def get_website_sale_city(self, mode='billing'):
        return self.sudo().search([('website_published', '=', True)])


class ResCountry(models.Model):
    _inherit = 'res.country'

    def get_website_sale_city(self, mode='billing'):
        return self.env['res.city'].sudo().search([('website_published', '=', True)])

    def get_website_sale_countries(self, mode='billing'):
        return [x.country_id for x in self.get_website_sale_city()]

    def get_website_sale_states(self, mode='billing'):
        state_ids = self.env['res.country.state']
        for x in self.get_website_sale_city():
            state_ids += x.state_id
        return state_ids
