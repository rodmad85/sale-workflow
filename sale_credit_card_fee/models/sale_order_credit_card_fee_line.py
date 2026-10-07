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
    currency_id = fields.Many2one(
        related="sale_order_id.currency_id",
        string="Currency",
    )
    amount = fields.Monetary(
        currency_field="currency_id",
        help="Amount the fee of this payment method is charged on. It "
        "defaults to the order total plus the credit card fee, follows the "
        "order until it is edited and can be edited to charge the fee of "
        "this payment method on another amount.",
    )
    custom_amount = fields.Boolean(
        default=False,
        help="Keep the amount of this line when the order total or the "
        "credit card fees change.",
    )
    fee_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_fee_amount",
        store=True,
        help="Fee of this payment method, charged on the amount.",
    )

    @api.model
    def _format_fee_percents(self, percents):
        """Return the fee percentages as a single comma separated string."""
        return ", ".join(
            f"{percent:.2f}".rstrip("0").rstrip(".") for percent in percents if percent
        )

    @api.model
    def _amount_with_fee(self, amount, percent):
        """Return an amount increased by the fee of a percentage."""
        return amount + amount * (percent or 0.0) / 100.0

    def _set_default_amount(self):
        """Fill the amount of the fee lines with the default of their order.

        The lines whose amount was edited are left untouched: their fee is
        charged on the amount chosen by the user.
        """
        for order in self.sale_order_id:
            lines = order.credit_card_fee_line_ids
            if not lines:
                continue
            amount = order._credit_card_fee_default_amount()
            todo = lines.filtered(
                lambda line, value=amount: (
                    line.amount != value and not line.custom_amount
                )
            )
            if todo:
                todo.with_context(credit_card_fee_default_amount=True).write(
                    {"amount": amount}
                )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._set_default_amount()
        return lines

    def write(self, vals):
        if "amount" in vals and not self.env.context.get(
            "credit_card_fee_default_amount"
        ):
            # The amount was set explicitly: keep it and flag it as custom,
            # so it is not overwritten by the default of the order anymore.
            vals = dict(vals, custom_amount=True)
            return super().write(vals)
        res = super().write(vals)
        if "fee_range_id" in vals:
            # The fee of the order changed: every default amount changed too.
            self._set_default_amount()
        return res

    @api.depends(
        "amount",
        "fee_percent",
        "currency_id",
    )
    def _compute_fee_amount(self):
        for line in self:
            line.fee_amount = line.amount * (line.fee_percent or 0.0) / 100.0

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
