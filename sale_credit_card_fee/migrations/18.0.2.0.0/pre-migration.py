import json

import odoo.tools.sql as sql


def _get_admin_user_id(cr):
    cr.execute("SELECT id FROM res_users ORDER BY id LIMIT 1")
    return cr.fetchone()[0]


def migrate(cr, version):
    if not version:
        return
    if not sql.table_exists(cr, "credit_card_admin"):
        return
    uid = _get_admin_user_id(cr)

    # Build a payment method per card administrator, reusing an existing
    # link when there is already a payment method pointing to the admin.
    cr.execute("SELECT id, name FROM credit_card_admin WHERE active IS NOT FALSE")
    admins = cr.fetchall()
    if not admins:
        return

    pm_by_admin = {}
    for admin_id, name in admins:
        cr.execute(
            "SELECT id FROM sale_payment_method "
            "WHERE credit_card_admin_id = %s LIMIT 1",
            (admin_id,),
        )
        row = cr.fetchone()
        if not row:
            name_json = json.dumps({"en_US": name})
            cr.execute(
                "INSERT INTO sale_payment_method "
                "(name, sequence, active, credit_card_admin_id, create_uid,"
                "create_date, write_uid, write_date) "
                "VALUES (%s, 10, TRUE, %s, %s, now(), %s, now()) RETURNING id",
                (name_json, admin_id, uid, uid),
            )
            row = cr.fetchone()
        pm_by_admin[admin_id] = row[0]

    cr.execute("DROP TABLE IF EXISTS l10n_br_ccf_mig_admin")
    cr.execute(
        "CREATE TABLE l10n_br_ccf_mig_admin ("
        "admin_id INT4 PRIMARY KEY, payment_method_id INT4)"
    )
    for admin_id, pm_id in pm_by_admin.items():
        cr.execute(
            "INSERT INTO l10n_br_ccf_mig_admin VALUES (%s, %s)",
            (admin_id, pm_id),
        )

    # Move the fee ranges from the administrator to the payment method.
    if not sql.column_exists(cr, "credit_card_fee_range", "payment_method_id"):
        cr.execute(
            "ALTER TABLE credit_card_fee_range " "ADD COLUMN payment_method_id INT4"
        )
    cr.execute(
        """
        UPDATE credit_card_fee_range r
        SET payment_method_id = m.payment_method_id
        FROM l10n_br_ccf_mig_admin m
        WHERE r.admin_id = m.admin_id
        """
    )
    cr.execute(
        "SELECT COUNT(*) FROM credit_card_fee_range " "WHERE payment_method_id IS NULL"
    )
    if cr.fetchone()[0]:
        cr.execute("SELECT payment_method_id FROM l10n_br_ccf_mig_admin LIMIT 1")
        fallback = cr.fetchone()[0]
        if fallback:
            cr.execute(
                "UPDATE credit_card_fee_range SET payment_method_id = %s "
                "WHERE payment_method_id IS NULL",
                (fallback,),
            )
    sql.set_not_null(cr, "credit_card_fee_range", "payment_method_id")

    # Capture the orders using a card administrator so the fee lines can be
    # restored in the post-migration, after the old columns are dropped.
    cr.execute("DROP TABLE IF EXISTS l10n_br_ccf_mig_order")
    cr.execute(
        """
        CREATE TABLE l10n_br_ccf_mig_order AS
        SELECT o.id AS sale_order_id,
               m.payment_method_id,
               COALESCE(o.credit_card_sum_fee, TRUE) AS sum_fee,
               o.credit_card_fee_range_id AS fee_range_id
        FROM sale_order o
        JOIN l10n_br_ccf_mig_admin m ON m.admin_id = o.credit_card_admin_id
        WHERE o.credit_card_admin_id IS NOT NULL
        """
    )
