# Copyright (C) 2026 Madooit
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import SUPERUSER_ID, api


def _recompute(env, model_name, domain, field_names):
    """Recompute and store the given fields of the records of a model."""
    records = env[model_name].search(domain)
    if not records:
        return
    fields = [records._fields[name] for name in field_names]
    for field in fields:
        env.add_to_compute(field, records)
    records._recompute_recordset(field_names)


def migrate(cr, version):
    """Fill the amount and the fee amount of the existing credit card fee lines.

    The fee lines now carry the amount the fee is charged on and the resulting
    fee amount, the fee of the sale order is the sum of the fee amounts of its
    lines and its fee percentages became a comma separated list. Orders created
    with the previous version have no such values, so the fee lines and the
    aggregates of the orders are filled here.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env["sale.order"].search([("credit_card_fee_line_ids", "!=", False)])
    if not orders:
        return
    cr.execute(
        "UPDATE sale_order_credit_card_fee_line "
        "SET custom_amount = FALSE WHERE custom_amount IS NULL"
    )
    orders.credit_card_fee_line_ids._check_amounts()
    _recompute(
        env,
        "sale.order.credit.card.fee.line",
        [("sale_order_id", "!=", False)],
        ["fee_amount"],
    )
    _recompute(
        env,
        "sale.order",
        [("credit_card_fee_line_ids", "!=", False)],
        [
            "credit_card_fee_percent",
            "credit_card_fee_percent_sum",
            "credit_card_fee_amount",
            "credit_card_amount_plus_fee",
            "amount_total",
        ],
    )
    _recompute(
        env,
        "sale.invoice.plan",
        [("sale_id.credit_card_fee_line_ids", "!=", False)],
        ["credit_card_fee_amount"],
    )
