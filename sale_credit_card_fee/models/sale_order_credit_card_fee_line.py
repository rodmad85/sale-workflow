from odoo import api, fields, models


class SaleOrderCreditCardFeeLine(models.Model):
    _name = "sale.order.credit.card.fee.line"
    _description = "Sale Order Credit Card Fee Line"

    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sale Order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    payment_method_id = fields.Many2one(
        comodel_name="payment.method",
        string="Payment Method",
        required=True,
        ondelete="restrict",
        domain="[('credit_card_admin', '=', True)]",
    )
    sum_fee = fields.Boolean(
        string="Add Fee",
        default=True,
        help="Add the credit card fee of this payment method to the order total.",
    )
    fee_range_id = fields.Many2one(
        comodel_name="credit.card.fee.range",
        string="Credit Card Fee Range",
        domain="[('payment_method_id', '=', payment_method_id)]",
    )
    fee_percent = fields.Float(
        string="Fee (%)",
        compute="_compute_fee_percent",
        store=True,
        readonly=True,
    )

    @api.depends(
        "fee_range_id",
        "fee_range_id.fee_percent",
        "payment_method_id",
        "payment_method_id.fee_line_ids",
        "payment_method_id.fee_line_ids.installments_from",
        "payment_method_id.fee_line_ids.installments_to",
        "payment_method_id.fee_line_ids.fee_percent",
        "sale_order_id",
        "sale_order_id.invoice_plan_ids",
        "sale_order_id.invoice_plan_ids.invoice_type",
    )
    def _compute_fee_percent(self):
        for line in self:
            line.fee_percent = 0.0
            if line.fee_range_id:
                line.fee_percent = line.fee_range_id.fee_percent
                continue
            installments = line.sale_order_id.invoice_plan_ids.filtered(
                lambda p: p.invoice_type == "installment"
            )
            num_installments = len(installments)
            if not num_installments:
                continue
            fee = line.payment_method_id.fee_line_ids.filtered(
                lambda r, n=num_installments: (
                    r.installments_from <= n and r.installments_to >= n
                )
            )[:1]
            line.fee_percent = fee.fee_percent if fee else 0.0
