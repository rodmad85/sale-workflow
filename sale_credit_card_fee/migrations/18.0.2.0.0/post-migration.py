import odoo.tools.sql as sql


def _get_admin_user_id(cr):
    cr.execute("SELECT id FROM res_users ORDER BY id LIMIT 1")
    return cr.fetchone()[0]


def migrate(cr, version):
    if not version:
        return
    if not sql.table_exists(cr, "l10n_br_ccf_mig_admin"):
        return
    uid = _get_admin_user_id(cr)

    # Flag the migrated payment methods as card administrators.
    cr.execute(
        """
        UPDATE sale_payment_method
        SET credit_card_admin = TRUE
        WHERE id IN (SELECT payment_method_id FROM l10n_br_ccf_mig_admin)
        """
    )

    # Restore the card administrator fee lines on the migrated orders.
    if sql.table_exists(cr, "l10n_br_ccf_mig_order") and sql.table_exists(
        cr, "sale_order_credit_card_fee_line"
    ):
        cr.execute(
            """
            INSERT INTO sale_order_credit_card_fee_line
                (sale_order_id, payment_method_id, sum_fee, fee_range_id,
                 fee_percent, create_uid, create_date, write_uid, write_date)
            SELECT o.sale_order_id, o.payment_method_id, o.sum_fee,
                   o.fee_range_id, COALESCE(r.fee_percent, 0.0),
                   %s, now(), %s, now()
            FROM l10n_br_ccf_mig_order o
            LEFT JOIN credit_card_fee_range r ON r.id = o.fee_range_id
            """,
            (uid, uid),
        )
        # Recompute the stored aggregates: the old columns kept their
        # pre-upgrade values and the fee lines were never seen by the ORM.
        cr.execute(
            """
            UPDATE sale_order o
            SET credit_card_fee_percent = COALESCE((
                    SELECT SUM(l.fee_percent)
                    FROM sale_order_credit_card_fee_line l
                    WHERE l.sale_order_id = o.id AND l.sum_fee
                ), 0.0)
            WHERE o.id IN (
                SELECT sale_order_id FROM l10n_br_ccf_mig_order
            )
            """
        )
        cr.execute(
            """
            UPDATE sale_order o
            SET credit_card_fee_amount =
                    ROUND((o.amount_untaxed * o.credit_card_fee_percent
                           / 100.0)::numeric, 2),
                credit_card_amount_plus_fee =
                    ROUND((o.amount_total + o.amount_untaxed
                           * o.credit_card_fee_percent / 100.0)::numeric, 2)
            WHERE o.id IN (
                SELECT sale_order_id FROM l10n_br_ccf_mig_order
            )
            """
        )
        cr.execute(
            """
            UPDATE sale_invoice_plan p
            SET credit_card_fee_amount = CASE
                    WHEN p.invoice_type = 'installment'
                         AND o.credit_card_fee_amount > 0
                    THEN ROUND(o.credit_card_fee_amount * p.percent / 100.0, 2)
                    ELSE 0
                END
            FROM sale_order o
            WHERE p.sale_id = o.id
              AND p.sale_id IN (
                SELECT sale_order_id FROM l10n_br_ccf_mig_order
            )
            """
        )

    cr.execute("DROP TABLE IF EXISTS l10n_br_ccf_mig_order")
    cr.execute("DROP TABLE IF EXISTS l10n_br_ccf_mig_admin")
