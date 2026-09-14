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

    @api.depends("invoice_line_ids.sale_line_ids.order_id")
    def _compute_credit_card_fee(self):
        for move in self:
            order = move.invoice_line_ids.sale_line_ids.order_id[:1]
            move.credit_card_fee_percent = order.credit_card_fee_percent or 0.0
            move.credit_card_fee_amount = order.credit_card_fee_amount or 0.0
            move.credit_card_amount_plus_fee = order.credit_card_amount_plus_fee or 0.0
