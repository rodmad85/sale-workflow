from psycopg2.sql import SQL, Identifier

import odoo.tools.sql as sql


def _copy_rel_table(
    cr, source, target, source_column, old_pm_column, target_column, map_table
):
    """Rebuild a many2many relation table against payment.method.

    source_column is the record side (sale_order_id / account_move_id),
    old_pm_column is the former sale.payment.method id column, and
    target_column is the new payment.method id column.
    """
    if sql.table_exists(cr, source):
        if not sql.table_exists(cr, target):
            cr.execute(
                SQL("CREATE TABLE {} ({} INT4 NOT NULL, {} INT4 NOT NULL)").format(
                    Identifier(target),
                    Identifier(source_column),
                    Identifier(target_column),
                )
            )
        cr.execute(
            SQL(
                "INSERT INTO {} ({}, {}) "
                "SELECT r.{}, m.new_id "
                "FROM {} r "
                "JOIN {} m ON m.old_id = r.{} "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM {} x "
                "WHERE x.{} = r.{} AND x.{} = m.new_id)"
            ).format(
                Identifier(target),
                Identifier(source_column),
                Identifier(target_column),
                Identifier(source_column),
                Identifier(source),
                Identifier(map_table),
                Identifier(old_pm_column),
                Identifier(target),
                Identifier(source_column),
                Identifier(source_column),
                Identifier(target_column),
            )
        )
        cr.execute(SQL("DROP TABLE IF EXISTS {}").format(Identifier(source)))


def migrate(cr, version):
    if not version or not sql.table_exists(cr, "l10n_br_ccf_pm_map"):
        return

    _copy_rel_table(
        cr,
        "sale_order_sale_payment_method_rel",
        "sale_order_payment_method_rel",
        "sale_order_id",
        "sale_payment_method_id",
        "payment_method_id",
        "l10n_br_ccf_pm_map",
    )
    _copy_rel_table(
        cr,
        "account_move_sale_payment_method_rel",
        "account_move_payment_method_rel",
        "account_move_id",
        "sale_payment_method_id",
        "payment_method_id",
        "l10n_br_ccf_pm_map",
    )

    cr.execute("DROP TABLE IF EXISTS l10n_br_ccf_pm_map")
