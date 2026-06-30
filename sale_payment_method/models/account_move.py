# Copyright 2025 Rodrigo A. Madureira <https://github.com/rodmad85>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    payment_method_ids = fields.Many2many(
        comodel_name="sale.payment.method",
        string="Payment Methods",
    )
