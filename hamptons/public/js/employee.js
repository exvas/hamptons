// Employee form customizations for Hamptons
//
// HR Actions > Setup New Employee: one click creates the Leave Policy Assignment
// (HRMS creates the Leave Allocations when it is submitted) and a Shift Assignment
// for the shift chosen in the dialog. Server side: hamptons.api.employee_setup

frappe.provide("hamptons.employee_setup");

frappe.ui.form.on("Employee", {
    refresh(frm) {
        hamptons.employee_setup.add_hr_actions(frm);
        hamptons.employee_setup.show_pending_setup(frm);
    },
});

hamptons.employee_setup = {
    LEAVE_STEP: "Leave Policy Assignment",
    SHIFT_STEP: "Shift Assignment",

    is_available(frm) {
        return (
            !frm.is_new() &&
            frm.doc.status === "Active" &&
            frappe.model.can_create(this.LEAVE_STEP) &&
            frappe.model.can_create(this.SHIFT_STEP)
        );
    },

    add_hr_actions(frm) {
        if (!this.is_available(frm)) return;
        frm.add_custom_button(
            __("Setup New Employee"),
            () => this.open_setup_dialog(frm),
            __("HR Actions")
        );
    },

    get_status(frm) {
        return frappe
            .call({
                method: "hamptons.api.employee_setup.get_setup_status",
                args: { employee: frm.doc.name },
            })
            .then((r) => r.message);
    },

    // Orange "Setup pending: ..." headline with a "Setup Now" link while something is missing.
    show_pending_setup(frm) {
        if (!this.is_available(frm)) return;
        const employee = frm.doc.name;
        this.get_status(frm).then((status) => {
            // the form may have moved to another employee while the call was in flight
            if (!status || frm.doc.name !== employee || !status.pending.length) return;

            const pending = status.pending.map((step) => __(step)).join(", ");
            frm.dashboard.set_headline(
                `${__("Setup pending: {0}", [pending])}
                 <a class="hamptons-setup-now" style="margin-left: 8px; cursor: pointer;">${__("Setup Now")}</a>`,
                "orange"
            );
            frm.layout.wrapper
                .off("click.hamptons_setup")
                .on("click.hamptons_setup", ".hamptons-setup-now", () => this.open_setup_dialog(frm));
        });
    },

    open_setup_dialog(frm) {
        this.get_status(frm).then((status) => {
            if (!status) return;
            const need_leave = status.pending.includes(this.LEAVE_STEP);
            const need_shift = status.pending.includes(this.SHIFT_STEP);
            const employee_label = status.employee_name || status.employee;

            if (!need_leave && !need_shift) {
                frappe.msgprint({
                    title: __("Nothing Pending for {0}", [employee_label]),
                    indicator: "green",
                    message: this.status_html(status),
                });
                return;
            }

            const fields = [
                { fieldtype: "HTML", fieldname: "current_status", options: this.status_html(status) },
            ];

            if (need_shift) {
                fields.push(
                    { fieldtype: "Section Break", label: __("Shift") },
                    {
                        fieldtype: "Link",
                        fieldname: "shift_type",
                        options: "Shift Type",
                        label: __("Which shift will this employee work?"),
                        reqd: 1,
                        default: status.default_shift || undefined,
                    },
                    { fieldtype: "Column Break" },
                    {
                        fieldtype: "Date",
                        fieldname: "shift_start_date",
                        label: __("Shift Start Date"),
                        description: __("Defaults to the Date of Joining"),
                        reqd: 1,
                        default: status.date_of_joining || frappe.datetime.get_today(),
                    }
                );
            }

            if (need_leave) {
                fields.push(
                    { fieldtype: "Section Break", label: __("Leave") },
                    {
                        fieldtype: "Link",
                        fieldname: "leave_policy",
                        options: "Leave Policy",
                        label: __("Leave Policy"),
                        reqd: 1,
                        default: status.default_leave_policy || undefined,
                        get_query: () => ({ filters: { docstatus: 1 } }),
                    },
                    { fieldtype: "Column Break" },
                    {
                        fieldtype: "Link",
                        fieldname: "leave_period",
                        options: "Leave Period",
                        label: __("Leave Period"),
                        description: __("Leave Allocations are created for this period"),
                        reqd: 1,
                        default: status.default_leave_period ? status.default_leave_period.name : undefined,
                        get_query: () => ({ filters: { is_active: 1, company: frm.doc.company } }),
                    }
                );
            }

            const dialog = new frappe.ui.Dialog({
                title: __("Setup New Employee: {0}", [employee_label]),
                fields: fields,
                primary_action_label: __("Create"),
                primary_action: (values) => {
                    const args = { employee: frm.doc.name };
                    if (need_shift) {
                        args.shift_type = values.shift_type;
                        args.shift_start_date = values.shift_start_date;
                    }
                    if (need_leave) {
                        args.leave_policy = values.leave_policy;
                        args.leave_period = values.leave_period;
                    }

                    dialog.disable_primary_action();
                    frappe
                        .call({
                            method: "hamptons.api.employee_setup.setup_new_employee",
                            args: args,
                            freeze: true,
                            freeze_message: __("Setting up {0}...", [employee_label]),
                        })
                        .then((r) => {
                            dialog.hide();
                            this.show_result(r.message);
                            frm.reload_doc();
                        })
                        .always(() => dialog.enable_primary_action());
                },
            });
            dialog.show();
        });
    },

    link(doctype, name) {
        return frappe.utils.get_form_link(doctype, name, true);
    },

    pill(color, text) {
        return `<span class="indicator-pill ${color}">${text}</span>`;
    },

    // Current state table shown at the top of the dialog.
    status_html(status) {
        const lpa = status.leave_policy_assignment;
        const sa = status.shift_assignment;
        const esc = frappe.utils.escape_html;
        const date = frappe.datetime.str_to_user;
        const pending = `${this.pill("orange", __("Pending"))} ${__("Will be created now")}`;

        const lpa_cell = lpa
            ? `${this.pill("green", __("Done"))} ${this.link(this.LEAVE_STEP, lpa.name)} &middot; ${esc(lpa.leave_policy)} (${date(lpa.effective_from)} &ndash; ${date(lpa.effective_to)})`
            : pending;

        let allocation_cell;
        if (!lpa) {
            allocation_cell = `${this.pill("orange", __("Pending"))} ${__("Created automatically with the Leave Policy Assignment")}`;
        } else if (lpa.leaves_allocated) {
            allocation_cell = `${this.pill("green", __("Done"))} ${__("Created with the Leave Policy Assignment")}`;
        } else {
            allocation_cell = `${this.pill("orange", __("Not granted"))} ${__("Open the Leave Policy Assignment and use Grant Leaves")}`;
        }

        const sa_cell = sa
            ? `${this.pill("green", __("Done"))} ${this.link(this.SHIFT_STEP, sa.name)} &middot; ${esc(sa.shift_type)} (${__("from")} ${date(sa.start_date)})`
            : pending;

        const missing = status.missing_attributes || [];
        const hint =
            !lpa && missing.length
                ? `<p class="text-muted small" style="margin: 0 0 0.5rem 0;">
                    ${frappe.utils.icon("solid-warning", "xs")}
                    ${__("{0} not set on the employee: leave types restricted by these will be skipped. Set them first if they apply.", [
                        esc(missing.join(", ")),
                    ])}
                   </p>`
                : "";

        return `
            <table class="table table-bordered table-sm" style="margin-bottom: 0.5rem;">
                <tr><td style="width: 35%;">${__("Leave Policy Assignment")}</td><td>${lpa_cell}</td></tr>
                <tr><td>${__("Leave Allocation")}</td><td>${allocation_cell}</td></tr>
                <tr><td>${__("Shift Assignment")}</td><td>${sa_cell}</td></tr>
            </table>${hint}`;
    },

    // Per-step outcome after the server call.
    show_result(result) {
        if (!result) return;
        const esc = frappe.utils.escape_html;
        const pills = {
            created: ["green", __("Created")],
            skipped: ["blue", __("Skipped")],
            failed: ["red", __("Failed")],
        };

        const step_row = (doctype, step, extra = "") => {
            const [color, text] = pills[step.status] || ["gray", step.status];
            const name = step.name ? `${this.link(doctype, step.name)} &middot; ` : "";
            return `<tr><td style="width: 35%;">${__(doctype)}</td>
                <td>${this.pill(color, text)} ${name}${step.message || ""}${extra}</td></tr>`;
        };

        const allocations = (result.leave_allocations || [])
            .map(
                (a) =>
                    `<li>${esc(a.leave_type)}: ${a.new_leaves_allocated} ${__("day(s)")} (${this.link("Leave Allocation", a.name)})</li>`
            )
            .join("");
        const allocation_list = allocations
            ? `<ul style="margin: 0.25rem 0 0 0; padding-left: 1.25rem;">${allocations}</ul>`
            : "";

        const steps = [result.leave_policy_assignment, result.shift_assignment];
        const any_failed = steps.some((s) => s.status === "failed");

        frappe.msgprint({
            title: __("Employee Setup: {0}", [result.employee_name || result.employee]),
            indicator: any_failed ? "red" : "green",
            message: `
                <table class="table table-bordered table-sm">
                    ${step_row(this.LEAVE_STEP, result.leave_policy_assignment, allocation_list)}
                    ${step_row(this.SHIFT_STEP, result.shift_assignment)}
                </table>`,
        });
    },
};
