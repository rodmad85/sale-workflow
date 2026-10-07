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
        "defaults to the order total plus the credit card fee and follows "
        "the order until it is edited. The amount of a line added to an "
        "order that already has one starts at zero and what it is given is "
        "taken from the other lines, so the amounts of an order never add up "
        "to more than its total.",
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

    @api.model
    def _spread_amount(self, lines, amount):
        """Return the amounts of ``lines`` once ``amount`` is taken from them.

        The amount is spread over the lines, proportionally to their amounts,
        and no line goes below zero. The rounding of the currency is left to
        the last line, so the amounts always add up to what is left of the
        total of the order.
        """
        currency = lines[:1].currency_id
        total = sum(lines.mapped("amount"))
        if total <= 0.0:
            return [0.0] * len(lines)
        values = [
            currency.round(max(line.amount - amount * line.amount / total, 0.0))
            for line in lines[:-1]
        ]
        values.append(max(currency.round(total - amount - sum(values)), 0.0))
        return values

    def _set_default_amount(self):
        """Set the amount of the fee lines that follow their order.

        The fee lines of an order share the amount it is charged on as a
        whole, taxes and credit card fees included: the lines whose amount
        was edited keep it and what is left of that total goes to the first
        line still following the order, the other ones being left with no
        amount at all.
        """
        for order in self.sale_order_id:
            lines = order.credit_card_fee_line_ids
            following = lines.filtered(lambda line: not line.custom_amount)
            if not following:
                # Every amount was chosen by the user: keep all of them.
                continue
            edited = lines - following
            amount = max(
                order._credit_card_fee_default_amount() - sum(edited.mapped("amount")),
                0.0,
            )
            values = [amount] + [0.0] * (len(following) - 1)
            for line, value in zip(following, values, strict=False):
                if line.amount != value:
                    line.with_context(credit_card_fee_sync_amount=True).write(
                        {"amount": value}
                    )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._set_default_amount()
        return lines

    def write(self, vals):
        if "amount" in vals and not self.env.context.get("credit_card_fee_sync_amount"):
            # The amount was set explicitly: the line stops following the
            # order and what it gains is taken from the other lines.
            return self._write_custom_amount(vals)
        res = super().write(vals)
        if "fee_range_id" in vals:
            # The fee of the order changed: every default amount changed too.
            self._set_default_amount()
        return res

    def _write_custom_amount(self, vals):
        """Write an amount chosen by the user, keeping the total of the order.

        What the edited lines gain is taken from the other lines of the order,
        in proportion to the amount they hold, so the amounts never add up to
        more than the total of the order: an amount bigger than what the other
        lines hold is capped to that total.
        """
        lines = self.env["sale.order.credit.card.fee.line"]
        for order in self.sale_order_id:
            edited = self.filtered(
                lambda line, order=order: line.sale_order_id == order
            )
            others = order.credit_card_fee_line_ids - edited
            values = {**vals, "custom_amount": True}
            if not others:
                # A single fee line is charged on the amount of the user.
                edited.with_context(credit_card_fee_sync_amount=True).write(values)
                continue
            current = sum(edited.mapped("amount"))
            available = sum(others.mapped("amount"))
            amount = min(vals["amount"], (current + available) / len(edited))
            edited.with_context(credit_card_fee_sync_amount=True).write(
                {**values, "amount": amount}
            )
            difference = len(edited) * amount - current
            if not difference:
                continue
            for line, value in zip(
                others, lines._spread_amount(others, difference), strict=False
            ):
                line.with_context(credit_card_fee_sync_amount=True).write(
                    {"amount": value}
                )
        return True

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
