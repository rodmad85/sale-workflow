# Copyright 2025 Rodrigo A. Madureira <https://github.com/rodmad85>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    payment_method_ids = fields.Many2many(
        comodel_name="sale.payment.method",
        string="Payment Methods",
    )

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        values["payment_method_ids"] = [
            Command.set(self.payment_method_ids.ids)
        ]
        return values
