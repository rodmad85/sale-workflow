from odoo import fields, models


class PaymentMethod(models.Model):
    _inherit = "payment.method"

    credit_card_admin = fields.Boolean(
        string="Card Administrator",
        help="Mark this payment method as a credit card administrator to "
        "configure the credit card fee ranges used in sale orders.",
    )
    fee_line_ids = fields.One2many(
        comodel_name="credit.card.fee.range",
        inverse_name="payment_method_id",
        string="Fee Ranges",
    )
