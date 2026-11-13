from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    payment_method_ids = fields.Many2many(
        comodel_name="payment.method",
        relation="account_move_payment_method_rel",
        column1="account_move_id",
        column2="payment_method_id",
        string="Payment Methods",
    )
    credit_card_fee_percent = fields.Float(
        string="Fee (%)",
        compute="_compute_credit_card_fee",
    )
    credit_card_fee_amount = fields.Monetary(
        compute="_compute_credit_card_fee",
    )
    credit_card_amount_plus_fee = fields.Monetary(
        string="Amount + Fee",
        compute="_compute_credit_card_fee",
    )
    credit_card_fee_line_ids = fields.Many2many(
        comodel_name="sale.order.credit.card.fee.line",
        string="Card Administrator Fees",
        compute="_compute_credit_card_fee_lines",
        help="Credit card fee of every card administrator of the sale orders "
        "this invoice comes from, with the amount it is charged on and the "
        "fee itself. Read-only: the fee is set on the sale order.",
    )

    def _credit_card_fee_orders(self):
        """Return the sale orders the credit card fees of the move come from.

        An invoice can come from more than one sale order, as the ones grouped
        by customer do.
        """
        self.ensure_one()
        return self.invoice_line_ids.sale_line_ids.order_id

    def _credit_card_fee_product(self):
        """Return the product the credit card fee is invoiced with."""
        return self.env.ref("sale_credit_card_fee.product_credit_card_fee")

    def _credit_card_fee_invoice_lines(self):
        """Return the credit card fee lines this invoice is charged with.

        The fee of an invoice is what its fee product lines add up to. The
        invoice plan charges the proportional share of the fee of the order
        on each installment invoice only, so the down payment (entrada)
        invoice holds no fee line and is charged with no fee at all.
        """
        self.ensure_one()
        product = self._credit_card_fee_product()
        return self.invoice_line_ids.filtered(lambda line: line.product_id == product)

    @api.depends(
        "invoice_line_ids.product_id",
        "invoice_line_ids.price_subtotal",
        "invoice_line_ids.price_total",
        "invoice_line_ids.sale_line_ids.order_id",
        "invoice_line_ids.sale_line_ids.order_id.credit_card_fee_percent_sum",
        "amount_total",
    )
    def _compute_credit_card_fee(self):
        for move in self:
            # The fee of the invoice is the one it is really charged with,
            # not the whole fee of the sale orders it comes from: the down
            # payment invoice of an invoice plan has no fee of its own.
            move.credit_card_fee_amount = sum(
                move._credit_card_fee_invoice_lines().mapped("price_total")
            )
            # The amount plus the fee is the final value of the invoice,
            # whose fee line is already part of its total.
            move.credit_card_amount_plus_fee = move.amount_total
            move.credit_card_fee_percent = sum(
                move._credit_card_fee_orders().mapped("credit_card_fee_percent_sum")
            )

    @api.depends(
        "invoice_line_ids.sale_line_ids.order_id.credit_card_fee_line_ids",
    )
    def _compute_credit_card_fee_lines(self):
        for move in self:
            move.credit_card_fee_line_ids = (
                move._credit_card_fee_orders().credit_card_fee_line_ids
            )
