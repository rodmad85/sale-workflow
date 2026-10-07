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
        "order that already has one starts at zero: what a line is given is "
        "taken from the lines that still follow the order, so the amounts of "
        "an order keep adding up to its total, and an amount that does not "
        "fit in that total is capped to it.",
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
    def _amount_within_total(self, lines, amount):
        """Return the amount the given lines can hold of the order total.

        The lines take what is left of the total of the order once the lines
        whose amount was edited keep theirs, so that the amounts of the lines
        of an order never add up to more than that total.
        """
        order = lines[:1].sale_order_id
        kept = sum(
            (order.credit_card_fee_line_ids - lines)
            .filtered("custom_amount")
            .mapped("amount")
        )
        room = max(order._credit_card_fee_default_amount() - kept, 0.0)
        return max(min(amount, room / len(lines)), 0.0)

    def _write_amount(self, pairs):
        """Write the given ``(line, amount)`` pairs from the module itself.

        The amounts set by the module do not make a line stop following the
        order, so they are written with a context telling it apart from the
        amounts chosen by the user.
        """
        for line, value in pairs:
            if line.amount != value:
                line.with_context(credit_card_fee_sync_amount=True).write(
                    {"amount": value}
                )

    def _check_amounts(self):
        """Make the amounts of the lines add up to the total of the order.

        The amounts of the fee lines of an order add up to the amount the
        order is charged on as a whole, taxes and credit card fees included:

        - the lines whose amount was edited keep it, and when they hold more
          than the order together the smallest ones are kept: the amount
          edited last, which is the one that went over, is cut back;
        - what is left of the total goes to the first line that still follows
          the order, the other ones being left with no amount at all.
        """
        for order in self.sale_order_id:
            lines = order.credit_card_fee_line_ids
            if not lines:
                continue
            total = order._credit_card_fee_default_amount()
            edited = lines.filtered("custom_amount")
            edited_amount = sum(edited.mapped("amount"))
            pairs = []
            if edited_amount > total:
                # The amounts chosen hold more than the order: what is left of
                # it is shared, the smallest amounts first.
                left = total
                for line in edited.sorted("amount"):
                    pairs.append((line, min(line.amount, left)))
                    left = max(left - line.amount, 0.0)
                edited_amount = total - left
            following = lines - edited
            if following:
                rest = max(total - edited_amount, 0.0)
                values = [rest] + [0.0] * (len(following) - 1)
                pairs += list(zip(following, values, strict=False))
            self._write_amount(pairs)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_amounts()
        return lines

    @api.onchange("amount")
    def _onchange_amount(self):
        """Flag an amount edited by the user as chosen by hand.

        The line then stops following the order: what it gains is taken from
        the other lines and what it gives up goes to the line that still
        follows the order.
        """
        self.custom_amount = True

    def write(self, vals):
        if "amount" in vals and not self.env.context.get("credit_card_fee_sync_amount"):
            # The amounts were set explicitly: they never go over what is
            # left of the total of the order, and the lines whose amount
            # really moves stop following the order.
            for order in self.sale_order_id:
                edited = self.filtered(
                    lambda line, order=order: line.sale_order_id == order
                )
                previous = {line: line.amount for line in edited}
                super(SaleOrderCreditCardFeeLine, edited).write(
                    {
                        **vals,
                        "amount": self._amount_within_total(edited, vals["amount"]),
                    }
                )
                moved = edited.filtered(
                    lambda line, previous=previous: line.amount != previous[line]
                )
                if moved:
                    moved.custom_amount = True
                    self._check_amounts()
            return True
        res = super().write(vals)
        if "fee_range_id" in vals:
            # The fee of the order changed: every default amount changed too.
            self._check_amounts()
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
