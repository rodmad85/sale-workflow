To use this module, you need to:

1. In *Sales → Configuration → Payment Methods*, open a payment method
   (e.g. *Cartão de Crédito*) and enable **Card Administrator**. The
   **Fee Ranges** tab appears; add the fee table for each installment
   range.
2. On a quotation or sale order, select the payment method(s). For each
   selected payment method marked as Card Administrator a row is shown
   with the payment method name and the fields **Add Fee**,
   **Credit Card Fee Range**, **Fee (%)**, **Amount** and
   **Fee Amount**.
3. The **Amount** of a row is the part of the order paid with that card.
   The **Amount** of the rows adds up to the total of the order, taxes
   included, and the fee of each card is charged on top of it. The whole
   of that total is charged on the first row, and a row added to an order
   that already has one starts with the **Amount** set to zero.
   **Fee Amount** is the fee of that row: its **Fee (%)** applied on its
   **Amount**.
4. The **Amount** is editable, so the fee of a payment method can be
   charged on another amount, e.g. only part of the order. The listing is
   corrected as soon as an amount changes, without waiting for the order
   to be saved: the amount just edited is kept exactly as it was typed and
   the other rows share the difference equally between them, none of them
   going below zero, so the **Amount** of the rows never adds up to more
   than the total of the order. An amount bigger than that total is
   refused. Setting the **Amount** of a row to zero gives the whole total
   back to the other row when there is only one left. The row being edited
   is the one holding an amount that is no longer the saved one, so the
   listing is settled even when the row is edited by another client.
5. A row whose **Amount** was edited stops following the order total and
   the credit card fees: when the order changes, the rows that were not
   edited share the new total.
6. Go to the *Invoice Plan* tab and click *⇒ Create Invoice Plan*. The
   wizard shows the applicable **Fee (%)**, the fee amount and the order
   total including the fee (**Amount + Fee**), previewing the same
   computation of the order.
7. Enable **Add Fee** on the order to add the credit card fee to the
   order total and to include it proportionally in each installment
   invoice. Leave it unchecked to track the fee without charging it.
8. Confirm the wizard and invoice the installments from the invoice
   plan; each customer invoice will contain a *Credit Card Fee* line
   with its proportional share of the fee.

In the totals of the sale order, **Fee (%)** lists the fee of each
credit card of the order separated by commas (e.g. *2.5, 3.5*), while
**Fee Amount** is the sum of the **Fee Amount** of its rows.