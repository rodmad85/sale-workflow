from odoo.tests import Form

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.sale.models.sale_order import SaleOrder

_IMAGE = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# the fields the web client sends and gets back for the credit card fee
# lines of a sale order and for the sale order itself
FEE_LINE_SPEC = {
    "id": {},
    "amount": {},
    "custom_amount": {},
    "edited_amount": {},
    "sum_fee": {},
    "fee_amount": {},
    "fee_percent": {},
    "fee_range_id": {},
    "payment_method_id": {},
    "currency_id": {},
}
ORDER_SPEC = {
    "credit_card_fee_line_ids": {"fields": FEE_LINE_SPEC},
    "partner_id": {"fields": {"display_name": {}}},
    "payment_method_ids": {"fields": {"id": {}}},
    "order_line": {
        "fields": {
            "id": {},
            "product_id": {"fields": {"display_name": {}}},
            "product_uom_qty": {},
            "price_unit": {},
            "price_subtotal": {},
        }
    },
    "invoice_plan_ids": {"fields": {"id": {}, "invoice_type": {}, "percent": {}}},
    "amount_untaxed": {},
    "amount_tax": {},
    "amount_total": {},
    "credit_card_fee_amount": {},
    "credit_card_fee_percent": {},
    "credit_card_amount_plus_fee": {},
    "currency_id": {"fields": {"id": {}}},
    "company_id": {"fields": {"id": {}}},
    "payment_term_id": {"fields": {"id": {}}},
}


