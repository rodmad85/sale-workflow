# Copyright (C) 2026 Madooit
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Recompute the credit card fee of the invoice plans.

    The fee of a plan used to be computed from the whole fee of the order,
    even the part of it whose Add Fee is off. It is now the fee the order
    really charges, so the stored values have to be refreshed.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    plans = env["sale.invoice.plan"].search(
        [("sale_id.credit_card_fee_line_ids", "!=", False)]
    )
    if not plans:
        return
    field = plans._fields["credit_card_fee_amount"]
    env.add_to_compute(field, plans)
    plans._recompute_recordset(["credit_card_fee_amount"])
