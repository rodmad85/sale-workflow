All notable changes to this module will be documented in this file.

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
