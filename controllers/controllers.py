# -*- coding: utf-8 -*-
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.exceptions import ValidationError
from odoo import http, tools, _
from odoo.http import request
from werkzeug.exceptions import Forbidden

import logging
_logger = logging.getLogger(__name__)


class WebsiteSale(WebsiteSale):

    def checkout_form_validate(self, mode, all_form_values, data):
        # mode: tuple ('new|edit', 'billing|shipping')
        # all_form_values: all values before preprocess
        # data: values after preprocess
        error = dict()
        error_message = []

        # Required fields from form
        required_fields = [f for f in (all_form_values.get('field_required') or '').split(',') if f]
        # Required fields from mandatory field function
        required_fields += mode[1] == 'shipping' and self._get_mandatory_shipping_fields() or self._get_mandatory_billing_fields()
        # update country and state
        city = request.env['res.city']
        required_fields += ['city_id']
        if data.get('city_id'):
            city = city.browse(int(data.get('city_id')))
            data['city'] = city.name
            data['country_id'] = city.country_id.id
            data['state_id'] = city.state_id.id
            if not data.get('zip'):
                data['zip'] = city.zipcode

        # error message for empty required fields
        for field_name in required_fields:
            if not data.get(field_name):
                _logger.info("missing %r" % field_name)
                error[field_name] = 'missing'

        # email validation
        if data.get('email') and not tools.single_email_re.match(data.get('email')):
            error["email"] = 'error'
            error_message.append(_('Invalid Email! Please enter a valid email address.'))

        # vat validation
        Partner = request.env['res.partner']
        if data.get("vat") and hasattr(Partner, "check_vat"):
            if data.get("country_id"):
                data["vat"] = Partner.fix_eu_vat_number(data.get("country_id"), data.get("vat"))
            partner_dummy = Partner.new({
                'vat': data['vat'],
                'country_id': (int(data['country_id'])
                               if data.get('country_id') else False),
            })
            try:
                partner_dummy.check_vat()
            except ValidationError:
                error["vat"] = 'error'

        if [err for err in error.values() if err == 'missing']:
            error_message.append(_('Some required fields are empty.'))

        return error, error_message

    def _get_mandatory_billing_fields(self):
        return ["name", "email", "street", "city_id", "country_id"]

    def _get_mandatory_shipping_fields(self):
        return ["name", "street", "city_id", "country_id"]

    def values_postprocess(self, order, mode, values, errors, error_msg):
        new_values, errors, error_msg = super(WebsiteSale, self).values_postprocess( order, mode, values, errors, error_msg)
        new_values['city_id'] = values['city_id']
        return new_values, errors, error_msg

    @http.route(['/shop/address'], type='http', methods=['GET', 'POST'], auth="public", website=True, sitemap=False)
    def address(self, **kw):
        Partner = request.env['res.partner'].with_context(show_address=1).sudo()
        order = request.website.sale_get_order()

        redirection = self.checkout_redirection(order)
        if redirection:
            return redirection

        mode = (False, False)
        can_edit_vat = False
        def_country_id = order.partner_id.country_id
        values, errors = {}, {}

        partner_id = int(kw.get('partner_id', -1))

        # IF PUBLIC ORDER
        if order.partner_id.id == request.website.user_id.sudo().partner_id.id:
            mode = ('new', 'billing')
            can_edit_vat = True
            country_code = request.session['geoip'].get('country_code')
            if country_code:
                def_country_id = request.env['res.country'].search([('code', '=', country_code)], limit=1)
            else:
                def_country_id = request.website.user_id.sudo().country_id
        # IF ORDER LINKED TO A PARTNER
        else:
            if partner_id > 0:
                _logger.info('aca')
                if partner_id == order.partner_id.id:
                    _logger.info('aca')
                    mode = ('edit', 'billing')
                    can_edit_vat = order.partner_id.can_edit_vat()
                else:
                    shippings = Partner.search([('id', 'child_of', order.partner_id.commercial_partner_id.ids)])
                    if partner_id in shippings.mapped('id'):
                        mode = ('edit', 'shipping')
                    else:
                        return Forbidden()
                if mode:
                    values = Partner.browse(partner_id)
            elif partner_id == -1:
                mode = ('new', 'shipping')
            else: # no mode - refresh without post?
                return request.redirect('/shop/checkout')

        # IF POSTED
        if 'submitted' in kw:
            pre_values = self.values_preprocess(order, mode, kw)
            errors, error_msg = self.checkout_form_validate(mode, kw, pre_values)
            post, errors, error_msg = self.values_postprocess(order, mode, pre_values, errors, error_msg)

            if errors:
                errors['error_message'] = error_msg
                values = kw
            else:
                partner_id = self._checkout_form_save(mode, post, kw)
                if mode[1] == 'billing':
                    order.partner_id = partner_id
                    order.with_context(not_self_saleperson=True).onchange_partner_id()
                    # This is the *only* thing that the front end user will see/edit anyway when choosing billing address
                    order.partner_invoice_id = partner_id
                    if not kw.get('use_same'):
                        kw['callback'] = kw.get('callback') or \
                            (not order.only_services and (mode[0] == 'edit' and '/shop/checkout' or '/shop/address'))
                elif mode[1] == 'shipping':
                    order.partner_shipping_id = partner_id

                order.message_partner_ids = [(4, partner_id), (3, request.website.partner_id.id)]
                if not errors:
                    return request.redirect(kw.get('callback') or '/shop/confirm_order')
        city_id = 'city_id' in values and values['city_id'] != '' and request.env['res.city'].browse(int(values['city_id']))
        country = city_id and city_id.exists() and city_id.country_id
        country = country and country.exists() or def_country_id
        city_ids = country.get_website_sale_city(mode=mode[1])
        states = city_ids.state_id
        countries = city_ids.country_id
        render_values = {
            'website_sale_order': order,
            'partner_id': partner_id,
            'mode': mode,
            'checkout': values,
            'can_edit_vat': can_edit_vat,
            'country': country,
            'city_id': city_id,
            'city_ids': country.get_website_sale_city(mode=mode[1]),
            'countries': countries,
            'states': states,
            'error': errors,
            'callback': kw.get('callback'),
            'only_services': order and order.only_services,
        }
        return request.render("website_sale.address", render_values)

    @http.route(['/shop/city_infos/<model("res.city"):city>'], type='json', auth="public", methods=['POST'], website=True)
    def city_infos(self, city, mode, **kw):
        return dict(
            fields=city.country_id.get_address_fields(),
            states=[(st.id, st.name, st.code) for st in city.country_id.get_website_sale_states(mode=mode)],
            phone_code=city.country_id.phone_code,
            zipcode=city.zipcode
        )
