from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _refresh_credit_card_fee_amounts(self):
        """Keep the credit card fee amounts up to date with the order.

        The amount of a fee line defaults to the order total plus the credit
        card fee, so it has to be refreshed whenever the order lines change.
        """
        for order in self.order_id:
            order.credit_card_fee_line_ids._check_amounts()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._refresh_credit_card_fee_amounts()
        return lines

    def write(self, vals):
        res = super().write(vals)
        self._refresh_credit_card_fee_amounts()
        return res

    def unlink(self):
        orders = self.order_id
        res = super().unlink()
        orders._refresh_credit_card_fee_amounts()
        return res