class TestCreditCardFee(AccountTestInvoicingCommon):
    chart_template = "generic_coa"

    @staticmethod
    def _confirm_sale_order(order):
        SaleOrder.action_confirm(order)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payment_method = cls.env["payment.method"].create(
            {
                "name": "Cartao de Credito",
                "code": "cartao_de_credito",
                "image": _IMAGE,
                "credit_card_admin": True,
            }
        )
        cls.env["credit.card.fee.range"].create(
            {
                "payment_method_id": cls.payment_method.id,
                "installments_from": 1,
                "installments_to": 3,
                "fee_percent": 2.5,
            }
        )
        cls.env["credit.card.fee.range"].create(
            {
                "payment_method_id": cls.payment_method.id,
                "installments_from": 4,
                "installments_to": 6,
                "fee_percent": 3.5,
            }
        )
        cls.second_method = cls.env["payment.method"].create(
            {
                "name": "Cartao de Credito 2",
                "code": "cartao_de_credito_2",
                "image": _IMAGE,
                "credit_card_admin": True,
            }
        )
        cls.env["credit.card.fee.range"].create(
            {
                "payment_method_id": cls.second_method.id,
                "installments_from": 1,
                "installments_to": 12,
                "fee_percent": 1.5,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product",
                "list_price": 100.0,
                "invoice_policy": "order",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )

    def _create_sale_order(self, methods=None):
        order_form = Form(self.env["sale.order"])
        order_form.partner_id = self.partner
        with order_form.order_line.new() as line:
            line.product_id = self.product
            line.product_uom_qty = 1
        for method in methods or [self.payment_method]:
            order_form.payment_method_ids.add(method)
        return order_form.save()

    def _create_admin_method(self, name, code, percent, installments=(1, 12)):
        """Return a card administrator payment method and its fee table."""
        method = self.env["payment.method"].create(
            {
                "name": name,
                "code": code,
                "image": _IMAGE,
                "credit_card_admin": True,
            }
        )
        self.env["credit.card.fee.range"].create(
            {
                "payment_method_id": method.id,
                "installments_from": installments[0],
                "installments_to": installments[1],
                "fee_percent": percent,
            }
        )
        return method

    def _expected_amount(self, order, percent):
        """Return the amount the fee lines add up to: the total of the order.

        The fee is a part of that amount, so the order only receives the rest
        of it, taxes included.
        """
        base = order.amount_untaxed + order.amount_tax
        return order.currency_id.round(base / (1.0 - percent / 100.0))

    def _expected_fee(self, order, percent):
        """Return the fee charged on the default fee line amount."""
        amount = self._expected_amount(order, percent)
        return order.currency_id.round(amount * percent / 100.0)

    def _expected_line_fee(self, order, percent, amount):
        """Return the fee of ``percent`` charged on ``amount``."""
        return order.currency_id.round(amount * percent / 100.0)

    def _assert_amounts_add_up_to_the_total(self, order):
        """The amounts of the lines add up to the total of the order."""
        self.assertAlmostEqual(
            sum(order.credit_card_fee_line_ids.mapped("amount")),
            order._credit_card_fee_default_amount(),
            places=2,
        )
        self.assertAlmostEqual(
            sum(order.credit_card_fee_line_ids.mapped("fee_amount")),
            order.credit_card_fee_amount,
            places=2,
        )

    def test_payment_method_fee_ranges(self):
        self.assertTrue(self.payment_method.credit_card_admin)
        self.assertEqual(len(self.payment_method.fee_line_ids), 2)

    def test_sale_order_creates_fee_line(self):
        order = self._create_sale_order()
        self.assertEqual(len(order.credit_card_fee_line_ids), 1)
        self.assertEqual(
            order.credit_card_fee_line_ids.payment_method_id,
            self.payment_method,
        )

    def test_fee_percent_by_installments(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        self.assertEqual(order.credit_card_fee_line_ids.fee_percent, 2.5)
        self.assertEqual(order.credit_card_fee_percent, "2.5")
        self.assertEqual(order.credit_card_fee_percent_sum, 2.5)
        self.assertAlmostEqual(
            order.credit_card_fee_amount,
            self._expected_fee(order, 2.5),
            places=2,
        )

    def test_fee_line_amount_and_fee_amount(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        line = order.credit_card_fee_line_ids
        self.assertEqual(line.amount, self._expected_amount(order, 2.5))
        self.assertEqual(line.fee_amount, self._expected_fee(order, 2.5))
        # The amount of the line is the total of the order, fee included.
        self._assert_amounts_add_up_to_the_total(order)

    def test_fee_line_amount_is_editable(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        line = order.credit_card_fee_line_ids
        line.amount = 100.0
        self.assertEqual(line.fee_amount, 2.5)
        self.assertEqual(order.credit_card_fee_amount, 2.5)
        self.assertEqual(
            order.amount_total,
            order.amount_untaxed + order.amount_tax + 2.5,
        )

    def test_fee_line_amount_cannot_go_over_the_order_total(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        line = order.credit_card_fee_line_ids
        amount = self._expected_amount(order, 2.5)
        line.amount = 1000.0
        # The amount of the lines cannot add up to more than the order.
        self.assertEqual(line.amount, amount)
        self.assertEqual(line.fee_amount, self._expected_fee(order, 2.5))
        line.amount = 0.0
        line.amount = amount
        self.assertEqual(line.amount, amount)

    def test_fee_line_amount_follows_order_amount(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        line = order.credit_card_fee_line_ids
        order.order_line.product_uom_qty = 2
        self.assertEqual(line.amount, self._expected_amount(order, 2.5))
        self._assert_amounts_add_up_to_the_total(order)

    def test_fee_line_custom_amount_is_kept(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        line = order.credit_card_fee_line_ids
        line.amount = 100.0
        self.assertTrue(line.custom_amount)
        order.order_line.product_uom_qty = 2
        self.assertEqual(line.amount, 100.0)
        self.assertEqual(line.fee_amount, 2.5)
        self.assertEqual(order.credit_card_fee_amount, 2.5)

    def test_second_fee_line_amount_is_zero(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        first, second = order.credit_card_fee_line_ids
        # The whole order is charged on the first fee line: the line added
        # after it starts with no amount at all.
        amount = self._expected_amount(order, 2.5)
        self.assertEqual(first.amount, amount)
        self.assertEqual(second.amount, 0.0)
        self.assertEqual(second.fee_amount, 0.0)
        self.assertAlmostEqual(
            order.credit_card_fee_amount, self._expected_line_fee(order, 2.5, amount)
        )
        self._assert_amounts_add_up_to_the_total(order)

    def test_amount_edit_is_taken_from_the_other_lines(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        total = order._credit_card_fee_default_amount()
        first, second = order.credit_card_fee_line_ids
        second.amount = 20.0
        self.assertTrue(second.custom_amount)
        self.assertEqual(second.amount, 20.0)
        # The other line takes exactly what the second one was given.
        self.assertEqual(first.amount, order.currency_id.round(total - 20.0))
        self.assertAlmostEqual(first.fee_amount, 2.45, places=2)
        self.assertAlmostEqual(second.fee_amount, 0.30, places=2)
        self._assert_amounts_add_up_to_the_total(order)

    def test_amount_edit_of_an_amount_gives_it_back_to_the_other_lines(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        total = order._credit_card_fee_default_amount()
        first, second = order.credit_card_fee_line_ids
        second.amount = 50.0
        # Give the amount of the second line to the first one.
        self.assertEqual(second.amount, 50.0)
        self.assertEqual(first.amount, order.currency_id.round(total - 50.0))
        self.assertEqual(second.amount, 50.0)
        self._assert_amounts_add_up_to_the_total(order)

    def test_amount_edit_cannot_go_over_the_order_total(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        total = order._credit_card_fee_default_amount()
        first, second = order.credit_card_fee_line_ids
        second.amount = 1000.0
        # The other lines hold nothing: the amount is capped to the total.
        self.assertEqual(second.amount, order.currency_id.round(total))
        self.assertEqual(first.amount, 0.0)
        self._assert_amounts_add_up_to_the_total(order)

    def test_amount_edit_of_the_line_holding_the_order_shares_it(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        total = order._credit_card_fee_default_amount()
        first, second = order.credit_card_fee_line_ids
        first.amount = 1000.0
        self.assertEqual(first.amount, order.currency_id.round(total))
        first.amount = 50.0
        # What the first line gives up is shared equally by the other ones.
        self.assertEqual(first.amount, 50.0)
        self.assertEqual(second.amount, order.currency_id.round(total - 50.0))
        self._assert_amounts_add_up_to_the_total(order)

    def test_amount_edit_is_spread_over_the_other_lines(self):
        third_method = self._create_admin_method("Cartao de Credito 3", "cartao_3", 2.0)
        order = self._create_sale_order(
            [self.payment_method, self.second_method, third_method]
        )
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        total = order._credit_card_fee_default_amount()
        first, second, third = order.credit_card_fee_line_ids
        first.amount = 50.0
        # What the first line gives up is shared equally by the other two.
        share = order.currency_id.round((total - 50.0) / 2)
        self.assertEqual(second.amount, share)
        self.assertEqual(third.amount, order.currency_id.round(total - 50.0 - share))
        # And what a line is given is shared equally by the other two.
        second.amount = 60.0
        given = 60.0 - share
        self.assertAlmostEqual(third.amount, total - 50.0 - share - given / 2, places=2)
        self.assertEqual(first.amount, order.currency_id.round(50.0 - given / 2))
        self._assert_amounts_add_up_to_the_total(order)

    def test_amount_edit_restores_the_total_of_the_order(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        total = order._credit_card_fee_default_amount()
        first, second = order.credit_card_fee_line_ids
        # An order left with amounts that do not add up to the total of the
        # order, as the previous versions did, is settled on the next edit.
        order.credit_card_fee_line_ids.with_context(
            credit_card_fee_sync_amount=True
        ).write({"amount": 10.0})
        self.assertEqual(sum(order.credit_card_fee_line_ids.mapped("amount")), 20.0)
        second.amount = 30.0
        self.assertEqual(second.amount, 30.0)
        self.assertEqual(first.amount, order.currency_id.round(total - 30.0))
        self._assert_amounts_add_up_to_the_total(order)

    def test_edited_amount_is_kept_when_the_order_changes(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        first, second = order.credit_card_fee_line_ids
        second.amount = 20.0
        order.order_line.product_uom_qty = 2
        # The line that still follows the order takes what is left of the
        # new total, which is twice as big.
        self.assertEqual(second.amount, 20.0)
        self.assertEqual(
            first.amount,
            order.currency_id.round(order._credit_card_fee_default_amount() - 20.0),
        )
        self._assert_amounts_add_up_to_the_total(order)

    def test_added_fee_line_amount_is_zero(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        first = order.credit_card_fee_line_ids
        order.write({"payment_method_ids": [(4, self.second_method.id)]})
        self.assertEqual(len(order.credit_card_fee_line_ids), 2)
        new_line = order.credit_card_fee_line_ids - first
        self.assertEqual(new_line.payment_method_id, self.second_method)
        self.assertEqual(new_line.amount, 0.0)
        self.assertEqual(first.amount, self._expected_amount(order, 2.5))
        self._assert_amounts_add_up_to_the_total(order)

    def _edit_fee_amount(self, order, index, amount):
        """Edit the amount of a fee line the way the form does it.

        The web client asks the fee line for its own onchange first, which
        flags the amount as chosen by the user and marks the line as edited,
        then the order for the checks of the whole listing, and finally saves
        the order with the values it got back.
        """
        lines = order.credit_card_fee_line_ids
        line = lines[index]
        pending = {
            fee_line.id: {
                "amount": fee_line.amount,
                "custom_amount": fee_line.custom_amount,
                "edited_amount": fee_line.edited_amount,
            }
            for fee_line in lines
        }
        pending[line.id]["amount"] = amount
        values = (
            line.onchange(dict(pending[line.id]), ["amount"], FEE_LINE_SPEC).get(
                "value"
            )
            or {}
        )
        pending[line.id].update(values)
        commands = [[1, line_id, dict(vals)] for line_id, vals in pending.items()]
        result = order.onchange(
            {"credit_card_fee_line_ids": commands},
            ["credit_card_fee_line_ids"],
            ORDER_SPEC,
        )
        for command in result.get("value", {}).get("credit_card_fee_line_ids") or []:
            pending[command[1]].update(command[2] or {})
        order.write(
            {
                "credit_card_fee_line_ids": [
                    [1, line_id, dict(vals)] for line_id, vals in pending.items()
                ]
            }
        )

    def test_onchange_amount_flags_the_line_as_edited(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        line = order.credit_card_fee_line_ids.new({"amount": 50.0})
        line._onchange_amount()
        self.assertTrue(line.custom_amount)

    def test_onchange_amount_is_shared_with_the_other_lines(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        total = order._credit_card_fee_default_amount()
        first, second = order.credit_card_fee_line_ids
        self._edit_fee_amount(order, 1, 20.0)
        # The onchange shares the amount before the order is saved.
        self.assertEqual(second.amount, 20.0)
        self.assertEqual(first.amount, order.currency_id.round(total - 20.0))
        self._assert_amounts_add_up_to_the_total(order)

    def test_onchange_amount_cannot_go_over_the_order_total(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        total = order._credit_card_fee_default_amount()
        first, second = order.credit_card_fee_line_ids
        self._edit_fee_amount(order, 1, 1000.0)
        self.assertEqual(second.amount, order.currency_id.round(total))
        self.assertEqual(first.amount, 0.0)
        self._assert_amounts_add_up_to_the_total(order)

    def test_onchange_amount_of_the_line_holding_the_order_shares_it(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        total = order._credit_card_fee_default_amount()
        first, second = order.credit_card_fee_line_ids
        self._edit_fee_amount(order, 0, 50.0)
        self.assertEqual(first.amount, 50.0)
        self.assertEqual(second.amount, order.currency_id.round(total - 50.0))
        self._assert_amounts_add_up_to_the_total(order)

    def test_onchange_keeps_the_other_amounts_following_the_order(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        first, second = order.credit_card_fee_line_ids
        self._edit_fee_amount(order, 1, 20.0)
        # Only the line edited by the user stops following the order.
        self.assertTrue(second.custom_amount)
        self.assertFalse(first.custom_amount)
        order.order_line.product_uom_qty = 2
        self.assertEqual(second.amount, 20.0)
        self.assertEqual(
            first.amount,
            order.currency_id.round(order._credit_card_fee_default_amount() - 20.0),
        )
        self._assert_amounts_add_up_to_the_total(order)

    def test_onchange_amount_is_shared_with_every_other_line(self):
        third_method = self._create_admin_method("Cartao de Credito 3", "cartao_3", 2.0)
        order = self._create_sale_order(
            [self.payment_method, self.second_method, third_method]
        )
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        total = order._credit_card_fee_default_amount()
        first, second, third = order.credit_card_fee_line_ids
        self._edit_fee_amount(order, 0, 50.0)
        # What the first line gives up is shared equally by the other two.
        share = order.currency_id.round((total - 50.0) / 2)
        self.assertEqual(second.amount, share)
        self.assertEqual(third.amount, order.currency_id.round(total - 50.0 - share))
        self._assert_amounts_add_up_to_the_total(order)

    def test_onchange_amount_keeps_the_amount_the_user_edited(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        total = order._credit_card_fee_default_amount()
        first, second = order.credit_card_fee_line_ids
        self._edit_fee_amount(order, 1, 50.0)
        self._edit_fee_amount(order, 0, 70.0)
        # The amount just edited is kept as it was typed, whatever the other
        # line holds, and the difference is shared by the other lines.
        self.assertEqual(first.amount, 70.0)
        self.assertEqual(second.amount, order.currency_id.round(total - 70.0))
        self._assert_amounts_add_up_to_the_total(order)

    def test_fee_percent_is_comma_separated(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        self.assertEqual(order.credit_card_fee_percent, "2.5, 1.5")
        self.assertEqual(order.credit_card_fee_percent_sum, 2.5 + 1.5)

    def test_fee_amount_is_the_sum_of_the_fee_line_amounts(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        lines = order.credit_card_fee_line_ids
        self.assertEqual(
            order.credit_card_fee_amount,
            sum(lines.mapped("fee_amount")),
        )

    def test_different_installment_range(self):
        order = self._create_sale_order()
        order.create_invoice_plan(5, "2025-01-01", 1, "month", False)
        self.assertEqual(order.credit_card_fee_percent, "3.5")

    def test_multiple_admin_methods(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        self.assertEqual(len(order.credit_card_fee_line_ids), 2)
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        self.assertEqual(order.credit_card_fee_percent_sum, 2.5 + 1.5)
        # The whole amount of the order is charged on the first fee line.
        amount = self._expected_amount(order, 2.5)
        self.assertAlmostEqual(
            order.credit_card_fee_amount,
            self._expected_line_fee(order, 2.5, amount),
        )
        self._assert_amounts_add_up_to_the_total(order)

    def test_no_fee_without_admin(self):
        order = Form(self.env["sale.order"])
        order.partner_id = self.partner
        with order.order_line.new() as line:
            line.product_id = self.product
            line.product_uom_qty = 1
        order = order.save()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        self.assertEqual(order.credit_card_fee_percent, "")
        self.assertEqual(order.credit_card_fee_percent_sum, 0.0)
        self.assertEqual(order.credit_card_fee_amount, 0.0)

    def test_fee_amount_included_in_total(self):
        order = self._create_sale_order()
        total_before = order.amount_total
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        expected_fee = self._expected_fee(order, 2.5)
        expected_total = total_before + expected_fee
        self.assertEqual(order.amount_total, expected_total)
        self.assertAlmostEqual(order.credit_card_amount_plus_fee, expected_total)

    def test_fee_amount_based_on_total_including_tax(self):
        tax = self.env["account.tax"].create(
            {
                "name": "Tax 10%",
                "amount": 10.0,
            }
        )
        product = self.env["product.product"].create(
            {
                "name": "Taxed Product",
                "list_price": 100.0,
                "invoice_policy": "order",
                "taxes_id": [(6, 0, tax.ids)],
            }
        )
        order_form = Form(self.env["sale.order"])
        order_form.partner_id = self.partner
        with order_form.order_line.new() as line:
            line.product_id = product
            line.product_uom_qty = 1
        order_form.payment_method_ids.add(self.payment_method)
        order = order_form.save()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        self.assertEqual(order.credit_card_fee_percent, "2.5")
        base = order.amount_untaxed + order.amount_tax
        self.assertAlmostEqual(
            order.credit_card_fee_amount,
            self._expected_fee(order, 2.5),
            places=2,
        )
        self.assertAlmostEqual(
            order.amount_total, base + self._expected_fee(order, 2.5)
        )

    def test_no_fee_after_removing_admin(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        self.assertTrue(order.credit_card_fee_percent_sum > 0)
        order.write({"payment_method_ids": [(6, 0, [])]})
        self.assertEqual(order.credit_card_fee_percent, "")
        self.assertFalse(order.credit_card_fee_line_ids)

    def test_sum_fee_false_keeps_total(self):
        order = self._create_sale_order()
        total_before = order.amount_total
        order.credit_card_fee_line_ids.sum_fee = False
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        self.assertEqual(order.amount_total, total_before)
        self.assertEqual(order.credit_card_fee_percent, "2.5")
        self.assertAlmostEqual(
            order.credit_card_fee_amount,
            self._expected_fee(order, 2.5),
            places=2,
        )

    def test_sum_fee_toggle_keeps_fee_field_values(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        percent = order.credit_card_fee_percent
        fee_amount = order.credit_card_fee_amount
        amount_plus_fee = order.credit_card_amount_plus_fee
        total_with_fee = order.amount_total
        order.credit_card_fee_line_ids.sum_fee = False
        self.assertEqual(order.credit_card_fee_percent, percent)
        self.assertEqual(order.credit_card_fee_amount, fee_amount)
        self.assertEqual(order.credit_card_amount_plus_fee, amount_plus_fee)
        self.assertEqual(order.amount_total, total_with_fee - fee_amount)
        order.credit_card_fee_line_ids.sum_fee = True
        self.assertEqual(order.amount_total, total_with_fee)

    def _create_wizard(self, order, num_installment=3):
        wizard_form = Form(
            self.env["sale.create.invoice.plan"].with_context(
                active_id=order.id,
                active_model="sale.order",
            )
        )
        wizard_form.num_installment = num_installment
        return wizard_form.save()

    def test_wizard_show_fee_preview(self):
        order = self._create_sale_order()
        total_before = order.amount_total
        wizard = self._create_wizard(order)
        self.assertEqual(wizard.credit_card_fee_percent, 2.5)
        self.assertAlmostEqual(
            wizard.credit_card_fee_amount,
            self._expected_fee(order, 2.5),
            places=2,
        )
        expected_total = total_before + wizard.credit_card_fee_amount
        self.assertAlmostEqual(wizard.amount_plus_fee, expected_total)
        wizard.sale_create_invoice_plan()
        self.assertEqual(order.credit_card_fee_percent, "2.5")
        self.assertEqual(order.amount_total, expected_total)

    def test_wizard_show_fee_preview_with_multiple_admin_methods(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        total_before = order.amount_total
        wizard = self._create_wizard(order)
        self.assertEqual(wizard.credit_card_fee_percent, 2.5 + 1.5)
        amount = self._expected_amount(order, 2.5)
        self.assertAlmostEqual(
            wizard.credit_card_fee_amount,
            self._expected_line_fee(order, 2.5, amount),
        )
        self.assertAlmostEqual(
            wizard.amount_plus_fee, total_before + wizard.credit_card_fee_amount
        )
        wizard.sale_create_invoice_plan()
        # The preview is the fee charged once the plan is created.
        self.assertAlmostEqual(
            order.credit_card_fee_amount, wizard.credit_card_fee_amount
        )
        self.assertAlmostEqual(
            order.credit_card_amount_plus_fee, wizard.amount_plus_fee
        )

    def test_installment_invoice_includes_fee(self):
        order = self._create_sale_order()
        wizard = self._create_wizard(order)
        wizard.sale_create_invoice_plan()
        self._confirm_sale_order(order)
        plans = order.invoice_plan_ids.filtered(
            lambda p: p.invoice_type == "installment"
        ).sorted("installment")
        move = order.with_context(invoice_plan_id=plans[0].id)._create_invoices()
        product = self.env.ref("sale_credit_card_fee.product_credit_card_fee")
        fee_lines = move.invoice_line_ids.filtered(
            lambda line: line.product_id == product
        )
        self.assertEqual(len(fee_lines), 1)
        expected_fee = plans[0].credit_card_fee_amount
        self.assertAlmostEqual(
            fee_lines.price_unit * fee_lines.quantity,
            expected_fee,
        )
        self.assertAlmostEqual(
            move.amount_total - move.amount_tax,
            plans[0].amount + expected_fee,
        )

    def test_installment_invoice_without_sum_fee_has_no_fee_line(self):
        order = self._create_sale_order()
        order.credit_card_fee_line_ids.sum_fee = False
        wizard = self._create_wizard(order)
        wizard.sale_create_invoice_plan()
        self._confirm_sale_order(order)
        plans = order.invoice_plan_ids.filtered(
            lambda p: p.invoice_type == "installment"
        ).sorted("installment")
        move = order.with_context(invoice_plan_id=plans[0].id)._create_invoices()
        product = self.env.ref("sale_credit_card_fee.product_credit_card_fee")
        self.assertFalse(
            move.invoice_line_ids.filtered(lambda line: line.product_id == product)
        )

    def test_account_move_shows_fee_fields(self):
        order = self._create_sale_order()
        wizard = self._create_wizard(order)
        wizard.sale_create_invoice_plan()
        self._confirm_sale_order(order)
        plans = order.invoice_plan_ids.filtered(
            lambda p: p.invoice_type == "installment"
        ).sorted("installment")
        move = order.with_context(invoice_plan_id=plans[0].id)._create_invoices()
        self.assertEqual(move.credit_card_fee_percent, 2.5)
        self.assertAlmostEqual(
            move.credit_card_fee_amount, order.credit_card_fee_amount
        )
        self.assertAlmostEqual(
            move.credit_card_amount_plus_fee, order.credit_card_amount_plus_fee
        )

    def test_create_invoice_without_plan_includes_fee(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        self._confirm_sale_order(order)
        move = order._create_invoices()
        product = self.env.ref("sale_credit_card_fee.product_credit_card_fee")
        fee_lines = move.invoice_line_ids.filtered(
            lambda line: line.product_id == product
        )
        self.assertEqual(len(fee_lines), 1)
        self.assertAlmostEqual(fee_lines.price_unit, order.credit_card_fee_amount)
        self.assertAlmostEqual(
            move.amount_untaxed + (move.amount_tax or 0.0),
            order.amount_untaxed + order.amount_tax + order.credit_card_fee_amount,
        )

    def test_invoice_fee_is_split_between_the_fee_lines(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        # Charge part of the order on the fee of the second card.
        order.credit_card_fee_line_ids[1].amount = 20.0
        self._confirm_sale_order(order)
        move = order._create_invoices()
        product = self.env.ref("sale_credit_card_fee.product_credit_card_fee")
        fee_lines = move.invoice_line_ids.filtered(
            lambda line: line.product_id == product
        )
        self.assertEqual(len(fee_lines), 2)
        self.assertAlmostEqual(
            sum(fee_lines.mapped("price_unit")),
            order.credit_card_fee_amount,
            places=2,
        )
        prices = {line.name: line.price_unit for line in fee_lines}
        for line in order.credit_card_fee_line_ids:
            name = self.env._("Credit Card Fee (%s%%) - %s") % (
                line.fee_percent,
                line.payment_method_id.name,
            )
            self.assertAlmostEqual(prices[name], line.fee_amount, places=2)

    def test_invoice_has_no_fee_line_without_amount(self):
        order = self._create_sale_order([self.payment_method, self.second_method])
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        self._confirm_sale_order(order)
        move = order._create_invoices()
        product = self.env.ref("sale_credit_card_fee.product_credit_card_fee")
        fee_lines = move.invoice_line_ids.filtered(
            lambda line: line.product_id == product
        )
        # The second fee line has no amount, so it is charged with no fee.
        self.assertEqual(len(fee_lines), 1)
        self.assertAlmostEqual(
            sum(fee_lines.mapped("price_unit")),
            order.credit_card_fee_amount,
            places=2,
        )

    def test_create_invoice_without_plan_no_fee_when_sum_fee_false(self):
        order = self._create_sale_order()
        order.credit_card_fee_line_ids.sum_fee = False
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        self._confirm_sale_order(order)
        move = order._create_invoices()
        product = self.env.ref("sale_credit_card_fee.product_credit_card_fee")
        self.assertFalse(
            move.invoice_line_ids.filtered(lambda line: line.product_id == product)
        )
