from odoo import api, fields, models


class SaleCreateInvoicePlan(models.TransientModel):
    _inherit = "sale.create.invoice.plan"

    sale_id = fields.Many2one(
        comodel_name="sale.order",
        default=lambda self: self.env.context.get("active_id"),
    )
    currency_id = fields.Many2one(related="sale_id.currency_id")
    credit_card_fee_percent = fields.Float(
        string="Fee (%)",
        compute="_compute_credit_card_fee",
    )
    credit_card_fee_amount = fields.Monetary(
        compute="_compute_credit_card_fee",
    )
    amount_plus_fee = fields.Monetary(
        string="Amount + Fee",
        compute="_compute_credit_card_fee",
        help="Order total including the credit card fee.",
    )

    @api.depends(
        "sale_id",
        "sale_id.amount_untaxed",
        "sale_id.amount_tax",
        "sale_id.credit_card_fee_line_ids",
        "sale_id.credit_card_fee_line_ids.fee_range_id",
        "sale_id.credit_card_fee_line_ids.payment_method_id",
        "sale_id.credit_card_fee_line_ids.payment_method_id.fee_line_ids",
        "sale_id.credit_card_fee_line_ids.payment_method_id.fee_line_ids.fee_percent",
        "num_installment",
    )
    def _compute_credit_card_fee(self):
        """Preview the fee of the invoice plan about to be created.

        The preview applies the same computation as the sale order fee lines:
        the order, taxes included, is charged on the first fee line, the ones
        after it starting with no amount at all, and the fee of that line is
        charged on top of it.
        """
        for rec in self:
            sale = rec.sale_id
            if not sale:
                rec.credit_card_fee_percent = 0.0
                rec.credit_card_fee_amount = 0.0
                rec.amount_plus_fee = 0.0
                continue
            percents = []
            for line in sale.credit_card_fee_line_ids:
                fee = line.fee_range_id
                if not fee and rec.num_installment and line.payment_method_id:
                    fee = line.payment_method_id.fee_line_ids.filtered(
                        lambda r, n=rec.num_installment: (
                            r.installments_from <= n and r.installments_to >= n
                        )
                    )[:1]
                if fee:
                    percents.append(fee.fee_percent or 0.0)
            rec.credit_card_fee_percent = sum(percents)
            # The preview follows the default distribution of the fee lines:
            # the order, taxes included, is charged on the first one, so only
            # its fee is charged.
            base = sale._credit_card_fee_base()
            rec.credit_card_fee_amount = sum(
                base * percent / 100.0 for percent in percents[:1]
            )
            rec.amount_plus_fee = base + rec.credit_card_fee_amount
