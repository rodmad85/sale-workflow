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
        help="Amount the fee of this payment method is charged on. The fee "
        "is charged on top of that amount, so the amounts of the lines of an "
        "order add up to the total of the order, taxes included. The whole of "
        "that amount is charged on the first line by default and a line added "
        "to an order that already has one starts with no amount at all. "
        "Editing it gives that amount to the line, which is then taken from "
        "the lines that still follow the order.",
    )
    custom_amount = fields.Boolean(
        default=False,
        help="Keep the amount of this line when the order total or the "
        "credit card fees change.",
    )
    edited_amount = fields.Boolean(
        string="Amount Edited",
        store=False,
        copy=False,
        default=False,
        help="Technical field set while the user edits the amount of this "
        "line, so that the checks of the listing take the difference from "
        "the other lines of the order.",
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
    def _share_amount(self, lines, amount):
        """Return the amounts of ``lines`` holding ``amount`` together.

        What the lines have to gain or to give is shared equally between
        them, so every line gets the same share of the change:

        - a change taking them below zero is taken from the lines that hold
          enough of it, the smallest ones first, and what is left is shared
          again with the lines that can still give their share;
        - the rounding of the currency is left to the last line.
        """
        if not lines:
            return []
        current = sum(lines.mapped("amount"))
        difference = amount - current
        if not difference:
            return list(lines.mapped("amount"))
        currency = lines[:1].currency_id
        if difference > 0.0:
            share = currency.round(difference / len(lines))
            values = [line.amount + share for line in lines[:-1]]
            values.append(lines[-1].amount + difference - share * (len(lines) - 1))
            return values
        left = -difference
        values = {line: line.amount for line in lines}
        # the smallest amounts are the ones running out of their share first
        pending = lines.sorted("amount")
        for line in pending:
            if not left or not pending:
                break
            share = min(line.amount, currency.round(left / len(pending)))
            values[line] = line.amount - share
            left -= share
            pending = pending - line
        return [values[line] for line in lines]

    @api.model
    def _amount_within_order(self, lines, amount):
        """Return the amount the given lines can hold of the order.

        The amounts of the lines of an order add up to the total of the order,
        taxes included, and the other lines can give up everything they hold,
        so a line can never hold more than that total.
        """
        total = lines[:1].sale_order_id._credit_card_fee_default_amount()
        return max(min(amount, total / max(len(lines), 1)), 0.0)

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

    def _check_amounts(self, edited=None):
        """Keep the amounts of the lines adding up to the total of the order.

        The amounts of the fee lines of an order add up to the total of the
        order, taxes included, the fee of each card being charged on top of
        the amount charged on it:

        - when the user edits an amount, the other lines share what is left
          of that total equally, so the amounts can never add up to more than
          it;
        - when the order changes, the lines whose amount was edited keep it
          and what is left of the total goes to the first line that still
          follows the order, the other ones being left with no amount.
        """
        for order in self.sale_order_id:
            lines = order.credit_card_fee_line_ids
            if not lines:
                continue
            total = order._credit_card_fee_default_amount()
            if edited:
                # The user chose amounts: the other lines share what is left
                # of the total of the order between them, equally.
                others = lines - edited
                values = self._share_amount(
                    others, total - sum(edited.mapped("amount"))
                )
                self._write_amount(list(zip(others, values, strict=False)))
            else:
                # Nothing was just edited: the amounts chosen by the user are
                # kept and the first line still following the order takes
                # what is left of the total of the order.
                edited = lines.filtered("custom_amount")
                following = lines - edited
                rest = max(total - sum(edited.mapped("amount")), 0.0)
                values = [rest] + [0.0] * (len(following) - 1)
                self._write_amount(list(zip(following, values, strict=False)))
            if sum(edited.mapped("amount")) > total:
                # The amounts chosen do not fit in the total of the order:
                # they share what is left of it, equally.
                self._write_amount(
                    list(zip(edited, self._share_amount(edited, total), strict=False))
                )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_amounts()
        return lines

    @api.onchange("amount")
    def _onchange_amount(self):
        """Flag an amount edited by the user as chosen by hand.

        The line then stops following the order: what it gains is taken from
        the other lines and what it gives up goes to them, shared equally.
        The marker tells the onchange of the order which line the user has
        just edited, so that only that one keeps its amount.
        """
        self.custom_amount = True
        self.edited_amount = True

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
                        "amount": self._amount_within_order(edited, vals["amount"]),
                    }
                )
                moved = edited.filtered(
                    lambda line, previous=previous: line.amount != previous[line]
                )
                if moved:
                    moved.custom_amount = True
                    self._check_amounts(edited=moved)
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
