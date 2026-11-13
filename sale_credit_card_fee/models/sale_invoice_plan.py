from odoo import api, fields, models


class SaleInvoicePlan(models.Model):
    _inherit = "sale.invoice.plan"

    credit_card_fee_percent = fields.Float(
        string="Fee (%)",
        related="sale_id.credit_card_fee_percent_sum",
    )
    credit_card_fee_amount = fields.Float(
        string="Fee Amount",
        digits="Product Price",
        compute="_compute_fee_amount",
        store=True,
    )

    @api.depends(
        "sale_id.credit_card_fee_line_ids.fee_amount",
        "sale_id.credit_card_fee_line_ids.sum_fee",
        "amount",
        "invoice_type",
        "sale_id.invoice_plan_ids.amount",
        "sale_id.invoice_plan_ids.invoice_type",
    )
    def _compute_fee_amount(self):
        for rec in self:
            # Only the fee the order really charges is invoiced: a fee line
            # without Add Fee is kept for tracking but is not added to the
            # value of the order.
            fee = sum(
                rec.sale_id.credit_card_fee_line_ids.filtered("sum_fee").mapped(
                    "fee_amount"
                )
            )
            if not fee or rec.invoice_type != "installment":
                rec.credit_card_fee_amount = 0.0
                continue
            total_installment_amount = sum(
                rec.sale_id.invoice_plan_ids.filtered(
                    lambda p: p.invoice_type == "installment"
                ).mapped("amount")
            )
            if total_installment_amount:
                ratio = rec.amount / total_installment_amount
                rec.credit_card_fee_amount = fee * ratio
            else:
                rec.credit_card_fee_amount = 0.0
