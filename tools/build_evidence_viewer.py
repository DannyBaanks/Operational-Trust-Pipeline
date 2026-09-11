#!/usr/bin/env python3
"""
OTP Evidence Viewer Generator

Reads OTP evidence receipt JSON files and produces a self-contained
HTML viewer with Windows XP aesthetic. Works offline from file:// protocol.

RULE: UI = projection(receipt). All visible fields rendered from embedded
JSON via JavaScript. Zero static placeholders. The thing you see and the
thing you verify are literally the same artifact.

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

body {
    font-family: Tahoma, "MS Sans Serif", Arial, sans-serif;
    font-size: 11px;
    background: #ECE9D8;
    color: #000;
    min-height: 100vh;
}

/* Title bar */
.title-bar {
    background: linear-gradient(180deg, #0A246A 0%, #3C82D6 8%, #0A246A 100%);
    color: white;
    padding: 4px 8px;
    font-size: 12px;
    font-weight: bold;
    display: flex;
    align-items: center;
    gap: 8px;
}
.title-bar .icon { font-size: 16px; }
.title-bar .title { flex: 1; }
.title-bar .close {
    background: #C0392B;
    color: white;
    border: 1px outset #E74C3C;
    padding: 1px 6px;
    font-size: 11px;
    font-weight: bold;
    cursor: pointer;
}
.title-bar .close:hover { background: #E74C3C; }

/* Window frame */
.window {
    border: 2px outset #D4D0C8;
    margin: 4px;
    background: #ECE9D8;
}

/* Menu bar */
.menu-bar {
    background: #ECE9D8;
    border-bottom: 1px solid #ACA899;
    padding: 2px 4px;
    display: flex;
    gap: 0;
}
.menu-bar .menu-item {
    padding: 2px 8px;
    cursor: pointer;
}
.menu-bar .menu-item:hover {
    background: #316AC5;
    color: white;
}

/* Status bar */
.status-bar {
    background: #ECE9D8;
    border-top: 1px solid #ACA899;
    padding: 2px 8px;
    font-size: 10px;
    color: #444;
    display: flex;
    gap: 16px;
}
.status-bar .section {
    border: 1px inset #D4D0C8;
    padding: 1px 6px;
    flex: 1;
}

/* Tab control */
.tabs {
    display: flex;
    border-bottom: 1px solid #ACA899;
    padding: 0 4px;
    background: #ECE9D8;
}
.tab {
    padding: 4px 12px;
    border: 1px solid #ACA899;
    border-bottom: none;
    background: #D4D0C8;
    cursor: pointer;
    margin-right: 2px;
    position: relative;
    top: 1px;
}
.tab:hover { background: #C8C4BC; }
.tab.active {
    background: #ECE9D8;
    font-weight: bold;
    border-bottom: 1px solid #ECE9D8;
}

/* Tab content */
.tab-content { display: none; padding: 8px; }
.tab-content.active { display: block; }

/* Group boxes */
.group-box {
    border: 1px solid #ACA899;
    margin: 8px 0;
    padding: 8px;
    background: #FFF;
    position: relative;
}
.group-box > .label {
    background: #ECE9D8;
    padding: 0 4px;
    position: absolute;
    top: -8px;
    left: 8px;
    font-weight: bold;
    font-size: 11px;
}

/* Fields */
.field {
    display: flex;
    margin: 3px 0;
    gap: 8px;
    align-items: flex-start;
}
.field-label {
    font-weight: bold;
    min-width: 140px;
    flex-shrink: 0;
}
.field-value {
    flex: 1;
    word-break: break-all;
}
.field-value code {
    font-family: "Lucida Console", "Courier New", monospace;
    background: #F5F5DC;
    padding: 1px 3px;
    border: 1px inset #D4D0C8;
    font-size: 10px;
}

/* Status colors */
.status-FAIL { color: #CC0000; font-weight: bold; }
.status-PASS { color: #006400; font-weight: bold; }
.status-ERROR { color: #CC0000; font-weight: bold; }
.status-WARN { color: #FF8C00; font-weight: bold; }

/* Severity colors */
.severity-CRITICAL { color: #CC0000; font-weight: bold; }
.severity-HIGH { color: #CC0000; font-weight: bold; }
.severity-MEDIUM { color: #FF8C00; }
.severity-LOW { color: #0066CC; }
.severity-INFO { color: #0066CC; }

/* Component cards */
.component {
    border: 1px solid #ACA899;
    margin: 4px 0;
    background: #FFF;
}
.component-header {
    background: #E8E4DC;
    padding: 4px 8px;
    font-weight: bold;
    border-bottom: 1px solid #ACA899;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
}
.component-header:hover { background: #D8D4CC; }
.component-header .arrow { font-size: 8px; }
.component-body {
    padding: 8px;
    display: none;
}
.component-body.open { display: block; }
.component-body pre {
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
}

/* SHA-256 display */
.sha256 {
    font-family: "Lucida Console", "Courier New", monospace;
    font-size: 10px;
    background: #F5F5DC;
    border: 1px inset #D4D0C8;
    padding: 2px 4px;
    word-break: break-all;
}

/* Verification button */
.verify-btn {
    background: #D4D0C8;
    border: 2px outset #D4D0C8;
    padding: 4px 16px;
    font-family: Tahoma, "MS Sans Serif", Arial, sans-serif;
    font-size: 11px;
    cursor: pointer;
}
.verify-btn:hover { background: #C8C4BC; }
.verify-btn:active { border-style: inset; }

/* Verification result */
.verify-result {
    margin: 8px 0;
    padding: 8px;
    border: 2px inset #D4D0C8;
    font-weight: bold;
}
.verify-valid {
    background: #90EE90;
    color: #006400;
}
.verify-invalid {
    background: #FFB3B3;
    color: #8B0000;
}

/* Limitations box */
.limitations {
    background: #FFFACD;
    border: 1px solid #DAA520;
    padding: 8px;
    margin: 8px 0;
    font-size: 10px;
}
.limitations .title {
    font-weight: bold;
    color: #8B4513;
    margin-bottom: 4px;
}

/* Phase badge */
.phase-badge {
    display: inline-block;
    padding: 2px 8px;
    border: 1px solid #ACA899;
    background: #E8E4DC;
    font-size: 10px;
    margin-left: 8px;
}
.phase-badge.RESOLVED { background: #90EE90; color: #006400; }
.phase-badge.OPEN { background: #FFE0B2; color: #E65100; }
.phase-badge.SATISFIED { background: #90EE90; color: #006400; }
.phase-badge.EXPIRED { background: #FFB3B3; color: #8B0000; }

/* XP-style scrollbar */
::-webkit-scrollbar { width: 16px; height: 16px; }
::-webkit-scrollbar-track { background: #ECE9D8; border: 1px inset #D4D0C8; }
::-webkit-scrollbar-thumb {
    background: #D4D0C8;
    border: 2px outset #D4D0C8;
}
::-webkit-scrollbar-thumb:hover { background: #C8C4BC; }
::-webkit-scrollbar-button {
    background: #D4D0C8;
    border: 1px outset #D4D0C8;
    height: 16px;
}
</style>
</head>
<body>

<!-- Title Bar -->
<div class="title-bar">
    <span class="icon">📋</span>
    <span class="title">OTP Evidence Viewer — <span id="v-execution-id"></span></span>
    <span class="close" onclick="window.close()">X</span>
</div>

<div class="window">

<!-- Menu Bar -->
<div class="menu-bar">
    <span class="menu-item" onclick="verifyReceipt()">🔍 Verify</span>
    <span class="menu-item" onclick="downloadEvidence()">💾 Save As...</span>
    <span class="menu-item" onclick="copyHash()">📋 Copy Hash</span>
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
            <span class="field-value"><code id="v-exec-id"></code></span>
        </div>
        <div class="field">
            <span class="field-label">Source Adapter:</span>
            <span class="field-value" id="v-source-adapter"></span>
        </div>
        <div class="field">
            <span class="field-label">Policy Version:</span>
            <span class="field-value" id="v-policy-version"></span>
        </div>
        <div class="field">
            <span class="field-label">Channel Adapter:</span>
            <span class="field-value" id="v-channel"></span>
        </div>
        <div class="field">
            <span class="field-label">Verdict:</span>
            <span class="field-value" id="v-verdict"></span>
        </div>
    </div>

    <div class="group-box">
        <span class="label">Finding</span>
        <div class="field">
            <span class="field-label">Status:</span>
            <span class="field-value" id="v-finding-status"></span>
        </div>
        <div class="field">
            <span class="field-label">Reason Code:</span>
            <span class="field-value"><code id="v-finding-reason-code"></code></span>
        </div>
        <div class="field">
            <span class="field-label">Severity:</span>
            <span class="field-value" id="v-finding-severity"></span>
        </div>
        <div class="field">
            <span class="field-label">Action Recommended:</span>
            <span class="field-value" id="v-finding-action-rec"></span>
        </div>
    </div>

    <div class="group-box">
        <span class="label">Receipt Integrity</span>
        <div class="field">
            <span class="field-label">Receipt SHA-256:</span>
            <span class="field-value"><span class="sha256" id="receipt-hash"></span></span>
        </div>
        <div class="field">
            <span class="field-label">Previous Receipt:</span>
            <span class="field-value"><span class="sha256" id="v-prev-receipt"></span></span>
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
            <span class="field-value"><code id="v-event-id"></code></span>
        </div>
        <div class="field">
            <span class="field-label">Source:</span>
            <span class="field-value" id="v-event-source"></span>
        </div>
        <div class="field">
            <span class="field-label">Event Type:</span>
            <span class="field-value" id="v-event-type"></span>
        </div>
        <div class="field">
            <span class="field-label">Source Ref:</span>
            <span class="field-value"><code id="v-event-source-ref"></code></span>
        </div>
        <div class="field">
            <span class="field-label">Entity Type:</span>
            <span class="field-value" id="v-event-entity-type"></span>
        </div>
        <div class="field">
            <span class="field-label">Entity ID:</span>
            <span class="field-value"><code id="v-event-entity-id"></code></span>
        </div>
        <div class="field">
            <span class="field-label">Observed At:</span>
            <span class="field-value" id="v-event-observed-at"></span>
        </div>
        <div class="field">
            <span class="field-label">Payload SHA-256:</span>
            <span class="field-value"><span class="sha256" id="v-event-payload-sha"></span></span>
        </div>
    </div>

    <div class="group-box">
        <span class="label">Payload</span>
        <pre id="v-event-payload"></pre>
    </div>
</div>

<!-- Tab: Finding -->
<div id="tab-finding" class="tab-content">
    <div class="group-box">
        <span class="label">Finding Details</span>
        <div class="field">
            <span class="field-label">Finding ID:</span>
            <span class="field-value"><code id="v-finding-id"></code></span>
        </div>
        <div class="field">
            <span class="field-label">Rule ID:</span>
            <span class="field-value" id="v-finding-rule-id"></span>
        </div>
        <div class="field">
            <span class="field-label">Status:</span>
            <span class="field-value" id="v-finding-status2"></span>
        </div>
        <div class="field">
            <span class="field-label">Severity:</span>
            <span class="field-value" id="v-finding-severity2"></span>
        </div>
        <div class="field">
            <span class="field-label">Subject:</span>
            <span class="field-value"><code id="v-finding-subject"></code></span>
        </div>
        <div class="field">
            <span class="field-label">Reason Code:</span>
            <span class="field-value"><code id="v-finding-reason-code2"></code></span>
        </div>
        <div class="field">
            <span class="field-label">Reason:</span>
            <span class="field-value" id="v-finding-reason"></span>
        </div>
        <div class="field">
            <span class="field-label">Action Recommended:</span>
            <span class="field-value" id="v-finding-action-rec2"></span>
        </div>
        <div class="field">
            <span class="field-label">Evidence Refs:</span>
            <span class="field-value"><code id="v-finding-evidence-refs"></code></span>
        </div>
    </div>

    <div class="group-box">
        <span class="label">Component SHA-256</span>
        <div class="field">
            <span class="field-label">Finding Hash:</span>
            <span class="field-value"><span class="sha256" id="v-sha-finding"></span></span>
        </div>
    </div>
</div>

<!-- Tab: Action -->
<div id="tab-action" class="tab-content">
    <div class="group-box">
        <span class="label">Action Request</span>
        <div class="field">
            <span class="field-label">Action ID:</span>
            <span class="field-value"><code id="v-action-id"></code></span>
        </div>
        <div class="field">
            <span class="field-label">Type:</span>
            <span class="field-value" id="v-action-type"></span>
        </div>
        <div class="field">
            <span class="field-label">Target:</span>
            <span class="field-value"><code id="v-action-target"></code></span>
        </div>
        <div class="field">
            <span class="field-label">Channel:</span>
            <span class="field-value" id="v-action-channel"></span>
        </div>
        <div class="field">
            <span class="field-label">Urgency:</span>
            <span class="field-value" id="v-action-urgency"></span>
        </div>
        <div class="field">
            <span class="field-label">Objective:</span>
            <span class="field-value" id="v-action-objective"></span>
        </div>
        <div class="field">
            <span class="field-label">Message:</span>
            <span class="field-value" id="v-action-message"></span>
        </div>
        <div class="field">
            <span class="field-label">Require ACK:</span>
            <span class="field-value" id="v-action-require-ack"></span>
        </div>
    </div>

    <div class="group-box">
        <span class="label">Action Result</span>
        <div class="field">
            <span class="field-label">Provider:</span>
            <span class="field-value" id="v-result-provider"></span>
        </div>
        <div class="field">
            <span class="field-label">Provider Ref:</span>
            <span class="field-value"><code id="v-result-provider-ref"></code></span>
        </div>
        <div class="field">
            <span class="field-label">Status:</span>
            <span class="field-value" id="v-result-status"></span>
        </div>
        <div class="field">
            <span class="field-label">Acknowledged:</span>
            <span class="field-value" id="v-result-acknowledged"></span>
        </div>
        <div class="field">
            <span class="field-label">Delivery:</span>
            <span class="field-value" id="v-result-delivery"></span>
        </div>
        <div class="field">
            <span class="field-label">Reached Ringing:</span>
            <span class="field-value" id="v-result-reached-ringing"></span>
        </div>
        <div class="field">
            <span class="field-label">Terminal Cause:</span>
            <span class="field-value" id="v-result-terminal-cause"></span>
        </div>
        <div class="field">
            <span class="field-label">Started At:</span>
            <span class="field-value" id="v-result-started-at"></span>
        </div>
        <div class="field">
            <span class="field-label">Completed At:</span>
            <span class="field-value" id="v-result-completed-at"></span>
        </div>
        <div class="field">
            <span class="field-label">Response:</span>
            <span class="field-value" id="v-result-response"></span>
        </div>
    </div>

    <div class="group-box">
        <span class="label">Component SHA-256</span>
        <div class="field">
            <span class="field-label">Action Hash:</span>
            <span class="field-value"><span class="sha256" id="v-sha-action"></span></span>
        </div>
        <div class="field">
            <span class="field-label">Result Hash:</span>
            <span class="field-value"><span class="sha256" id="v-sha-result"></span></span>
        </div>
    </div>
</div>

<!-- Tab: Components -->
<div id="tab-components" class="tab-content">
    <div class="component">
        <div class="component-header" onclick="toggleComponent('comp-event')">
            <span class="arrow" id="arrow-comp-event">▶</span>
            Event Component
            <span class="sha256" style="margin-left: auto;" id="v-comp-sha-event"></span>
        </div>
        <div class="component-body" id="comp-event">
            <pre id="v-comp-json-event"></pre>
        </div>
    </div>

    <div class="component">
        <div class="component-header" onclick="toggleComponent('comp-lease')">
            <span class="arrow" id="arrow-comp-lease">▶</span>
            Lease Component
            <span class="sha256" style="margin-left: auto;" id="v-comp-sha-lease"></span>
        </div>
        <div class="component-body" id="comp-lease">
            <pre id="v-comp-json-lease"></pre>
        </div>
    </div>

    <div class="component">
        <div class="component-header" onclick="toggleComponent('comp-finding')">
            <span class="arrow" id="arrow-comp-finding">▶</span>
            Finding Component
            <span class="sha256" style="margin-left: auto;" id="v-comp-sha-finding"></span>
        </div>
        <div class="component-body" id="comp-finding">
            <pre id="v-comp-json-finding"></pre>
        </div>
    </div>

    <div class="component">
        <div class="component-header" onclick="toggleComponent('comp-action')">
            <span class="arrow" id="arrow-comp-action">▶</span>
            Action Component
            <span class="sha256" style="margin-left: auto;" id="v-comp-sha-action"></span>
        </div>
        <div class="component-body" id="comp-action">
            <pre id="v-comp-json-action"></pre>
        </div>
    </div>

    <div class="component">
        <div class="component-header" onclick="toggleComponent('comp-result')">
            <span class="arrow" id="arrow-comp-result">▶</span>
            Result Component
            <span class="sha256" style="margin-left: auto;" id="v-comp-sha-result"></span>
        </div>
        <div class="component-body" id="comp-result">
            <pre id="v-comp-json-result"></pre>
        </div>
    </div>
</div>

<!-- Tab: Raw -->
<div id="tab-raw" class="tab-content">
    <div class="group-box">
        <span class="label">Full Evidence Receipt (JSON)</span>
        <pre style="max-height: 500px; overflow-y: auto;" id="v-raw-json"></pre>
    </div>
</div>

<!-- Status Bar -->
<div class="status-bar">
    <span class="section">Schema: <span id="v-schema"></span></span>
    <span class="section">Components: <span id="v-component-count"></span></span>
    <span class="section" id="status-verify">Ready</span>
</div>

</div><!-- /window -->

<!-- Evidence JSON embedded for verification -->
<script id="otp-evidence" type="application/json">$receipt_json</script>

<script>
// ============================================================
// OTP EVIDENCE VIEWER — UI = projection(receipt)
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

// Safe getters
function g(obj, ...keys) {
    let cur = obj;
    for (const k of keys) {
        if (cur == null || typeof cur !== 'object') return undefined;
        cur = cur[k];
    }
    return cur;
}

function fmt(val) {
    if (val === undefined || val === null) return '—';
    if (typeof val === 'boolean') return val ? 'Yes' : 'No';
    return String(val);
}

function fmtClass(val, prefix) {
    const s = String(val || 'NONE').replace(/[^A-Z0-9_]/gi, '-').toUpperCase();
    return prefix + s;
}

// Render all visible fields from the receipt JSON
function renderFields() {
    const r = currentRecord;
    const c = r.components || {};

    // Title bar
    document.getElementById('v-execution-id').textContent = fmt(r.execution_id);

    // Overview
    document.getElementById('v-exec-id').textContent = fmt(r.execution_id);
    document.getElementById('v-source-adapter').textContent = fmt(r.source_adapter);
    document.getElementById('v-policy-version').textContent = fmt(r.policy_version);
    document.getElementById('v-channel').textContent = fmt(r.channel_adapter);

    // Verdict
    const verdict = r.verdict || g(c, 'finding', 'status') || 'UNKNOWN';
    const vEl = document.getElementById('v-verdict');
    vEl.textContent = fmt(verdict);
    vEl.className = 'field-value status-' + String(verdict).replace(/[^A-Z0-9]/gi, '-').toUpperCase();

    // Finding overview
    const f = c.finding || {};
    const fStatus = f.status;
    const fsEl = document.getElementById('v-finding-status');
    fsEl.textContent = fmt(fStatus);
    fsEl.className = 'field-value ' + fmtClass(fStatus, 'status-');

    document.getElementById('v-finding-reason-code').textContent = fmt(f.reason_code);

    const fSev = f.severity;
    const fvEl = document.getElementById('v-finding-severity');
    fvEl.textContent = fmt(fSev);
    fvEl.className = 'field-value ' + fmtClass(fSev, 'severity-');

    document.getElementById('v-finding-action-rec').textContent = fmt(f.action_recommended);

    // Receipt hashes
    document.getElementById('receipt-hash').textContent = fmt(r.receipt_sha256);
    document.getElementById('v-prev-receipt').textContent = fmt(r.previous_receipt_sha256);

    // Event tab
    const ev = c.event || {};
    document.getElementById('v-event-id').textContent = fmt(ev.event_id);
    document.getElementById('v-event-source').textContent = fmt(ev.source);
    document.getElementById('v-event-type').textContent = fmt(ev.source_event_type);
    document.getElementById('v-event-source-ref').textContent = fmt(ev.source_ref);
    document.getElementById('v-event-entity-type').textContent = fmt(ev.entity_type);
    document.getElementById('v-event-entity-id').textContent = fmt(ev.entity_id);
    document.getElementById('v-event-observed-at').textContent = fmt(ev.observed_at);
    document.getElementById('v-event-payload-sha').textContent = fmt(ev.payload_sha256);

    const payload = ev.payload;
    document.getElementById('v-event-payload').textContent =
        payload ? JSON.stringify(payload, null, 2) : '—';

    // Finding tab (detail)
    document.getElementById('v-finding-id').textContent = fmt(f.finding_id);
    document.getElementById('v-finding-rule-id').textContent = fmt(f.rule_id);

    const fs2El = document.getElementById('v-finding-status2');
    fs2El.textContent = fmt(fStatus);
    fs2El.className = 'field-value ' + fmtClass(fStatus, 'status-');

    const fs2vEl = document.getElementById('v-finding-severity2');
    fs2vEl.textContent = fmt(fSev);
    fs2vEl.className = 'field-value ' + fmtClass(fSev, 'severity-');

    document.getElementById('v-finding-subject').textContent = fmt(f.subject_ref);
    document.getElementById('v-finding-reason-code2').textContent = fmt(f.reason_code);
    document.getElementById('v-finding-reason').textContent = fmt(f.reason);
    document.getElementById('v-finding-action-rec2').textContent = fmt(f.action_recommended);
    document.getElementById('v-finding-evidence-refs').textContent =
        fmt(f.evidence_refs);

    // Action tab
    const act = c.action || {};
    document.getElementById('v-action-id').textContent = fmt(act.action_id);
    document.getElementById('v-action-type').textContent = fmt(act.action_type);
    document.getElementById('v-action-target').textContent = fmt(act.target_ref);
    document.getElementById('v-action-channel').textContent = fmt(act.channel);
    document.getElementById('v-action-urgency').textContent = fmt(act.urgency);
    document.getElementById('v-action-objective').textContent = fmt(act.objective);
    document.getElementById('v-action-message').textContent = fmt(act.message);
    document.getElementById('v-action-require-ack').textContent = fmt(act.require_ack);

    // Result tab
    const res = c.result || {};
    document.getElementById('v-result-provider').textContent = fmt(res.provider);
    document.getElementById('v-result-provider-ref').textContent = fmt(res.provider_ref);
    document.getElementById('v-result-status').textContent = fmt(res.status);
    document.getElementById('v-result-acknowledged').textContent = fmt(res.acknowledged);
    document.getElementById('v-result-delivery').textContent = fmt(res.delivery);
    document.getElementById('v-result-reached-ringing').textContent = fmt(res.reached_ringing);
    document.getElementById('v-result-terminal-cause').textContent = fmt(res.terminal_cause);
    document.getElementById('v-result-started-at').textContent = fmt(res.started_at);
    document.getElementById('v-result-completed-at').textContent = fmt(res.completed_at);
    document.getElementById('v-result-response').textContent = fmt(res.response);

    // Component hashes
    const ch = r.component_hashes || {};
    document.getElementById('v-sha-finding').textContent = fmt(ch.finding);
    document.getElementById('v-sha-action').textContent = fmt(ch.action);
    document.getElementById('v-sha-result').textContent = fmt(ch.result);

    // Components tab — raw JSON per component
    const compMap = [
        ['event', 'event'],
        ['lease', 'lease'],
        ['finding', 'finding'],
        ['action', 'action'],
        ['result', 'result'],
    ];
    compMap.forEach(([key, jsonKey]) => {
        const el = document.getElementById('v-comp-json-' + key);
        const sha = document.getElementById('v-comp-sha-' + key);
        const data = c[jsonKey];
        const hash = ch[jsonKey];
        el.textContent = data ? JSON.stringify(data, null, 2) : '—';
        sha.textContent = fmt(hash);
    });

    // Raw JSON tab
    document.getElementById('v-raw-json').textContent = JSON.stringify(r, null, 2);

    // Status bar
    document.getElementById('v-schema').textContent = fmt(r.schema_version);
    const compCount = Object.keys(ch).length;
    document.getElementById('v-component-count').textContent = compCount || '—';
}

// Tab switching
function switchTab(name) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    document.querySelectorAll('.tab').forEach(el => {
        if (el.textContent.toLowerCase() === name) el.classList.add('active');
    });
}

// Component toggle
function toggleComponent(id) {
    const body = document.getElementById(id);
    const arrow = document.getElementById('arrow-' + id);
    body.classList.toggle('open');
    arrow.textContent = body.classList.contains('open') ? '▼' : '▶';
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

        // Compute component hashes from components object
        const comps = currentRecord.components || {};
        const ch = currentRecord.component_hashes || {};
        const compResults = [];
        for (const [key, data] of Object.entries(comps)) {
            if (data && typeof data === 'object') {
                const hash = await sha256(data);
                const expected = ch[key];
                compResults.push({
                    name: key,
                    hash: hash,
                    expected: expected,
                    match: expected ? hash === expected : null,
                });
            }
        }

        // Also verify ledger if present
        let ledgerValid = null;
        if (currentRecord.ledger && currentRecord.ledger.length > 0) {
            let chainValid = true;
            for (let i = 1; i < currentRecord.ledger.length; i++) {
                if (currentRecord.ledger[i].previous_receipt_sha256 !==
                    currentRecord.ledger[i-1].receipt_sha256) {
                    chainValid = false;
                    break;
                }
            }
            ledgerValid = chainValid;
        }

        let html = '<div style="margin-bottom: 8px;">';
        html += '<strong>Receipt hash: </strong>';
        if (valid) {
            html += '<span style="color: #006400;">VALID</span>';
            html += ' — ' + computed.substring(0, 32) + '...';
        } else {
            html += '<span style="color: #8B0000;">INVALID</span>';
            html += '<br>Computed: ' + computed;
            html += '<br>Expected: ' + currentRecord.receipt_sha256;
        }
        html += '</div>';

        html += '<div style="margin-bottom: 8px;"><strong>Components:</strong></div>';
        html += '<table style="border-collapse: collapse; width: 100%;">';
        compResults.forEach(r => {
            const color = r.match === true ? '#006400' :
                         r.match === false ? '#8B0000' : '#666';
            const label = r.match === true ? 'MATCH' :
                         r.match === false ? 'MISMATCH' : 'NO EXPECTED';
            html += '<tr style="border-bottom: 1px solid #DDD;">';
            html += '<td style="padding: 2px 8px;">' + r.name + '</td>';
            html += '<td style="padding: 2px 8px; font-family: monospace; font-size: 9px;">' +
                    r.hash.substring(0, 32) + '...</td>';
            html += '<td style="padding: 2px 8px; color: ' + color + '; font-weight: bold;">' +
                    label + '</td>';
            html += '</tr>';
        });
        html += '</table>';

        if (ledgerValid !== null) {
            html += '<div style="margin-top: 8px;">';
            html += '<strong>Ledger chain: </strong>';
            html += ledgerValid ?
                '<span style="color: #006400;">VALID</span> — all links intact' :
                '<span style="color: #8B0000;">BROKEN</span> — chain discontinuity detected';
            html += '</div>';
        }

        resultEl.innerHTML = html;
        resultEl.className = 'verify-result ' + (valid ? 'verify-valid' : 'verify-invalid');
        statusEl.textContent = valid ? 'VALID — All hashes match' : 'INVALID — Hash mismatch';

    } catch (err) {
        resultEl.innerHTML = '<span style="color: #8B0000;">ERROR: ' + err.message + '</span>';
        resultEl.className = 'verify-result verify-invalid';
        statusEl.textContent = 'Error: ' + err.message;
    }
}

// Download evidence as JSON
function downloadEvidence() {
    const blob = new Blob([JSON.stringify(currentRecord, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (currentRecord.execution_id || 'evidence') + '.json';
    a.click();
    URL.revokeObjectURL(url);
}

// Copy receipt hash to clipboard
async function copyHash() {
    if (currentRecord.receipt_sha256) {
        await navigator.clipboard.writeText(currentRecord.receipt_sha256);
        const el = document.getElementById('status-verify');
        el.textContent = 'Hash copied!';
        setTimeout(() => { el.textContent = 'Ready'; }, 2000);
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'v') { e.preventDefault(); verifyReceipt(); }
    if (e.ctrlKey && e.key === 's') { e.preventDefault(); downloadEvidence(); }
    if (e.ctrlKey && e.key === 'c' && !window.getSelection().toString()) {
        e.preventDefault(); copyHash();
    }
});

// Initial render — UI = projection(receipt)
renderFields();
</script>
</body>
</html>"""


