from odoo import api, fields, models


class CreditCardFeeRange(models.Model):
    _name = "credit.card.fee.range"
    _description = "Credit Card Fee Range by Installments"
    _order = "payment_method_id, installments_from"

    name = fields.Char(
        string="Range",
        compute="_compute_name",
    )
    payment_method_id = fields.Many2one(
        comodel_name="payment.method",
        string="Payment Method",
        required=True,
        ondelete="cascade",
    )
    installments_from = fields.Integer(required=True, default=1)
    installments_to = fields.Integer(required=True, default=1)
    fee_percent = fields.Float(
        string="Fee (%)",
        required=True,
        help="Credit card fee percentage for this installment range",
    )

    @api.depends("installments_from", "fee_percent")
    def _compute_name(self):
        for rec in self:
            rec.name = "%sX - %s%%" % (
                rec.installments_from,
                ("%.2f" % rec.fee_percent).replace(".", ","),
            )

    @api.constrains("installments_from", "installments_to")
    def _check_installments_range(self):
        for rec in self:
            if rec.installments_from < 1:
                rec.installments_from = 1
            if rec.installments_to < rec.installments_from:
                rec.installments_to = rec.installments_from