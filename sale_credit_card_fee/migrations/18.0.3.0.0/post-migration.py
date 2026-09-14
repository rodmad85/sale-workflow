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
                "CREATE TABLE %s (%s INT4 NOT NULL, %s INT4 NOT NULL)"
                % (target, source_column, target_column)
            )
        cr.execute(
            "INSERT INTO %s (%s, %s) "
            "SELECT r.%s, m.new_id "
            "FROM %s r "
            "JOIN %s m ON m.old_id = r.%s "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM %s x "
            "WHERE x.%s = r.%s AND x.%s = m.new_id)"
            % (
                target,
                source_column,
                target_column,
                source_column,
                source,
                map_table,
                old_pm_column,
                target,
                source_column,
                source_column,
                target_column,
            )
        )
        cr.execute("DROP TABLE IF EXISTS %s" % source)


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