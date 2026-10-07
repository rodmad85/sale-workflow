from odoo.tests import Form

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.sale.models.sale_order import SaleOrder

_IMAGE = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


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

    def _expected_amount(self, order, percent):
        """Return the default fee line amount: the order total plus the fee."""
        base = order.amount_untaxed + order.amount_tax
        return order.currency_id.round(base + base * percent / 100.0)

    def _expected_fee(self, order, percent):
        """Return the fee charged on the default fee line amount."""
        amount = self._expected_amount(order, percent)
        return order.currency_id.round(amount * percent / 100.0)

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
        base = order.amount_untaxed + order.amount_tax
        self.assertEqual(line.amount, order.currency_id.round(base + base * 0.025))
        self.assertEqual(line.amount, self._expected_amount(order, 2.5))
        self.assertEqual(line.fee_amount, self._expected_fee(order, 2.5))

    def test_fee_line_amount_is_editable(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        line = order.credit_card_fee_line_ids
        line.amount = 1000.0
        self.assertEqual(line.fee_amount, 25.0)
        self.assertEqual(order.credit_card_fee_amount, 25.0)
        self.assertEqual(
            order.amount_total,
            order.amount_untaxed + order.amount_tax + 25.0,
        )

    def test_fee_line_amount_follows_order_amount(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        line = order.credit_card_fee_line_ids
        order.order_line.product_uom_qty = 2
        base = order.amount_untaxed + order.amount_tax
        self.assertEqual(line.amount, base + base * 0.025)
        self.assertEqual(line.amount, self._expected_amount(order, 2.5))

    def test_fee_line_custom_amount_is_kept(self):
        order = self._create_sale_order()
        order.create_invoice_plan(3, "2025-01-01", 1, "month", False)
        line = order.credit_card_fee_line_ids
        line.amount = 1000.0
        self.assertTrue(line.custom_amount)
        order.order_line.product_uom_qty = 2
        self.assertEqual(line.amount, 1000.0)
        self.assertEqual(line.fee_amount, 25.0)
        self.assertEqual(order.credit_card_fee_amount, 25.0)

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
        expected_fee = self._expected_fee(order, 2.5 + 1.5)
        self.assertAlmostEqual(order.credit_card_fee_amount, expected_fee, places=2)

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
        expected = order.credit_card_fee_line_ids.sorted("fee_percent").mapped(
            "fee_amount"
        )
        for fee_line, expected_fee in zip(
            fee_lines.sorted(lambda line: line.name), expected, strict=False
        ):
            self.assertAlmostEqual(fee_line.price_unit, expected_fee, places=2)

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
