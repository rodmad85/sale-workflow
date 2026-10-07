from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    payment_method_ids = fields.Many2many(
        comodel_name="payment.method",
        relation="sale_order_payment_method_rel",
        column1="sale_order_id",
        column2="payment_method_id",
        string="Payment Methods",
    )

    credit_card_fee_line_ids = fields.One2many(
        comodel_name="sale.order.credit.card.fee.line",
        inverse_name="sale_order_id",
        string="Card Administrator Fees",
        copy=True,
    )
    credit_card_fee_percent = fields.Char(
        string="Fee (%)",
        compute="_compute_credit_card_fee",
        store=True,
        readonly=True,
        copy=False,
        help="Fee of every credit card of the order, separated by commas.",
    )
    credit_card_fee_percent_sum = fields.Float(
        string="Fee (%) Sum",
        compute="_compute_credit_card_fee",
        store=True,
        readonly=True,
        copy=False,
        help="Sum of the fees of every credit card of the order.",
    )
    credit_card_fee_amount = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        help="Sum of the fee amount of the credit card fee lines.",
    )
    credit_card_amount_plus_fee = fields.Monetary(
        string="Amount + Fee",
        compute="_compute_amounts",
        store=True,
    )

    @api.onchange("payment_method_ids")
    def _onchange_payment_method_ids(self):
        card_admins = self.payment_method_ids.filtered("credit_card_admin")
        lines = self.env["sale.order.credit.card.fee.line"]
        percent = next(
            (
                line.fee_percent
                for line in self.credit_card_fee_line_ids
                if line.payment_method_id in card_admins
            ),
            0.0,
        )
        # The whole order is charged on the first fee line: the lines added
        # after it start with no amount at all.
        amount = lines._amount_of_net(self._credit_card_fee_base(), percent)
        commands = [(5, 0, 0)]
        amounts = [amount] + [0.0] * (len(card_admins) - 1)
        for method, value in zip(card_admins, amounts, strict=False):
            commands.append((0, 0, {"payment_method_id": method.id, "amount": value}))
        self.credit_card_fee_line_ids = commands

    @api.onchange("credit_card_fee_line_ids")
    def _onchange_credit_card_fee_line_ids(self):
        """Check the amounts of the fee lines as they are changed.

        The amount the user just edited is kept and the other lines share
        what is left of the total of the order between them, equally, without
        waiting for the order to be saved.
        """
        lines = self.credit_card_fee_line_ids
        lines._check_amounts(edited=lines.filtered("edited_amount"))
        lines.write({"edited_amount": False})

    def _sync_credit_card_fee_lines(self):
        """Keep one fee line per selected card administrator payment method."""
        for order in self:
            card_admins = order.payment_method_ids.filtered("credit_card_admin")
            existing = order.credit_card_fee_line_ids.mapped("payment_method_id")
            for method in card_admins - existing:
                self.env["sale.order.credit.card.fee.line"].create(
                    {
                        "sale_order_id": order.id,
                        "payment_method_id": method.id,
                    }
                )
            lines_to_remove = order.credit_card_fee_line_ids.filtered(
                lambda line, admins=card_admins: (line.payment_method_id not in admins)
            )
            if lines_to_remove:
                lines_to_remove.unlink()

    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._sync_credit_card_fee_lines()
        orders.credit_card_fee_line_ids._check_amounts()
        return orders

    def write(self, vals):
        if "credit_card_fee_line_ids" in vals:
            # The amounts that come with the fee lines are the ones the
            # checks of the module produced, either by the onchange of the
            # form or by the checks themselves: write them as they are, the
            # lines edited by the user being the ones flagged as custom, and
            # only check that they fit in the total of the order.
            orders = self.with_context(credit_card_fee_sync_amount=True)
            res = super(SaleOrder, orders).write(vals)
            self.credit_card_fee_line_ids._cap_amounts()
            return res
        res = super().write(vals)
        if vals.get("payment_method_ids"):
            self._sync_credit_card_fee_lines()
        self.credit_card_fee_line_ids._check_amounts()
        return res

    def _credit_card_fee_base(self):
        """Return the order amount the credit card fees are charged on.

        The fees are charged on the taxed total without them, so the base is
        the same for every fee line and does not depend on the fee itself.
        """
        self.ensure_one()
        return self.amount_untaxed + self.amount_tax

    def _credit_card_fee_default_amount(self):
        """Return the amount the fee lines of the order add up to by default.

        The fee lines add up to the total of the order, taxes and credit card
        fees included, which is what they leave of the order once their own
        fee is taken. By default the whole of that amount is charged on the
        first fee line, the other ones having no amount at all.
        """
        self.ensure_one()
        lines = self.env["sale.order.credit.card.fee.line"]
        percent = self.credit_card_fee_line_ids[:1].fee_percent
        return lines._amount_of_net(self._credit_card_fee_base(), percent)

    @api.depends(
        "credit_card_fee_line_ids",
        "credit_card_fee_line_ids.fee_percent",
    )
    def _compute_credit_card_fee(self):
        fee_lines = self.env["sale.order.credit.card.fee.line"]
        for order in self:
            percents = order.credit_card_fee_line_ids.mapped("fee_percent")
            order.credit_card_fee_percent = fee_lines._format_fee_percents(percents)
            order.credit_card_fee_percent_sum = sum(percents)

    @api.depends(
        "order_line.price_subtotal",
        "order_line.price_total",
        "amount_tax",
        "currency_id",
        "company_id",
        "payment_term_id",
        "credit_card_fee_line_ids",
        "credit_card_fee_line_ids.sum_fee",
        "credit_card_fee_line_ids.fee_amount",
    )
    def _compute_amounts(self):
        res = super()._compute_amounts()
        for order in self:
            fee = sum(order.credit_card_fee_line_ids.mapped("fee_amount"))
            fee_to_add = sum(
                order.credit_card_fee_line_ids.filtered("sum_fee").mapped("fee_amount")
            )
            order.credit_card_fee_amount = fee
            order.amount_total += fee_to_add
            order.credit_card_amount_plus_fee = order._credit_card_fee_base() + fee
        return res

    def _create_invoices(self, grouped=False, final=False, date=None):
        moves = super()._create_invoices(grouped=grouped, final=final, date=date)
        plan = self.env["sale.invoice.plan"].browse(
            self.env.context.get("invoice_plan_id") or 0
        )
        product = self.env.ref("sale_credit_card_fee.product_credit_card_fee")
        for order in self:
            fee_lines = order.credit_card_fee_line_ids.filtered(
                lambda line: line.sum_fee and line.fee_amount
            )
            lines_fee = sum(fee_lines.mapped("fee_amount"))
            if not lines_fee:
                continue
            if plan.exists():
                if plan.sale_id != order or not plan.credit_card_fee_amount:
                    continue
                fee_amount = plan.credit_card_fee_amount
            else:
                fee_amount = order.credit_card_fee_amount
            if not fee_amount:
                continue
            for move in moves:
                if move.move_type != "out_invoice":
                    continue
                if not move.invoice_line_ids.sale_line_ids.filtered(
                    lambda line, order=order: line.order_id == order
                ):
                    continue
                if move.invoice_line_ids.filtered(
                    lambda line: line.product_id == product
                ):
                    continue
                lines = []
                for fee_line in fee_lines:
                    lines.append(
                        (
                            0,
                            0,
                            {
                                "product_id": product.id,
                                "name": self.env._("Credit Card Fee (%s%%) - %s")
                                % (
                                    fee_line.fee_percent,
                                    fee_line.payment_method_id.name,
                                ),
                                "quantity": 1,
                                "price_unit": fee_amount
                                * fee_line.fee_amount
                                / lines_fee,
                                "tax_ids": [(5, 0, 0)],
                            },
                        )
                    )
                move.write({"invoice_line_ids": lines})
        return moves