def generate_viewer(receipt_path: Path, output_path: Path) -> dict:
    """Generate HTML viewer from receipt JSON."""
    with open(receipt_path, 'r', encoding='utf-8') as f:
        receipt = json.load(f)

    receipt_json = json.dumps(receipt, indent=2, ensure_ascii=False)

    html = HTML_TEMPLATE.replace('$receipt_json', receipt_json)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return {
        'execution_id': receipt.get('execution_id', 'unknown'),
        'verdict': receipt.get('verdict', 'UNKNOWN'),
        'output': str(output_path),
    }


def main():
    parser = argparse.ArgumentParser(
        description='Generate OTP Evidence Viewer HTML from receipt JSON'
    )
    parser.add_argument('receipt', help='Path to evidence receipt JSON')
    parser.add_argument('-o', '--output', default=None,
                        help='Output HTML path (default: same dir as receipt)')
    args = parser.parse_args()

    receipt_path = Path(args.receipt)
    if not receipt_path.exists():
        print(f'ERROR: Receipt not found: {receipt_path}', file=sys.stderr)
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = receipt_path.with_name('viewer.html')

    result = generate_viewer(receipt_path, output_path)

    print(f'Generated: {output_path}')
    print(f'Execution: {result["execution_id"]}')
    print(f'Verdict:   {result["verdict"]}')
    print(f'Open in browser: file:///{output_path.resolve().as_posix()}')


if __name__ == '__main__':
    main()
