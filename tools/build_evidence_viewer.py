#!/usr/bin/env python3
"""
OTP Evidence Viewer Generator

Reads OTP evidence receipt JSON files and produces a self-contained
HTML viewer with Windows XP aesthetic. Works offline from file:// protocol.

Usage:
    py tools/build_evidence_viewer.py evidence/receipt.json
    py tools/build_evidence_viewer.py evidence/receipt.json -o viewer.html
"""

import argparse
import json
import sys
from pathlib import Path


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OTP Evidence Viewer</title>
<style>
/* ============================================================
   WINDOWS XP AESTHETIC
   ============================================================ */

* { margin: 0; padding: 0; box-sizing: border-box; }

body {{
    font-family: Tahoma, "MS Sans Serif", Arial, sans-serif;
    font-size: 11px;
    background: #ECE9D8;
    color: #000;
    min-height: 100vh;
}}

/* Title bar */
.title-bar {{
    background: linear-gradient(180deg, #0A246A 0%, #3C82D6 8%, #0A246A 100%);
    color: white;
    padding: 4px 8px;
    font-size: 12px;
    font-weight: bold;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.title-bar .icon {{ font-size: 16px; }}
.title-bar .title {{ flex: 1; }}
.title-bar .close {{
    background: #C0392B;
    color: white;
    border: 1px outset #E74C3C;
    padding: 1px 6px;
    font-size: 11px;
    font-weight: bold;
    cursor: pointer;
}}
.title-bar .close:hover {{ background: #E74C3C; }}

/* Window frame */
.window {{
    border: 2px outset #D4D0C8;
    margin: 4px;
    background: #ECE9D8;
}}

/* Menu bar */
.menu-bar {{
    background: #ECE9D8;
    border-bottom: 1px solid #ACA899;
    padding: 2px 4px;
    display: flex;
    gap: 0;
}}
.menu-bar .menu-item {{
    padding: 2px 8px;
    cursor: pointer;
}}
.menu-bar .menu-item:hover {{
    background: #316AC5;
    color: white;
}}

/* Status bar */
.status-bar {{
    background: #ECE9D8;
    border-top: 1px solid #ACA899;
    padding: 2px 8px;
    font-size: 10px;
    color: #444;
    display: flex;
    gap: 16px;
}}
.status-bar .section {{
    border: 1px inset #D4D0C8;
    padding: 1px 6px;
    flex: 1;
}}

/* Tab control */
.tabs {{
    display: flex;
    border-bottom: 1px solid #ACA899;
    padding: 0 4px;
    background: #ECE9D8;
}}
.tab {{
    padding: 4px 12px;
    border: 1px solid #ACA899;
    border-bottom: none;
    background: #D4D0C8;
    cursor: pointer;
    margin-right: 2px;
    position: relative;
    top: 1px;
}}
.tab.active {{
    background: #ECE9D8;
    border-bottom: 1px solid #ECE9D8;
    font-weight: bold;
}}
.tab:hover:not(.active) {{
    background: #C8C4BC;
}}

/* Tab content */
.tab-content {{
    display: none;
    padding: 8px;
}}
.tab-content.active {{
    display: block;
}}

/* Group box */
.group-box {{
    border: 1px solid #ACA899;
    margin: 8px 0;
    padding: 12px 8px 8px 8px;
    position: relative;
}}
.group-box .label {{
    background: #ECE9D8;
    padding: 0 4px;
    position: absolute;
    top: -8px;
    left: 8px;
    font-weight: bold;
    font-size: 11px;
}}

/* Fields */
.field {{
    display: flex;
    margin: 3px 0;
    align-items: flex-start;
}}
.field-label {{
    width: 140px;
    font-weight: bold;
    color: #003399;
    flex-shrink: 0;
}}
.field-value {{
    flex: 1;
    word-break: break-all;
}}
.field-value code {{
    background: #FFF;
    border: 1px inset #D4D0C8;
    padding: 1px 4px;
    font-family: "Lucida Console", "Courier New", monospace;
    font-size: 10px;
}}

/* Verdict badge */
.verdict {{
    display: inline-block;
    padding: 2px 8px;
    font-weight: bold;
    border: 2px outset;
    font-size: 12px;
}}
.verdict-ACTION_REQUESTED {{ background: #FF6B6B; color: #000; border-color: #FF8888; }}
.verdict-NO_ACTION {{ background: #90EE90; color: #000; border-color: #98FB98; }}
.verdict-BLOCKED {{ background: #FFB347; color: #000; border-color: #FFC87C; }}
.verdict-NEEDS_REVIEW {{ background: #FFD700; color: #000; border-color: #FFE44D; }}
.verdict-NOT_DEMONSTRATED {{ background: #D3D3D3; color: #000; border-color: #DCDCDC; }}

/* Finding status */
.status-PASS {{ color: #008000; font-weight: bold; }}
.status-FAIL {{ color: #CC0000; font-weight: bold; }}
.status-UNKNOWN {{ color: #666; font-style: italic; }}

/* Severity */
.severity-HIGH {{ color: #CC0000; font-weight: bold; }}
.severity-INFO {{ color: #0066CC; }}

/* Component cards */
.component {{
    border: 1px solid #ACA899;
    margin: 4px 0;
    background: #FFF;
}}
.component-header {{
    background: #E8E4DC;
    padding: 4px 8px;
    font-weight: bold;
    border-bottom: 1px solid #ACA899;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.component-header:hover {{
    background: #D8D4CC;
}}
.component-header .arrow {{
    font-size: 8px;
}}
.component-body {{
    padding: 8px;
    display: none;
}}
.component-body.open {{
    display: block;
}}
.component-body pre {{
    background: #FFF;
    border: 1px inset #D4D0C8;
    padding: 4px;
    font-family: "Lucida Console", "Courier New", monospace;
    font-size: 10px;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 300px;
    overflow-y: auto;
}}

/* SHA-256 display */
.sha256 {{
    font-family: "Lucida Console", "Courier New", monospace;
    font-size: 10px;
    background: #F5F5DC;
    border: 1px inset #D4D0C8;
    padding: 2px 4px;
    word-break: break-all;
}}

/* Verification button */
.verify-btn {{
    background: #D4D0C8;
    border: 2px outset #D4D0C8;
    padding: 4px 16px;
    font-family: Tahoma, "MS Sans Serif", Arial, sans-serif;
    font-size: 11px;
    cursor: pointer;
}}
.verify-btn:hover {{
    background: #C8C4BC;
}}
.verify-btn:active {{
    border-style: inset;
}}

/* Verification result */
.verify-result {{
    margin: 8px 0;
    padding: 8px;
    border: 2px inset #D4D0C8;
    font-weight: bold;
}}
.verify-valid {{
    background: #90EE90;
    color: #006400;
}}
.verify-invalid {{
    background: #FFB3B3;
    color: #8B0000;
}}

/* Limitations box */
.limitations {{
    background: #FFFACD;
    border: 1px solid #DAA520;
    padding: 8px;
    margin: 8px 0;
    font-size: 10px;
}}
.limitations .title {{
    font-weight: bold;
    color: #8B4513;
    margin-bottom: 4px;
}}

/* Ledger chain */
.ledger-chain {{
    font-family: "Lucida Console", "Courier New", monospace;
    font-size: 9px;
    background: #1E1E1E;
    color: #0F0;
    padding: 8px;
    border: 2px inset #444;
    overflow-x: auto;
    white-space: pre;
}}

/* XP-style scrollbar */
::-webkit-scrollbar {{ width: 16px; height: 16px; }}
::-webkit-scrollbar-track {{ background: #ECE9D8; border: 1px inset #D4D0C8; }}
::-webkit-scrollbar-thumb {{
    background: #D4D0C8;
    border: 2px outset #D4D0C8;
}}
::-webkit-scrollbar-thumb:hover {{ background: #C8C4BC; }}
::-webkit-scrollbar-button {{
    background: #D4D0C8;
    border: 1px outset #D4D0C8;
    height: 16px;
}}
</style>
</head>
<body>

<!-- Title Bar -->
<div class="title-bar">
    <span class="icon">📋</span>
    <span class="title">OTP Evidence Viewer - $execution_id</span>
    <span class="close" onclick="window.close()">X</span>
</div>

<div class="window">

<!-- Menu Bar -->
<div class="menu-bar">
    <span class="menu-item" onclick="verifyReceipt()">🔍 Verify</span>
    <span class="menu-item" onclick="downloadEvidence()">💾 Save As...</span>
    <span class="menu-item" onclick="copyHash()">📋 Copy Hash</span>
    <span class="menu-item" onclick="toggleTheme()">🌙 Theme</span>
</div>

<!-- Tabs -->
<div class="tabs">
    <div class="tab active" onclick="switchTab('overview')">Overview</div>
    <div class="tab" onclick="switchTab('event')">Event</div>
    <div class="tab" onclick="switchTab('finding')">Finding</div>
    <div class="tab" onclick="switchTab('action')">Action</div>
    <div class="tab" onclick="switchTab('components')">Components</div>
    <div class="tab" onclick="switchTab('raw')">Raw JSON</div>
</div>

<!-- Tab: Overview -->
<div id="tab-overview" class="tab-content active">
    <div class="group-box">
        <span class="label">Execution</span>
        <div class="field">
            <span class="field-label">Execution ID:</span>
            <span class="field-value"><code>$execution_id</code></span>
        </div>
        <div class="field">
            <span class="field-label">Source Adapter:</span>
            <span class="field-value">$source_adapter</span>
        </div>
        <div class="field">
            <span class="field-label">Policy Version:</span>
            <span class="field-value">$policy_version</span>
        </div>
        <div class="field">
            <span class="field-label">Channel Adapter:</span>
            <span class="field-value">$channel_adapter</span>
        </div>
    </div>

    <div class="group-box">
        <span class="label">Verdict</span>
        <div style="text-align: center; padding: 8px;">
            <span class="verdict verdict-$verdict">$verdict</span>
        </div>
    </div>

    <div class="group-box">
        <span class="label">Finding</span>
        <div class="field">
            <span class="field-label">Status:</span>
            <span class="field-value status-$finding_status">$finding_status</span>
        </div>
        <div class="field">
            <span class="field-label">Reason Code:</span>
            <span class="field-value"><code>$finding_reason_code</code></span>
        </div>
        <div class="field">
            <span class="field-label">Severity:</span>
            <span class="field-value severity-$finding_severity">$finding_severity</span>
        </div>
        <div class="field">
            <span class="field-label">Action Recommended:</span>
            <span class="field-value">$finding_action_recommended</span>
        </div>
        <div class="field">
            <span class="field-label">Description:</span>
            <span class="field-value">$finding_reason</span>
        </div>
    </div>

    <div class="group-box">
        <span class="label">Receipt Integrity</span>
        <div class="field">
            <span class="field-label">Receipt SHA-256:</span>
            <span class="field-value"><span class="sha256" id="receipt-hash">$receipt_sha256</span></span>
        </div>
        <div class="field">
            <span class="field-label">Previous Receipt:</span>
            <span class="field-value"><span class="sha256">$previous_receipt_sha256</span></span>
        </div>
        <div style="margin-top: 8px; text-align: center;">
            <button class="verify-btn" onclick="verifyReceipt()">🔍 Verify Integrity</button>
        </div>
        <div id="verify-result" class="verify-result" style="display: none;"></div>
    </div>

    <div class="limitations">
        <div class="title">⚠️ Limitations</div>
        <ul>
            <li>Integrity verification does not replay external provider behavior.</li>
            <li>An unanchored append-only chain cannot detect tail truncation.</li>
        </ul>
    </div>
</div>

<!-- Tab: Event -->
<div id="tab-event" class="tab-content">
    <div class="group-box">
        <span class="label">Operational Event</span>
        <div class="field">
            <span class="field-label">Event ID:</span>
            <span class="field-value"><code>$event_id</code></span>
        </div>
        <div class="field">
            <span class="field-label">Source:</span>
            <span class="field-value">$event_source</span>
        </div>
        <div class="field">
            <span class="field-label">Event Type:</span>
            <span class="field-value">$event_source_event_type</span>
        </div>
        <div class="field">
            <span class="field-label">Source Ref:</span>
            <span class="field-value"><code>$event_source_ref</code></span>
        </div>
        <div class="field">
            <span class="field-label">Entity Type:</span>
            <span class="field-value">$event_entity_type</span>
        </div>
        <div class="field">
            <span class="field-label">Entity ID:</span>
            <span class="field-value"><code>$event_entity_id</code></span>
        </div>
        <div class="field">
            <span class="field-label">Observed At:</span>
            <span class="field-value">$event_observed_at</span>
        </div>
        <div class="field">
            <span class="field-label">Payload SHA-256:</span>
            <span class="field-value"><span class="sha256">$event_payload_sha256</span></span>
        </div>
    </div>

    <div class="group-box">
        <span class="label">Payload</span>
        <pre>$event_payload_pretty</pre>
    </div>
</div>

<!-- Tab: Finding -->
<div id="tab-finding" class="tab-content">
    <div class="group-box">
        <span class="label">Finding Details</span>
        <div class="field">
            <span class="field-label">Finding ID:</span>
            <span class="field-value"><code>$finding_id</code></span>
        </div>
        <div class="field">
            <span class="field-label">Rule ID:</span>
            <span class="field-value">$finding_rule_id</span>
        </div>
        <div class="field">
            <span class="field-label">Status:</span>
            <span class="field-value status-$finding_status">$finding_status</span>
        </div>
        <div class="field">
            <span class="field-label">Severity:</span>
            <span class="field-value severity-$finding_severity">$finding_severity</span>
        </div>
        <div class="field">
            <span class="field-label">Subject:</span>
            <span class="field-value"><code>$finding_subject_ref</code></span>
        </div>
        <div class="field">
            <span class="field-label">Reason Code:</span>
            <span class="field-value"><code>$finding_reason_code</code></span>
        </div>
        <div class="field">
            <span class="field-label">Reason:</span>
            <span class="field-value">$finding_reason</span>
        </div>
        <div class="field">
            <span class="field-label">Action Recommended:</span>
            <span class="field-value">$finding_action_recommended</span>
        </div>
        <div class="field">
            <span class="field-label">Evidence Refs:</span>
            <span class="field-value"><code>$finding_evidence_refs</code></span>
        </div>
    </div>

    <div class="group-box">
        <span class="label">Component SHA-256</span>
        <div class="field">
            <span class="field-label">Finding Hash:</span>
            <span class="field-value"><span class="sha256">$sha256_finding</span></span>
        </div>
    </div>
</div>

<!-- Tab: Action -->
<div id="tab-action" class="tab-content">
    <div class="group-box">
        <span class="label">Action Request</span>
        <div class="field">
            <span class="field-label">Action ID:</span>
            <span class="field-value"><code>$action_id</code></span>
        </div>
        <div class="field">
            <span class="field-label">Type:</span>
            <span class="field-value">$action_type</span>
        </div>
        <div class="field">
            <span class="field-label">Target:</span>
            <span class="field-value"><code>$action_target_ref</code></span>
        </div>
        <div class="field">
            <span class="field-label">Channel:</span>
            <span class="field-value">$action_channel</span>
        </div>
        <div class="field">
            <span class="field-label">Urgency:</span>
            <span class="field-value">$action_urgency</span>
        </div>
        <div class="field">
            <span class="field-label">Objective:</span>
            <span class="field-value">$action_objective</span>
        </div>
        <div class="field">
            <span class="field-label">Message:</span>
            <span class="field-value">$action_message</span>
        </div>
        <div class="field">
            <span class="field-label">Require ACK:</span>
            <span class="field-value">$action_require_ack</span>
        </div>
    </div>

    <div class="group-box">
        <span class="label">Action Result</span>
        <div class="field">
            <span class="field-label">Provider:</span>
            <span class="field-value">$result_provider</span>
        </div>
        <div class="field">
            <span class="field-label">Provider Ref:</span>
            <span class="field-value"><code>$result_provider_ref</code></span>
        </div>
        <div class="field">
            <span class="field-label">Status:</span>
            <span class="field-value">$result_status</span>
        </div>
        <div class="field">
            <span class="field-label">Acknowledged:</span>
            <span class="field-value">$result_acknowledged</span>
        </div>
        <div class="field">
            <span class="field-label">Delivery:</span>
            <span class="field-value">$result_delivery</span>
        </div>
        <div class="field">
            <span class="field-label">Reached Ringing:</span>
            <span class="field-value">$result_reached_ringing</span>
        </div>
        <div class="field">
            <span class="field-label">Terminal Cause:</span>
            <span class="field-value">$result_terminal_cause</span>
        </div>
        <div class="field">
            <span class="field-label">Started At:</span>
            <span class="field-value">$result_started_at</span>
        </div>
        <div class="field">
            <span class="field-label">Completed At:</span>
            <span class="field-value">$result_completed_at</span>
        </div>
        <div class="field">
            <span class="field-label">Response:</span>
            <span class="field-value">$result_response</span>
        </div>
    </div>

    <div class="group-box">
        <span class="label">Component SHA-256</span>
        <div class="field">
            <span class="field-label">Action Hash:</span>
            <span class="field-value"><span class="sha256">$sha256_action</span></span>
        </div>
        <div class="field">
            <span class="field-label">Result Hash:</span>
            <span class="field-value"><span class="sha256">$sha256_result</span></span>
        </div>
    </div>
</div>

<!-- Tab: Components -->
<div id="tab-components" class="tab-content">
    <div class="component">
        <div class="component-header" onclick="toggleComponent('comp-event')">
            <span class="arrow" id="arrow-comp-event">▶</span>
            Event Component
            <span class="sha256" style="margin-left: auto;">$sha256_event</span>
        </div>
        <div class="component-body" id="comp-event">
            <pre>$event_json_pretty</pre>
        </div>
    </div>

    <div class="component">
        <div class="component-header" onclick="toggleComponent('comp-lease')">
            <span class="arrow" id="arrow-comp-lease">▶</span>
            Lease Component
            <span class="sha256" style="margin-left: auto;">$sha256_lease</span>
        </div>
        <div class="component-body" id="comp-lease">
            <pre>$lease_json_pretty</pre>
        </div>
    </div>

    <div class="component">
        <div class="component-header" onclick="toggleComponent('comp-finding')">
            <span class="arrow" id="arrow-comp-finding">▶</span>
            Finding Component
            <span class="sha256" style="margin-left: auto;">$sha256_finding</span>
        </div>
        <div class="component-body" id="comp-finding">
            <pre>$finding_json_pretty</pre>
        </div>
    </div>

    <div class="component">
        <div class="component-header" onclick="toggleComponent('comp-action')">
            <span class="arrow" id="arrow-comp-action">▶</span>
            Action Component
            <span class="sha256" style="margin-left: auto;">$sha256_action</span>
        </div>
        <div class="component-body" id="comp-action">
            <pre>$action_json_pretty</pre>
        </div>
    </div>

    <div class="component">
        <div class="component-header" onclick="toggleComponent('comp-result')">
            <span class="arrow" id="arrow-comp-result">▶</span>
            Result Component
            <span class="sha256" style="margin-left: auto;">$sha256_result</span>
        </div>
        <div class="component-body" id="comp-result">
            <pre>$result_json_pretty</pre>
        </div>
    </div>
</div>

<!-- Tab: Raw -->
<div id="tab-raw" class="tab-content">
    <div class="group-box">
        <span class="label">Full Evidence Receipt (JSON)</span>
        <pre style="max-height: 500px; overflow-y: auto;">$receipt_json_pretty</pre>
    </div>
</div>

<!-- Status Bar -->
<div class="status-bar">
    <span class="section">Schema: evidence-receipt/1</span>
    <span class="section">Components: 5</span>
    <span class="section" id="status-verify">Ready</span>
</div>

</div><!-- /window -->

<!-- Evidence JSON embedded for verification -->
<script id="otp-evidence" type="application/json">$receipt_json</script>

<script>
// ============================================================
// OTP EVIDENCE VIEWER — VERIFICATION LOGIC
// ============================================================

const originalRecord = JSON.parse(document.getElementById('otp-evidence').textContent);
let currentRecord = JSON.parse(JSON.stringify(originalRecord));

// Canonical JSON (matches Python otp.canonical.canonical_json)
function canonicalize(value) {
    if (Array.isArray(value)) return value.map(canonicalize);
    if (value !== null && typeof value === 'object') {
        const result = {};
        Object.keys(value).sort().forEach(key => {
            result[key] = canonicalize(value[key]);
        });
        return result;
    }
    return value;
}

// SHA-256 (matches Python otp.canonical.sha256)
async function sha256(value) {
    const canonical = JSON.stringify(canonicalize(value));
    const encoded = new TextEncoder().encode(canonical);
    const digest = await crypto.subtle.digest('SHA-256', encoded);
    return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
}

// Verify receipt integrity
async function verifyReceipt() {
    const resultEl = document.getElementById('verify-result');
    const statusEl = document.getElementById('status-verify');
    resultEl.style.display = 'block';
    resultEl.className = 'verify-result';
    resultEl.innerHTML = 'Verifying...';
    statusEl.textContent = 'Verifying...';

    try {
        // Compute receipt hash (excluding receipt_sha256 field)
        const body = {};
        Object.keys(currentRecord).forEach(key => {
            if (key !== 'receipt_sha256') body[key] = currentRecord[key];
        });
        const computed = await sha256(body);
        const valid = computed === currentRecord.receipt_sha256;

        // Verify component hashes
        const components = currentRecord.components || {};
        const compHashes = currentRecord.component_sha256 || {};
        const componentResults = {};

        for (const [name, comp] of Object.entries(components)) {
            const expected = compHashes[name];
            if (expected && comp) {
                const actual = await sha256(comp);
                componentResults[name] = { valid: actual === expected, expected, actual };
            }
        }

        const allComponentsValid = Object.values(componentResults).every(r => r.valid);

        if (valid && allComponentsValid) {
            resultEl.className = 'verify-result verify-valid';
            resultEl.innerHTML = `
                <div style="font-size: 14px; margin-bottom: 8px;">✅ RECEIPT VALID</div>
                <div>Receipt SHA-256: <span class="sha256">${computed}</span></div>
                <div style="margin-top: 4px;">All ${Object.keys(componentResults).length} component hashes verified.</div>
            `;
            statusEl.textContent = '✅ VALID — All hashes match';
        } else {
            let html = '<div style="font-size: 14px; margin-bottom: 8px;">❌ VERIFICATION FAILED</div>';

            if (!valid) {
                html += `<div>Receipt hash mismatch:<br>`;
                html += `Expected: <span class="sha256">${currentRecord.receipt_sha256}</span><br>`;
                html += `Computed: <span class="sha256">${computed}</span></div>`;
            }

            for (const [name, result] of Object.entries(componentResults)) {
                if (!result.valid) {
                    html += `<div style="margin-top: 4px;">Component "${name}" hash mismatch:<br>`;
                    html += `Expected: <span class="sha256">${result.expected}</span><br>`;
                    html += `Computed: <span class="sha256">${result.actual}</span></div>`;
                }
            }

            resultEl.className = 'verify-result verify-invalid';
            resultEl.innerHTML = html;
            statusEl.textContent = '❌ INVALID — Hash mismatch';
        }
    } catch (e) {
        resultEl.className = 'verify-result verify-invalid';
        resultEl.innerHTML = `<div>❌ ERROR: ${e.message}</div>`;
        statusEl.textContent = '❌ ERROR';
    }
}

// Tab switching
function switchTab(name) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById('tab-' + name).classList.add('active');
}

// Component expand/collapse
function toggleComponent(id) {
    const el = document.getElementById(id);
    const arrow = document.getElementById('arrow-' + id);
    el.classList.toggle('open');
    arrow.textContent = el.classList.contains('open') ? '▼' : '▶';
}

// Download evidence
function downloadEvidence() {
    const blob = new Blob([JSON.stringify(currentRecord, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = currentRecord.execution_id + '.json';
    a.click();
    URL.revokeObjectURL(url);
}

// Copy hash
function copyHash() {
    navigator.clipboard.writeText(currentRecord.receipt_sha256);
    document.getElementById('status-verify').textContent = '📋 Hash copied!';
    setTimeout(() => {
        document.getElementById('status-verify').textContent = 'Ready';
    }, 2000);
}

// Theme toggle (light mode)
let darkTheme = true;
function toggleTheme() {
    darkTheme = !darkTheme;
    if (darkTheme) {
        document.body.style.background = '#ECE9D8';
        document.querySelectorAll('.component-body pre, .tab-content pre').forEach(el => {
            el.style.background = '#FFF';
            el.style.color = '#000';
        });
    } else {
        document.body.style.background = '#1E1E1E';
        document.querySelectorAll('.component-body pre, .tab-content pre').forEach(el => {
            el.style.background = '#2D2D2D';
            el.style.color = '#D4D4D4';
        });
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'v' || e.key === 'V') verifyReceipt();
    if (e.key === 'e' || e.key === 'E') downloadEvidence();
    if (e.key === 'c' || e.key === 'C') copyHash();
});
</script>

</body>
</html>"""


def escape_html(s):
    """Escape HTML special characters."""
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_viewer(receipt: dict) -> str:
    """Build the HTML viewer from a receipt dict."""
    components = receipt.get("components", {})
    comp_hashes = receipt.get("component_sha256", {})

    event = components.get("event", {})
    lease = components.get("lease", {})
    finding = components.get("finding", {})
    action = components.get("action", {})
    result = components.get("result", {})

    # Extract verdict (may be dict or string)
    verdict = receipt.get("verdict", "UNKNOWN")
    if isinstance(verdict, dict):
        verdict = verdict.get("name", str(verdict))

    # Finding fields
    finding_status = finding.get("status", "UNKNOWN")
    if isinstance(finding_status, int):
        status_map = {0: "PASS", 1: "FAIL", 2: "UNKNOWN"}
        finding_status = status_map.get(finding_status, "UNKNOWN")

    finding_severity = finding.get("severity", "INFO")
    finding_action_rec = finding.get("action_recommended", False)
    if isinstance(finding_action_rec, bool):
        finding_action_rec = "Yes" if finding_action_rec else "No"

    # Result fields
    result_ack = result.get("acknowledged", False)
    if isinstance(result_ack, bool):
        result_ack = "Yes" if result_ack else "No"

    # Event payload
    event_payload = event.get("payload", {})
    event_payload_pretty = json.dumps(event_payload, indent=2, default=str)
    event_payload_sha256 = event.get("payload_sha256", "")

    # JSON for raw tab
    receipt_json = json.dumps(receipt, indent=2, default=str)
    receipt_json_escaped = escape_html(receipt_json)

    # Component JSONs
    event_json_pretty = escape_html(json.dumps(event, indent=2, default=str))
    lease_json_pretty = escape_html(json.dumps(lease, indent=2, default=str))
    finding_json_pretty = escape_html(json.dumps(finding, indent=2, default=str))
    action_json_pretty = escape_html(json.dumps(action, indent=2, default=str))
    result_json_pretty = escape_html(json.dumps(result, indent=2, default=str))

    # Evidence refs
    finding_evidence_refs = ", ".join(finding.get("evidence_refs", []))

    # Previous receipt
    prev_hash = receipt.get("previous_receipt_sha256")
    if prev_hash is None:
        prev_hash = "(none — first receipt)"

    # Title
    title = f"OTP Evidence — {receipt.get('execution_id', 'unknown')}"

    # Apply template
    html = HTML_TEMPLATE
    replacements = {
        "$execution_id": escape_html(receipt.get("execution_id", "")),
        "$source_adapter": escape_html(receipt.get("source_adapter", "")),
        "$policy_version": escape_html(receipt.get("policy_version", "")),
        "$channel_adapter": escape_html(receipt.get("channel_adapter", "")),
        "$verdict": escape_html(verdict),
        "$receipt_sha256": escape_html(receipt.get("receipt_sha256", "")),
        "$previous_receipt_sha256": escape_html(prev_hash),
        "$event_id": escape_html(event.get("event_id", "")),
        "$event_source": escape_html(event.get("source", "")),
        "$event_source_event_type": escape_html(event.get("source_event_type", "")),
        "$event_source_ref": escape_html(event.get("source_ref", "")),
        "$event_entity_type": escape_html(event.get("entity_type", "")),
        "$event_entity_id": escape_html(event.get("entity_id", "")),
        "$event_observed_at": escape_html(event.get("observed_at", "")),
        "$event_payload_sha256": escape_html(event_payload_sha256),
        "$event_payload_pretty": escape_html(event_payload_pretty),
        "$finding_id": escape_html(finding.get("finding_id", "")),
        "$finding_rule_id": escape_html(finding.get("rule_id", "")),
        "$finding_status": escape_html(finding_status),
        "$finding_severity": escape_html(finding_severity),
        "$finding_subject_ref": escape_html(finding.get("subject_ref", "")),
        "$finding_reason_code": escape_html(finding.get("reason_code", "")),
        "$finding_reason": escape_html(finding.get("reason", "")),
        "$finding_action_recommended": escape_html(finding_action_rec),
        "$finding_evidence_refs": escape_html(finding_evidence_refs),
        "$action_id": escape_html(action.get("action_id", "")),
        "$action_type": escape_html(action.get("action_type", "")),
        "$action_target_ref": escape_html(action.get("target_ref", "")),
        "$action_channel": escape_html(action.get("channel", "")),
        "$action_urgency": escape_html(action.get("urgency", "")),
        "$action_objective": escape_html(action.get("objective", "")),
        "$action_message": escape_html(action.get("message", "")),
        "$action_require_ack": "Yes" if action.get("require_ack") else "No",
        "$result_provider": escape_html(result.get("provider", "")),
        "$result_provider_ref": escape_html(result.get("provider_ref", "")),
        "$result_status": escape_html(result.get("status", "")),
        "$result_acknowledged": escape_html(result_ack),
        "$result_delivery": escape_html(result.get("delivery", "")),
        "$result_reached_ringing": escape_html(result.get("reached_ringing", "")),
        "$result_terminal_cause": escape_html(result.get("terminal_cause", "")),
        "$result_started_at": escape_html(result.get("started_at", "")),
        "$result_completed_at": escape_html(result.get("completed_at", "")),
        "$result_response": escape_html(result.get("response", "")),
        "$sha256_event": escape_html(comp_hashes.get("event", "")),
        "$sha256_lease": escape_html(comp_hashes.get("lease", "")),
        "$sha256_finding": escape_html(comp_hashes.get("finding", "")),
        "$sha256_action": escape_html(comp_hashes.get("action", "")),
        "$sha256_result": escape_html(comp_hashes.get("result", "")),
        "$event_json_pretty": event_json_pretty,
        "$lease_json_pretty": lease_json_pretty,
        "$finding_json_pretty": finding_json_pretty,
        "$action_json_pretty": action_json_pretty,
        "$result_json_pretty": result_json_pretty,
        "$receipt_json_pretty": receipt_json_escaped,
        "$receipt_json": receipt_json_escaped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
    }

    for key, val in replacements.items():
        html = html.replace(key, val)

    return html


def main():
    parser = argparse.ArgumentParser(
        description="Generate OTP Evidence Viewer HTML from receipt JSON"
    )
    parser.add_argument("receipt", help="Path to receipt JSON file")
    parser.add_argument("-o", "--output", help="Output HTML path (default: receipt name + .html)")
    args = parser.parse_args()

    receipt_path = Path(args.receipt)
    if not receipt_path.exists():
        print(f"ERROR: {receipt_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(receipt_path) as f:
        receipt = json.load(f)

    html = build_viewer(receipt)

    output_path = Path(args.output) if args.output else receipt_path.with_suffix(".html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Generated: {output_path}")
    print(f"Execution: {receipt.get('execution_id', 'unknown')}")
    print(f"Verdict:   {receipt.get('verdict', 'unknown')}")
    print(f"Open in browser: file:///{output_path.resolve()}")


if __name__ == "__main__":
    main()
