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
        by customer do, and the fees of the move are the fees of all of them.
        """
        self.ensure_one()
        return self.invoice_line_ids.sale_line_ids.order_id

    @api.depends(
        "invoice_line_ids.sale_line_ids.order_id",
        "invoice_line_ids.sale_line_ids.order_id.credit_card_fee_percent_sum",
        "invoice_line_ids.sale_line_ids.order_id.credit_card_fee_amount",
        "invoice_line_ids.sale_line_ids.order_id.credit_card_amount_plus_fee",
    )
    def _compute_credit_card_fee(self):
        for move in self:
            orders = move._credit_card_fee_orders()
            move.credit_card_fee_percent = sum(
                orders.mapped("credit_card_fee_percent_sum")
            )
            move.credit_card_fee_amount = sum(orders.mapped("credit_card_fee_amount"))
            move.credit_card_amount_plus_fee = sum(
                orders.mapped("credit_card_amount_plus_fee")
            )

    @api.depends(
        "invoice_line_ids.sale_line_ids.order_id.credit_card_fee_line_ids",
    )
    def _compute_credit_card_fee_lines(self):
        for move in self:
            move.credit_card_fee_line_ids = (
                move._credit_card_fee_orders().credit_card_fee_line_ids
            )
