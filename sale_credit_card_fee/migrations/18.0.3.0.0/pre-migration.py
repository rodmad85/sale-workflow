import json
import re

from psycopg2.sql import SQL, Identifier

import odoo.tools.sql as sql


def _get_admin_user_id(cr):
    cr.execute("SELECT id FROM res_users ORDER BY id LIMIT 1")
    return cr.fetchone()[0]


def _slug(name):
    slug = re.sub(r"[^0-9a-z]+", "_", name.lower()).strip("_")
    return slug or "payment_method"


def migrate(cr, version):
    if not version:
        return
    uid = _get_admin_user_id(cr)

    # Drop the views inherited on the former model: they now reference a
    # field that no longer exists on sale.payment.method. Their XML
    # definitions were removed from the module in this version.
    for xmlid in (
        "view_sale_payment_method_form_inherit_card_fee",
        "view_sale_payment_method_tree_inherit_card_fee",
    ):
        cr.execute(
            "SELECT id FROM ir_model_data "
            "WHERE module = 'l10n_br_sale_credit_card_fee' AND name = %s "
            "AND model = 'ir.ui.view'",
            (xmlid,),
        )
        row = cr.fetchone()
        if row:
            cr.execute("DELETE FROM ir_ui_view WHERE id = %s", (row[0],))
            cr.execute(
                "DELETE FROM ir_model_data "
                "WHERE module = 'l10n_br_sale_credit_card_fee' AND name = %s "
                "AND model = 'ir.ui.view'",
                (xmlid,),
            )

    # Make sure the image and fee columns exist before inserting new rows:
    # the module load below would create them anyway when it auto-inits
    # the payment.method model, but the pre-migration must not depend on that.
    cr.execute("ALTER TABLE payment_method ADD COLUMN IF NOT EXISTS image bytea")
    cr.execute(
        "ALTER TABLE payment_method "
        "ADD COLUMN IF NOT EXISTS image_payment_form bytea"
    )
    cr.execute(
        "ALTER TABLE payment_method "
        "ADD COLUMN IF NOT EXISTS credit_card_admin boolean"
    )

    # Create a payment.method record for each former sale.payment.method
    # and keep the mapping so the fee ranges and fee lines can follow.
    cr.execute("DROP TABLE IF EXISTS l10n_br_ccf_pm_map")
    cr.execute(
        "CREATE TABLE l10n_br_ccf_pm_map (" "old_id INT4 PRIMARY KEY, new_id INT4)"
    )
    cr.execute(
        "SELECT id, name, sequence, active, COALESCE(credit_card_admin, FALSE) "
        "FROM sale_payment_method ORDER BY id"
    )
    for old_id, name, sequence, active, credit_card_admin in cr.fetchall():
        name = name or {}
        en_name = name.get("en_US") or name.get("pt_BR") or "Payment Method"
        code = _slug(en_name)
        cr.execute("SELECT 1 FROM payment_method WHERE code = %s LIMIT 1", (code,))
        if cr.fetchone():
            code = f"{code}_{old_id}"
        cr.execute(
            "INSERT INTO payment_method "
            "(name, code, sequence, active, support_refund, credit_card_admin, "
            "create_date, create_uid, write_date, write_uid) "
            "VALUES (%s, %s, %s, %s, 'none', %s, now(), %s, now(), %s) "
            "RETURNING id",
            (
                json.dumps({"en_US": en_name}),
                code,
                sequence if sequence is not None else 1,
                active if active is not None else True,
                bool(credit_card_admin),
                uid,
                uid,
            ),
        )
        new_id = cr.fetchone()[0]
        cr.execute("INSERT INTO l10n_br_ccf_pm_map VALUES (%s, %s)", (old_id, new_id))

    # Drop the old foreign keys before remapping the rows: they still
    # reference sale_payment_method and would reject the new values.
    for table in ("credit_card_fee_range", "sale_order_credit_card_fee_line"):
        if sql.table_exists(cr, table):
            cr.execute(
                SQL("ALTER TABLE {} DROP CONSTRAINT IF EXISTS {}").format(
                    Identifier(table),
                    Identifier(f"{table}_payment_method_id_fkey"),
                )
            )

    # Point the fee ranges and the sale order fee lines at the new records.
    cr.execute(
        "UPDATE credit_card_fee_range r "
        "SET payment_method_id = m.new_id "
        "FROM l10n_br_ccf_pm_map m "
        "WHERE r.payment_method_id = m.old_id"
    )
    cr.execute(
        "UPDATE sale_order_credit_card_fee_line l "
        "SET payment_method_id = m.new_id "
        "FROM l10n_br_ccf_pm_map m "
        "WHERE l.payment_method_id = m.old_id"
    )
