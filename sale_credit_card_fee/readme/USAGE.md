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
3. The **Amount** of a row defaults to the order total plus the credit
   card fee, and **Fee Amount** is the fee of that row: its **Fee (%)**
   applied on its **Amount**. The **Amount** is editable, so the fee of a
   payment method can be charged on another amount, e.g. only part of
   the order. Once edited, the row shows a **Custom Amount** toggle: the
   amount stops following the order total and the credit card fees, and
   switching the toggle off restores the default.
4. Go to the *Invoice Plan* tab and click *⇒ Create Invoice Plan*. The
   wizard shows the applicable **Fee (%)**, the fee amount and the order
   total including the fee (**Amount + Fee**), previewing the same
   computation of the order.
5. Enable **Add Fee** on the order to add the credit card fee to the
   order total and to include it proportionally in each installment
   invoice. Leave it unchecked to track the fee without charging it.
6. Confirm the wizard and invoice the installments from the invoice
   plan; each customer invoice will contain a *Credit Card Fee* line
   with its proportional share of the fee.

In the totals of the sale order, **Fee (%)** lists the fee of each
credit card of the order separated by commas (e.g. *2.5, 3.5*), while
**Fee Amount** is the sum of the **Fee Amount** of its rows.