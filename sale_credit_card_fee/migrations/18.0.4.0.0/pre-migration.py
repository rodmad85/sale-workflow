# Copyright (C) 2026 Madooit
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import odoo.tools.sql as sql


def migrate(cr, version):
    """Convert the sale order fee percentage column from Float to Char.

    sale.order.credit_card_fee_percent became a Char field, since the fees of
    every credit card of the order are displayed as a comma separated list
    (e.g. "2.5, 3.5"). The values are recomputed in the post-migration.
    """
    if not version:
        return
    if not sql.table_exists(cr, "sale_order"):
        return
    if not sql.column_exists(cr, "sale_order", "credit_card_fee_percent"):
        return
    sql.convert_column(cr, "sale_order", "credit_card_fee_percent", "varchar")
