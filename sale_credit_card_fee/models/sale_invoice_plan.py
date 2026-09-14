from odoo import api, fields, models


class SaleInvoicePlan(models.Model):
    _inherit = "sale.invoice.plan"

    credit_card_fee_percent = fields.Float(
        string="Fee (%)",
        related="sale_id.credit_card_fee_percent",
    )
    credit_card_fee_amount = fields.Float(
        string="Fee Amount",
        digits="Product Price",
        compute="_compute_fee_amount",
        store=True,
    )

    def _get_distribution_base(self):
        """Base amount used to distribute the installments.

        When the credit card fee is added to the order total (``sum_fee``),
        the fee is included in the base so every installment covers its
        share of the fee.
        """
        self.ensure_one()
        sale = self.sale_id._origin
        base = sale.amount_untaxed
        if sale.credit_card_fee_line_ids.filtered("sum_fee"):
            base += sale.credit_card_fee_amount
        return base

    @api.depends(
        "percent",
        "sale_id.credit_card_fee_amount",
        "sale_id.credit_card_fee_line_ids.sum_fee",
    )
    def _compute_amount(self):
        for rec in self:
            amount_base = rec._get_distribution_base()
            if not amount_base:
                continue
            # With invoice already created, no recompute
            if rec.invoiced:
                rec.amount = rec.amount_invoiced
                rec.percent = rec.amount / amount_base * 100
                continue
            # For last line, amount is the left over
            if rec.last:
                installments = rec.sale_id.invoice_plan_ids.filtered(
                    lambda plan: plan.invoice_type == "installment"
                )
                advance = rec.sale_id.invoice_plan_ids.filtered(
                    lambda plan: plan.invoice_type == "advance"
                )
                prev_amount = sum((installments - rec).mapped("amount")) + sum(
                    advance.mapped("amount")
                )
                rec.amount = amount_base - prev_amount
                continue
            rec.amount = rec.percent * amount_base / 100

    @api.onchange("amount", "percent")
    def _inverse_amount(self):
        for rec in self:
            amount_base = rec._get_distribution_base()
            if amount_base != 0:
                if rec.last:
                    installments = rec.sale_id.invoice_plan_ids.filtered(
                        lambda invoice_plan: invoice_plan.invoice_type == "installment"
                    )
                    prev_percent = sum((installments - rec).mapped("percent"))
                    rec.percent = 100 - prev_percent
                    continue
                rec.percent = rec.amount / amount_base * 100
                if rec.invoice_type == "advance":
                    rec._redistribute_installments()
                continue
            rec.percent = 0

    @api.depends(
        "sale_id.credit_card_fee_amount",
        "amount",
        "invoice_type",
    )
    def _compute_fee_amount(self):
        for rec in self:
            if not rec.sale_id.credit_card_fee_amount:
                rec.credit_card_fee_amount = 0.0
                continue
            if rec.invoice_type != "installment":
                rec.credit_card_fee_amount = 0.0
                continue
            total_installment_amount = sum(
                rec.sale_id.invoice_plan_ids.filtered(
                    lambda p: p.invoice_type == "installment"
                ).mapped("amount")
            )
            if total_installment_amount:
                ratio = rec.amount / total_installment_amount
                rec.credit_card_fee_amount = rec.sale_id.credit_card_fee_amount * ratio
            else:
                rec.credit_card_fee_amount = 0.0
