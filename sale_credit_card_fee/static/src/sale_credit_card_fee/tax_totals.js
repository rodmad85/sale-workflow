/** @odoo-module **/

import { TaxTotalsComponent } from "@account/components/tax_totals/tax_totals";
import { patch } from "@web/core/utils/patch";

patch(TaxTotalsComponent.prototype, {
    formatData(props) {
        super.formatData(props);
        if (!Array.isArray(this.totals.subtotals)) {
            this.totals = {
                subtotals: [],
                has_tax_groups: false,
                base_amount: 0.0,
                base_amount_currency: 0.0,
                tax_amount: 0.0,
                tax_amount_currency: 0.0,
                total_amount: 0.0,
                total_amount_currency: 0.0,
            };
        }
    },
});