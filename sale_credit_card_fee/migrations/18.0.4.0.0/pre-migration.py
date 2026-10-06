# Copyright (C) 2026 Madooit
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from psycopg2.sql import SQL, Identifier

import odoo.tools.sql as sql

COLUMNS = [
    ("sale_order", "credit_card_fee_percent"),
    ("sale_create_invoice_plan", "credit_card_fee_percent"),
]


def migrate(cr, version):
    """Convert the fee percentage columns from Float to Char.

    sale.order.credit_card_fee_percent and the transient wizard field became
    Char fields, since the fees of every payment method of the order are
    displayed as a comma separated list (e.g. "2.5, 3.5").
    """
    if not version:
        return
    for table, column in COLUMNS:
        if not sql.table_exists(cr, table) or not sql.column_exists(cr, table, column):
            continue
        cr.execute(
            SQL("ALTER TABLE {} ALTER COLUMN {} TYPE varchar USING {}::varchar").format(
                Identifier(table),
                Identifier(column),
                Identifier(column),
            )
        )
