# Copyright 2025 Rodrigo A. Madureira <https://github.com/rodmad85>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Sale Payment Method",
    "summary": "Add payment method to sale orders and invoices",
    "version": "18.0.1.0.0",
    "category": "Sales Management",
    "website": "https://www.madooit.com",
    "author": "Madooit, Rodrigo A. Madureira, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "sale",
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/sale_payment_method_data.xml",
        "views/sale_payment_method_views.xml",
        "views/sale_order_view.xml",
        "views/account_move_view.xml",
    ],
}
