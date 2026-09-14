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
        "sale_id.amount_total",
        "sale_id.credit_card_fee_line_ids",
        "sale_id.credit_card_fee_line_ids.sum_fee",
        "sale_id.credit_card_fee_line_ids.fee_range_id",
        "sale_id.credit_card_fee_line_ids.payment_method_id",
        "sale_id.credit_card_fee_line_ids.payment_method_id.fee_line_ids",
        "sale_id.credit_card_fee_line_ids.payment_method_id.fee_line_ids.fee_percent",
        "num_installment",
    )
    def _compute_credit_card_fee(self):
        for rec in self:
            percent = 0.0
            sale = rec.sale_id
            if sale:
                rec.amount_plus_fee = sale.amount_untaxed + sale.amount_tax
            else:
                rec.credit_card_fee_percent = 0.0
                rec.credit_card_fee_amount = 0.0
                continue
            for line in sale.credit_card_fee_line_ids:
                fee = line.fee_range_id
                if not fee and rec.num_installment and line.payment_method_id:
                    fee = line.payment_method_id.fee_line_ids.filtered(
                        lambda r: r.installments_from <= rec.num_installment
                        and r.installments_to >= rec.num_installment
                    )[:1]
                if fee:
                    percent += fee.fee_percent or 0.0
            rec.credit_card_fee_percent = percent
            base = sale.amount_untaxed + sale.amount_tax
            fee_amount = base * percent / 100.0
            rec.credit_card_fee_amount = fee_amount
            rec.amount_plus_fee = base + fee_amount