All notable changes to this module will be documented in this file.

## 18.0.4.1.0 (2026-10-08)

- Show the credit card fees of the sale order in the customer invoice
  form: a **Credit Card Fees** tab lists the fee of every card
  administrator of the orders the invoice comes from, with the amount
  it is charged on and the fee itself, and an invoice of several orders
  shows the fee of all of them.
- Let the invoicing and accounting users read the credit card fees of
  the invoice form.
- Invoice the credit card fee of every order an invoice groups, instead
  of the fee of the first one only.
- Show the payment methods of the invoice in the header, next to the
  due date, as *sale_payment_method* does, instead of after the payment
  terms.

## 18.0.4.0.1 (2026-10-07)

- Share the amount of the order between its credit card fee lines: the
  **Amount** of the rows adds up to the total of the order, taxes included,
  and the fee of each card is charged on top of it. The whole of that total
  is charged on the first line by default, and a line added to an order
  that already has one starts with no amount at all.
- Keep that total when the user edits an amount: the amount just edited is
  kept as it was typed and the other lines share the difference equally
  between them, none of them going below zero, so the amounts can never
  add up to more than the total of the order.
- Check the amounts of the fee lines while the order is being edited: the
  listing is corrected as soon as an amount changes, without waiting for
  the order to be saved. The line being edited is found by the marker of the
  listing or, when it does not reach the server, by the amounts that changed
  since they were saved, so the other lines always share the difference.
- Keep the technical fields of those checks in the listing of the fee lines,
  hidden, so that the web client sends them back to the server with the
  amounts and the order is settled even if a listing is edited by another
  client.
- Update the fee preview of the *Create Invoice Plan* wizard and do not
  invoice a fee line that has no amount.

## 18.0.4.0.0 (2026-10-06)

- Add the **Amount** (editable, defaulting to the order total plus the
  credit card fee) and the **Fee Amount** columns to the credit card fee
  lines of the sale order.
- Compute the sale order **Fee Amount** as the sum of the fee amounts of
  its credit card fee lines, and split the invoiced fee proportionally to
  them.
- List the fee of each credit card of the order, separated by commas, in
  the *Fee (%)* of the sale order totals.

## 18.0.3.0.0 (2026-08-21)

- Include the credit card fee in installment invoices through a
  *Credit Card Fee* product line, proportional to each planned
  installment, when *Sum Fee* is enabled.
- Move the card administrator selection into the *Create Invoice Plan*
  wizard and show the fee preview (*Fee (%)*, fee amount,
  *Amount + Fee*).
- Add the *Sum Fee* option to charge or only track the fee.
- Restructure the sale order fee summary block.

## 18.0.1.0.0 (2025-01-01)

- Initial version: credit card administrators with fee ranges by
  installments, fee computation on sale orders based on the invoice
  plan and per-installment fee distribution.
