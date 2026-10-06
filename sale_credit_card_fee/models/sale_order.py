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
    credit_card_fee_percent = fields.Float(
        string="Fee (%)",
        compute="_compute_credit_card_fee",
        store=True,
        readonly=True,
        copy=False,
    )
    credit_card_fee_amount = fields.Monetary(
        compute="_compute_amounts",
        store=True,
    )
    credit_card_amount_plus_fee = fields.Monetary(
        string="Amount + Fee",
        compute="_compute_amounts",
        store=True,
    )

    @api.onchange("payment_method_ids")
    def _onchange_payment_method_ids(self):
        card_admins = self.payment_method_ids.filtered("credit_card_admin")
        commands = [(5, 0, 0)]
        for method in card_admins:
            commands.append((0, 0, {"payment_method_id": method.id}))
        self.credit_card_fee_line_ids = commands

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
        return orders

    def write(self, vals):
        res = super().write(vals)
        if vals.get("payment_method_ids"):
            self._sync_credit_card_fee_lines()
        return res

    @api.depends(
        "credit_card_fee_line_ids",
        "credit_card_fee_line_ids.fee_percent",
    )
    def _compute_credit_card_fee(self):
        for order in self:
            percent = sum(
                (line.fee_percent or 0.0) for line in order.credit_card_fee_line_ids
            )
            order.credit_card_fee_percent = percent

    @api.depends(
        "order_line.price_subtotal",
        "order_line.price_total",
        "amount_tax",
        "currency_id",
        "company_id",
        "payment_term_id",
        "credit_card_fee_line_ids",
        "credit_card_fee_line_ids.sum_fee",
        "credit_card_fee_line_ids.fee_percent",
    )
    def _compute_amounts(self):
        res = super()._compute_amounts()
        for order in self:
            base = order.amount_untaxed + order.amount_tax
            fee = 0.0
            fee_to_add = 0.0
            for line in order.credit_card_fee_line_ids:
                line_fee = base * (line.fee_percent or 0.0) / 100.0
                fee += line_fee
                if line.sum_fee:
                    fee_to_add += line_fee
            order.credit_card_fee_amount = fee
            order.amount_total += fee_to_add
            order.credit_card_amount_plus_fee = base + fee
        return res

    def _create_invoices(self, grouped=False, final=False, date=None):
        moves = super()._create_invoices(grouped=grouped, final=final, date=date)
        plan = self.env["sale.invoice.plan"].browse(
            self.env.context.get("invoice_plan_id") or 0
        )
        product = self.env.ref("sale_credit_card_fee.product_credit_card_fee")
        for order in self:
            fee_lines = order.credit_card_fee_line_ids.filtered("sum_fee")
            if not fee_lines or not order.credit_card_fee_percent:
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
                                * fee_line.fee_percent
                                / order.credit_card_fee_percent,
                                "tax_ids": [(5, 0, 0)],
                            },
                        )
                    )
                move.write({"invoice_line_ids": lines})
        return moves
