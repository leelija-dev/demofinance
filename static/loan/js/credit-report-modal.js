/* Equifax IDCR-style credit report renderer for the pre-application check modal.
   window.buildCreditReportHtml(report, check) -> HTML string
   window.printCreditReport(report, check) -> opens A4-formatted print/PDF dialog */
(function () {
    'use strict';

    var BRAND_COLOR = '#003A70';
    var CSS_HREF = '/static/loan/css/credit-report-idcr.css';

    function esc(v) {
        if (v === null || v === undefined || v === '') return '-';
        return String(v)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function inr(v) {
        if (v === null || v === undefined || v === '') return '-';
        var n = Number(v);
        return isNaN(n) ? esc(v) : '\u20B9' + n.toLocaleString('en-IN');
    }

    function section(title, inner, flow) {
        var cls = 'idcr-section' + (flow ? ' idcr-section-flow' : ' idcr-section-compact');
        return '<div class="' + cls + '"><div class="idcr-section-hd">' + esc(title) + '</div>' +
            '<div class="idcr-section-bd">' + inner + '</div></div>';
    }

    function kv(label, value) {
        return '<div class="idcr-kv"><span class="idcr-kv-lbl">' + esc(label) + ': </span>' +
            '<span class="idcr-kv-val">' + value + '</span></div>';
    }

    function kvGrid(pairs, cols) {
        var cls = cols === 4 ? 'idcr-cols-4' : 'idcr-cols-3';
        return '<div class="' + cls + '">' +
            pairs.map(function (p) { return '<div>' + kv(p[0], p[1]) + '</div>'; }).join('') +
            '</div>';
    }

    function table(headers, rows) {
        var head = '<tr>' + headers.map(function (h) {
            return '<th>' + esc(h) + '</th>';
        }).join('') + '</tr>';
        var body = rows.map(function (r) {
            return '<tr>' + r.map(function (c) {
                return '<td>' + c + '</td>';
            }).join('') + '</tr>';
        }).join('');
        return '<div class="idcr-table-wrap"><table class="idcr-table">' + head + body + '</table></div>';
    }

    function paymentHistoryTable(history) {
        if (!history || !history.length) return '';
        var html = '<div class="idcr-ph-title">Payment History (' + history.length + ' Months)</div>';
        for (var i = 0; i < history.length; i += 12) {
            var chunk = history.slice(i, i + 12);
            var statusCells = chunk.map(function (h) {
                var st = h.status === null || h.status === undefined ? '*' : String(h.status);
                var bad = /^(0*[1-9]\d*\+?|DPD|SUB|LSS|DBT|1[0-9]{2}\+?|[3-9]0\+?)/.test(st) && st !== '000' && st !== 'STD' && st !== 'NEW' && st !== 'CLSD';
                return '<td class="' + (bad ? 'idcr-ph-bad' : '') + '">' + esc(st) + '</td>';
            }).join('');
            var suitFiledCells = chunk.map(function (h) {
                return '<td>' + esc(h.suit_filed === null || h.suit_filed === undefined ? '*' : h.suit_filed) + '</td>';
            }).join('');
            var assetCells = chunk.map(function (h) {
                return '<td>' + esc(h.asset_class === null || h.asset_class === undefined ? '*' : h.asset_class) + '</td>';
            }).join('');
            var monthCells = chunk.map(function (h) {
                return '<td class="idcr-ph-month">' + esc(h.month) + '</td>';
            }).join('');
            html += '<table class="idcr-ph-table">' +
                '<tr><td class="idcr-ph-label">Payment Status</td>' + statusCells + '</tr>' +
                '<tr><td class="idcr-ph-label">Suit Filed</td>' + suitFiledCells + '</tr>' +
                '<tr><td class="idcr-ph-label">Asset Classification</td>' + assetCells + '</tr>' +
                '<tr><td class="idcr-ph-label">Month</td>' + monthCells + '</tr>' +
                '</table>';
        }
        return html;
    }

    function accountCard(a) {
        var cols = [
            [
                kv('Acct #', esc(a.account_number)),
                kv('Institution', esc(a.institution)),
                kv('Type', esc(a.account_type)),
                kv('Ownership Type', esc(a.ownership)),
                kv('Repayment Tenure', esc(a.repayment_tenure)),
                kv('Dispute Code', esc(a.dispute_code)),
                kv('Suit Filed Status', esc(a.suit_filed_status)),
            ],
            [
                kv('Balance', inr(a.balance)),
                kv('Past Due Amount', inr(a.past_due_amount)),
                kv('Last Payment', inr(a.last_payment)),
                kv('Term Frequency', esc(a.term_frequency)),
                kv('Monthly Payment Amount', inr(a.monthly_payment)),
                kv('Writeoff Amount', inr(a.writeoff_amount)),
                kv('Asset Classification', esc(a.asset_classification)),
            ],
            [
                kv('Open', esc(a.open)),
                kv('Interest Rate', esc(a.interest_rate)),
                kv('Last Payment Date', esc(a.last_payment_date)),
                kv('Sanction Amount', inr(a.sanction_amount)),
                kv('Credit Limit', inr(a.credit_limit)),
                kv('Account Status', esc(a.account_status)),
                kv('Date Reported', esc(a.date_reported)),
            ],
            [
                kv('Date Opened', esc(a.date_opened)),
                kv('Date Closed', esc(a.date_closed)),
                kv('Reason', esc(a.reason)),
                kv('Collateral Value', esc(a.collateral_value)),
                kv('Collateral Type', esc(a.collateral_type)),
            ],
        ];
        return '<div class="idcr-account"><div class="idcr-account-hd"><div class="idcr-cols-4">' +
            cols.map(function (c) { return '<div>' + c.join('') + '</div>'; }).join('') +
            '</div></div>' + paymentHistoryTable(a.payment_history) + '</div>';
    }

    function formatPrintDateTimeParts() {
        var parts = new Intl.DateTimeFormat('en-GB', {
            timeZone: 'Asia/Kolkata',
            day: 'numeric',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        }).formatToParts(new Date());
        var day = '';
        var month = '';
        var year = '';
        var hour = '';
        var minute = '';
        parts.forEach(function (p) {
            if (p.type === 'day') day = p.value;
            if (p.type === 'month') month = p.value.toLowerCase();
            if (p.type === 'year') year = p.value;
            if (p.type === 'hour') hour = p.value;
            if (p.type === 'minute') minute = p.value;
        });
        return { date: day + ' ' + month + ' ' + year, time: hour + ':' + minute };
    }

    window.buildCreditReportHtml = function (report, check, options) {
        if (!report) return '<p class="idcr-empty">No report data available.</p>';
        options = options || {};
        var forPrint = !!options.forPrint;
        var p = report.personal || {};
        var idn = report.identification || {};
        var score = report.score || {};
        var s = report.account_summary || {};
        var ra = report.recent_activity || {};
        var eqs = report.enquiry_summary || {};
        var html = '';

        if (report.is_mock && !forPrint) {
            html += '<div class="idcr-mock-banner">Mock data (Surepass sandbox mock mode) &mdash; not a real bureau report.</div>';
        }

        html += '<div class="idcr-header">' +
            '<div class="idcr-header-top">' +
            '<div class="idcr-header-title">Retail Credit Report (IDCR)</div>';
        if (forPrint) {
            var dt = formatPrintDateTimeParts();
            html += '<div class="idcr-print-datetime">' +
                '<div class="idcr-print-date-line"><span class="idcr-print-lbl">Date :</span> ' + esc(dt.date) + '</div>' +
                '<div class="idcr-print-time-line"><span class="idcr-print-lbl">Time :</span> ' + esc(dt.time) + '</div>' +
                '</div>';
        }
        html += '</div>' +
            '<div class="idcr-header-sub">EQUIFAX &mdash; Equifax Credit Information Private Limited</div></div>';

        var phones = (report.phones || []).map(function (ph) {
            return kv('Mobile', esc(ph.number) + (ph.reported_date ? ' (' + esc(ph.reported_date) + ')' : ''));
        }).join('') || kv('Mobile', '-');
        var emails = (report.emails || []).map(function (em) {
            return kv('Email', esc(em.email) + (em.reported_date ? ' (' + esc(em.reported_date) + ')' : ''));
        }).join('');

        html += '<div class="idcr-top-row">' +
            section('Personal Information',
                kv('Name', esc(p.name)) + kv('DOB', esc(p.date_of_birth)) + kv('Age', esc(p.age)) +
                kv('Gender', esc(p.gender)) + kv('Total Income', esc(p.total_income)) + kv('Occupation', esc(p.occupation))) +
            section('Identification',
                kv('PAN', esc(idn.pan)) + kv('Voter ID', esc(idn.voter_id)) + kv('Passport ID', esc(idn.passport)) +
                kv('UID', esc(idn.uid)) + kv('Driver License', esc(idn.driver_license)) + kv('Other ID', esc(idn.other_id))) +
            section('Contact Details', phones + emails) +
            '</div>';

        if ((report.addresses || []).length) {
            var addrRows = report.addresses.map(function (ad, i) {
                return [String(i + 1), esc(ad.address), esc(ad.state), esc(ad.postal), esc(ad.type), esc(ad.reported_date)];
            });
            html += section('Consumer Address:', table(['Seq', 'Address', 'State', 'Postal', 'Type', 'Date Reported'], addrRows));
        }

        var scoreInner = '<div class="idcr-score-row"><div>' +
            '<div class="idcr-score-num">' + esc(score.value) + '</div>';
        if (check && check.decision === 'pass') {
            scoreInner += '<span class="idcr-badge" style="background:#22c55e">Pass</span>';
        } else if (check && check.decision === 'fail') {
            scoreInner += '<span class="idcr-badge" style="background:#ef4444">Below Minimum</span>';
        }
        scoreInner += '</div><div>' +
            kv('Score Type', esc(score.type)) + kv('Score Name', esc(score.name)) + kv('Score Version', esc(score.version)) +
            ((score.factors || []).length ? '<div class="idcr-kv"><span class="idcr-kv-lbl">Scoring Factors: </span>' +
                '<span class="idcr-kv-val">' + score.factors.map(esc).join(', ') + '</span></div>' : '') +
            '</div></div>';
        html += section('Equifax Score(s):', scoreInner);

        html += section('Retail Account Summary:', kvGrid([
            ['No Of Accounts', esc(s.no_of_accounts)],
            ['No Of Active Accounts', esc(s.active_accounts)],
            ['No Of Write-Offs', esc(s.write_offs)],
            ['No Of Past Due Accounts', esc(s.past_due_accounts)],
            ['No Of Zero Balance Accounts', esc(s.zero_balance_accounts)],
            ['Recent Account', esc(s.recent_account)],
            ['Oldest Account', esc(s.oldest_account)],
            ['Most Severe Status (24 Months)', esc(s.most_severe_status_24m)],
            ['Single Highest Balance', inr(s.single_highest_balance)],
            ['Single Highest Credit', inr(s.single_highest_credit)],
            ['Single Highest Sanction Amount', inr(s.single_highest_sanction)],
            ['Average Open Balance', inr(s.average_open_balance)],
            ['Total Past Due', inr(s.total_past_due)],
            ['Total Credit Limit', inr(s.total_credit_limit)],
            ['Total High Credit', inr(s.total_high_credit)],
            ['Total Sanction Amount', inr(s.total_sanction)],
            ['Total Balance Amount', inr(s.total_balance)],
            ['Total Monthly Payment Amount', inr(s.total_monthly_payment)],
        ], 3));

        if ((report.accounts || []).length) {
            html += section('Retail Accounts: (' + report.accounts.length + ')',
                report.accounts.map(accountCard).join(''), true);
        }

        html += section('Recent Activity:', table(
            ['Total Inquiries', 'Accounts Opened', 'Accounts Updated', 'Accounts Delinquent'],
            [[esc(ra.total_inquiries), esc(ra.accounts_opened), esc(ra.accounts_updated), esc(ra.accounts_delinquent)]]
        ));

        var enqRows = (report.enquiries || []).map(function (q) {
            return [esc(q.institution), esc(q.date), esc(q.purpose), inr(q.amount)];
        });
        html += section('Enquiries:', enqRows.length
            ? table(['Institution', 'Date', 'Purpose', 'Amount'], enqRows)
            : '<p class="idcr-empty">No enquiries reported.</p>');

        html += section('Enquiries Summary:', table(
            ['Purpose', 'Total', 'Past 30 Days', 'Past 12 Months', 'Past 24 Months', 'Recent'],
            [[esc(eqs.purpose), esc(eqs.total), esc(eqs.past_30_days), esc(eqs.past_12_months), esc(eqs.past_24_months), esc(eqs.recent)]]
        ));

        return '<div class="idcr-report">' + html + '</div>';
    };

    var CRITICAL_PRINT_CSS =
        '@page{size:A4 portrait;margin:0;}' +
        'html,body{margin:0;padding:0;background:#fff;}' +
        '.idcr-print-frame{box-sizing:border-box;width:100%;padding:12mm 14mm;background:#fff;}' +
        '@media print{.idcr-print-frame{padding:12mm 14mm !important;}}';

    function openPrintDocument(content, title) {
        var printWin = window.open('', '_blank');
        if (!printWin) {
            alert('Please allow pop-ups to download the PDF.');
            return;
        }

        function writeAndPrint(cssText) {
            printWin.document.open();
            printWin.document.write(
                '<!DOCTYPE html><html class="idcr-print-root"><head><meta charset="utf-8">' +
                '<title>' + esc(title) + '</title>' +
                '<style>' + CRITICAL_PRINT_CSS + (cssText || '') + '</style>' +
                '</head><body class="idcr-print-body">' +
                '<div class="idcr-print-frame">' + content + '</div>' +
                '</body></html>'
            );
            printWin.document.close();
            var printed = false;
            function doPrint() {
                if (printed) return;
                printed = true;
                printWin.focus();
                printWin.print();
            }
            printWin.onload = doPrint;
            setTimeout(doPrint, 600);
        }

        if (window.fetch) {
            fetch(CSS_HREF, { credentials: 'same-origin' })
                .then(function (r) { return r.ok ? r.text() : ''; })
                .then(writeAndPrint)
                .catch(function () { writeAndPrint(''); });
        } else {
            writeAndPrint('');
        }
    }

    window.printCreditReport = function (report, check) {
        if (!report) return;
        var content = window.buildCreditReportHtml(report, check, { forPrint: true });
        var title = 'Equifax_Credit_Report';
        if (report.personal && report.personal.name) {
            title = String(report.personal.name).replace(/[^\w\-]+/g, '_').substring(0, 40);
        }
        openPrintDocument(content, title);
    };
})();
