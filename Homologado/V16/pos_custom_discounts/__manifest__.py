# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#dddddddddddddddd
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################
{
  "name"                 :  "POS Custom Discount",
  "summary"              :  """This module allows the seller to apply discount on single product as well as complete order in pos session.Order Discount|Discount on Products|Discounted Products.""",
  "category"             :  "Point Of Sale",
  "version"              :  "1.0.1",
  "author"               :  "Webkul Software Pvt. Ltd.",
  "license"              :  "Other proprietary",
  "website"              :  "https://store.webkul.com/Odoo-POS-Custom-Discount.html",
  "description"          :  """http://webkul.com/blog/odoo-pos-custom-discount/""",
  "live_test_url"        :  "http://odoodemo.webkul.com/?module=pos_custom_discounts&custom_url=/pos/auto",
  "depends"              :  ['point_of_sale'],
  "data"                 :  [
                             'views/pos_config_view.xml',
                             'views/pos_custom_discounts_view.xml',
                             'security/ir.model.access.csv',
                            ],
  "demo"                 :  ['data/pos_custom_discount_demo.xml'],
  "images"               :  ['static/description/Banner.png'],
  "application"          :  True,
  "installable"          :  True,
  "assets"               :  {
                              'point_of_sale.assets': [
                                "/pos_custom_discounts/static/src/js/main.js",
                                "/pos_custom_discounts/static/src/css/pos_custom_discounts.css",
                                'pos_custom_discounts/static/src/xml/pos_custom_discounts.xml',
                                ],
                             },
  "auto_install"         :  False,
  "price"                :  49,
  "currency"             :  "USD",
  "pre_init_hook"        :  "pre_init_check",
}