# Copyright 2025 Rodrigo A. Madureira <https://github.com/rodmad85>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class SalePaymentMethod(models.Model):
    _name = "sale.payment.method"
    _description = "Sale Payment Method"
    _order = "sequence, name"

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )
