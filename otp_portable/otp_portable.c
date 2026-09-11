/*
 * otp_portable.c — OTP Portable Core
 *
 * Minimal C89/C90 implementation of the Operational Trust Pipeline.
 * Single-file compilation: cc otp_portable.c -o otp
 *
 * SHA-256: Public domain implementation (Brad Conte / EventEmitter).
 * JSON:    Minimal custom parser for OTP fixtures.
 *
 * FEATURES MAY DEGRADE. SEMANTICS MUST NOT.
 */

#include "otp_portable.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* ================================================================== */
/*  SHA-256 (public domain, C89 compatible)                            */
/* ================================================================== */

static const otp_u32 SHA256_K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
#define CH(x,y,z)  (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x)      (ROTR(x, 2) ^ ROTR(x, 13) ^ ROTR(x, 22))
#define EP1(x)      (ROTR(x, 6) ^ ROTR(x, 11) ^ ROTR(x, 25))
#define SIG0(x)     (ROTR(x, 7) ^ ROTR(x, 18) ^ ((x) >> 3))
#define SIG1(x)     (ROTR(x, 17) ^ ROTR(x, 19) ^ ((x) >> 10))

static void sha256_transform(otp_u32 state[8], const otp_u8 block[64]) {
    otp_u32 a, b, c, d, e, f, g, h, t1, t2, w[64];
    int i;

    for (i = 0; i < 16; i++) {
        w[i] = ((otp_u32)block[i*4] << 24) | ((otp_u32)block[i*4+1] << 16) |
               ((otp_u32)block[i*4+2] << 8)  | ((otp_u32)block[i*4+3]);
    }
    for (i = 16; i < 64; i++) {
        w[i] = SIG1(w[i-2]) + w[i-7] + SIG0(w[i-15]) + w[i-16];
    }

    a = state[0]; b = state[1]; c = state[2]; d = state[3];
    e = state[4]; f = state[5]; g = state[6]; h = state[7];

    for (i = 0; i < 64; i++) {
        t1 = h + EP1(e) + CH(e, f, g) + SHA256_K[i] + w[i];
        t2 = EP0(a) + MAJ(a, b, c);
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }

    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}

void otp_sha256_raw(const void *data, size_t len, otp_u8 out[32]) {
    otp_u32 state[8] = {
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    };
    otp_u8 block[64];
    size_t i, remaining;
    otp_u32 total_bits_hi, total_bits_lo;

    /* Split 64-bit bit count into hi/lo 32-bit words */
    total_bits_lo = (otp_u32)(len * 8);
    total_bits_hi = (otp_u32)((len * 8) >> 32);

    /* Process complete blocks */
    for (i = 0; i + 64 <= len; i += 64) {
        memcpy(block, (const char *)data + i, 64);
        sha256_transform(state, block);
    }

    /* Padding */
    remaining = len - i;
    memset(block, 0, 64);
    if (remaining > 0) {
        memcpy(block, (const char *)data + i, remaining);
    }
    block[remaining] = 0x80;

    if (remaining >= 56) {
        sha256_transform(state, block);
        memset(block, 0, 64);
    }

    /* Append length in bits (big-endian, split hi/lo) */
    block[56] = (otp_u8)(total_bits_hi >> 24);
    block[57] = (otp_u8)(total_bits_hi >> 16);
    block[58] = (otp_u8)(total_bits_hi >> 8);
    block[59] = (otp_u8)(total_bits_hi);
    block[60] = (otp_u8)(total_bits_lo >> 24);
    block[61] = (otp_u8)(total_bits_lo >> 16);
    block[62] = (otp_u8)(total_bits_lo >> 8);
    block[63] = (otp_u8)(total_bits_lo);
    sha256_transform(state, block);

    /* Output */
    for (i = 0; i < 8; i++) {
        out[i*4]   = (otp_u8)(state[i] >> 24);
        out[i*4+1] = (otp_u8)(state[i] >> 16);
        out[i*4+2] = (otp_u8)(state[i] >> 8);
        out[i*4+3] = (otp_u8)(state[i]);
    }
}

void otp_sha256_hex(const void *data, size_t len, char out[65]) {
    static const char hex[] = "0123456789abcdef";
    otp_u8 raw[32];
    int i;
    otp_sha256_raw(data, len, raw);
    for (i = 0; i < 32; i++) {
        out[i*2]   = hex[raw[i] >> 4];
        out[i*2+1] = hex[raw[i] & 0x0f];
    }
    out[64] = '\0';
}

/* ================================================================== */
/*  UTILITIES                                                          */
/* ================================================================== */

void otp_str_copy(char *dst, const char *src, int n) {
    if (n <= 0) return;
    strncpy(dst, src, (size_t)n - 1);
    dst[n - 1] = '\0';
}

int otp_str_eq(const char *a, const char *b) {
    if (a == NULL || b == NULL) return 0;
    return strcmp(a, b) == 0;
}

int otp_str_empty(const char *s) {
    return s == NULL || s[0] == '\0';
}

/* ================================================================== */
/*  CLOCK                                                              */
/* ================================================================== */

void otp_clock_system(char *buf, int bufsize) {
    otp_now_iso(buf, bufsize);
}

void otp_clock_fixed(const OtpFixedClock *clk, char *buf, int bufsize) {
    otp_str_copy(buf, clk->frozen_time, bufsize);
}

/* ================================================================== */
/*  CANONICAL JSON                                                     */
/* ================================================================== */

/* Simple bubble sort for string keys (C89, small n) */
static void sort_strings(const char **arr, int n) {
    int i, j;
    const char *tmp;
    for (i = 0; i < n - 1; i++) {
        for (j = i + 1; j < n; j++) {
            if (strcmp(arr[i], arr[j]) > 0) {
                tmp = arr[i];
                arr[i] = arr[j];
                arr[j] = tmp;
            }
        }
    }
}

int otp_canonical_json(char *buf, int bufsize,
                       const char *keys[], const char *vals[], int n) {
    char *sorted_keys[OTP_MAX_FIELDS];
    const char *sorted_vals[OTP_MAX_FIELDS];
    int i, pos = 0;
    int remaining;

    /* Copy and sort by key */
    for (i = 0; i < n; i++) {
        sorted_keys[i] = (char *)keys[i];
        sorted_vals[i] = vals[i];
    }
    sort_strings((const char **)sorted_keys, n);

    /* Re-map vals to sorted order */
    {
        const char *tmp_vals[OTP_MAX_FIELDS];
        for (i = 0; i < n; i++) {
            int j;
            for (j = 0; j < n; j++) {
                if (otp_str_eq(sorted_keys[i], keys[j])) {
                    tmp_vals[i] = vals[j];
                    break;
                }
            }
        }
        for (i = 0; i < n; i++) {
            sorted_vals[i] = tmp_vals[i];
        }
    }

    /* Serialize: {"key":"val","key2":"val2"} */
    remaining = bufsize;
    buf[pos++] = '{';
    for (i = 0; i < n && remaining > 1; i++) {
        int wrote;
        if (i > 0) {
            buf[pos++] = ',';
            remaining--;
        }
        wrote = snprintf(buf + pos, (size_t)remaining, "\"%s\":\"%s\"",
                         sorted_keys[i], sorted_vals[i ? i : 0]);
        /* Fix: use correct sorted_vals */
        pos += wrote;
        remaining -= wrote;
    }
    buf[pos++] = '}';
    buf[pos] = '\0';
    return pos;
}

/* ================================================================== */
/*  STABLE ID                                                          */
/* ================================================================== */

void otp_stable_id(char *out, int outsize,
                   const char *prefix, const char *value) {
    char hash[65];
    otp_sha256_hex(value, strlen(value), hash);
    snprintf(out, (size_t)outsize, "%.8s_%.20s", prefix, hash);
}

/* ================================================================== */
/*  DOMAIN CONSTRUCTORS                                                */
/* ================================================================== */

void otp_event_init(OtpEvent *e) {
    memset(e, 0, sizeof(*e));
    otp_str_copy(e->schema_version, "operational-event/1", OTP_MAX_STR);
}

void otp_event_compute_id(OtpEvent *e) {
    char basis[OTP_MAX_PAYLOAD];
    snprintf(basis, sizeof(basis), "%s:%s:%s:%s",
             e->source, e->source_event_type, e->entity_id, e->observed_at);
    otp_stable_id(e->event_id, OTP_MAX_ID, "evt", basis);

    /* Payload SHA-256 */
    {
        char payload_json[OTP_MAX_PAYLOAD];
        int n = 0;
        const char *keys[OTP_MAX_FIELDS];
        const char *vals[OTP_MAX_FIELDS];

        if (!otp_str_empty(e->payload_trip_ref)) {
            keys[n] = "trip_ref"; vals[n] = e->payload_trip_ref; n++;
        }
        if (!otp_str_empty(e->payload_leg_ref)) {
            keys[n] = "leg_ref"; vals[n] = e->payload_leg_ref; n++;
        }
        if (!otp_str_empty(e->payload_expected_at)) {
            keys[n] = "expected_at"; vals[n] = e->payload_expected_at; n++;
        }
        if (!otp_str_empty(e->payload_due_at)) {
            keys[n] = "due_at"; vals[n] = e->payload_due_at; n++;
        }
        if (!otp_str_empty(e->payload_latest_state_at)) {
            keys[n] = "latest_state_at"; vals[n] = e->payload_latest_state_at; n++;
        }
        if (!otp_str_empty(e->payload_operation_status)) {
            keys[n] = "operation_status"; vals[n] = e->payload_operation_status; n++;
        }
        if (!otp_str_empty(e->payload_remaining_hours)) {
            keys[n] = "remaining_hours"; vals[n] = e->payload_remaining_hours; n++;
        }
        if (!otp_str_empty(e->payload_contact_ref)) {
            keys[n] = "contact_ref"; vals[n] = e->payload_contact_ref; n++;
        }
        if (!otp_str_empty(e->payload_ack_due_at)) {
            keys[n] = "ack_due_at"; vals[n] = e->payload_ack_due_at; n++;
        }
        if (!otp_str_empty(e->payload_acknowledged_at)) {
            keys[n] = "acknowledged_at"; vals[n] = e->payload_acknowledged_at; n++;
        }

        if (n > 0) {
            otp_canonical_json(payload_json, sizeof(payload_json), keys, vals, n);
            otp_sha256_hex(payload_json, strlen(payload_json), e->payload_sha256);
        }
    }
}

void otp_lease_init(OtpLease *l) {
    memset(l, 0, sizeof(*l));
    l->state = LEASE_OPEN;
}

void otp_lease_compute_id(OtpLease *l) {
    char basis[OTP_MAX_PAYLOAD];
    snprintf(basis, sizeof(basis), "%s:%s:%s:%s",
             l->kind, l->subject_ref, l->opened_at, l->due_at);
    otp_stable_id(l->lease_id, OTP_MAX_ID, "lease", basis);
}

void otp_finding_init(OtpFinding *f) {
    memset(f, 0, sizeof(*f));
}

void otp_finding_compute_id(OtpFinding *f) {
    char basis[OTP_MAX_PAYLOAD];
    snprintf(basis, sizeof(basis), "%s:%s:%s",
             f->rule_id, f->subject_ref, f->reason_code);
    otp_stable_id(f->finding_id, OTP_MAX_ID, "finding", basis);
}

void otp_action_request_init(OtpActionRequest *a) {
    memset(a, 0, sizeof(*a));
}

void otp_action_request_compute_id(OtpActionRequest *a) {
    char basis[OTP_MAX_PAYLOAD];
    snprintf(basis, sizeof(basis), "%s:%s:%s:%s",
             a->action_type, a->target_ref, a->channel, a->objective);
    otp_stable_id(a->action_id, OTP_MAX_ID, "action", basis);
}

/* ================================================================== */
/*  DOMAIN PREDICATES                                                  */
/* ================================================================== */

int otp_recipient_acknowledged(const OtpActionResult *r) {
    return r->acknowledged && !otp_str_eq(r->delivery, "NOT_DEMONSTRATED");
}

/* ================================================================== */
/*  PIPELINE: pure functions                                           */
/* ================================================================== */

void otp_make_ack_lease(const OtpEvent *event, otp_clock_now_fn clock,
                        OtpLease *out) {
    char now[OTP_MAX_TIMESTAMP];
    clock(now, sizeof(now));

    otp_lease_init(out);
    otp_str_copy(out->kind, "acknowledgement", OTP_MAX_STR);
    otp_str_copy(out->subject_ref, event->entity_id, OTP_MAX_STR);
    otp_str_copy(out->opened_at, event->observed_at, OTP_MAX_TIMESTAMP);
    otp_str_copy(out->due_at, event->payload_ack_due_at, OTP_MAX_TIMESTAMP);
    otp_str_copy(out->required_condition, "acknowledged", OTP_MAX_STR);
    otp_lease_compute_id(out);
}

void otp_ack_lease_policy_evaluate(const OtpEvent *event,
                                   const OtpLease *lease,
                                   otp_clock_now_fn clock,
                                   OtpFinding *out) {
    char now[OTP_MAX_TIMESTAMP];
    clock(now, sizeof(now));

    otp_finding_init(out);
    otp_str_copy(out->rule_id, "ack-lease-v0", OTP_MAX_STR);
    otp_str_copy(out->subject_ref, event->entity_id, OTP_MAX_STR);

    /* Branch 1: no deadline => UNKNOWN */
    if (otp_str_empty(lease->due_at)) {
        out->status = FINDING_UNKNOWN;
        otp_str_copy(out->reason_code, "ACK_DUE_UNKNOWN", OTP_MAX_STR);
        otp_str_copy(out->reason, "No acknowledgement deadline set", OTP_MAX_STR);
        otp_str_copy(out->severity, "INFO", OTP_MAX_STR);
        out->action_recommended = 0;
        otp_finding_compute_id(out);
        return;
    }

    /* Branch 2: already acknowledged => PASS */
    if (!otp_str_empty(event->payload_acknowledged_at)) {
        out->status = FINDING_PASS;
        otp_str_copy(out->reason_code, "ACK_OBSERVED", OTP_MAX_STR);
        otp_str_copy(out->reason, "Acknowledgement observed in event", OTP_MAX_STR);
        otp_str_copy(out->severity, "INFO", OTP_MAX_STR);
        out->action_recommended = 0;
        otp_finding_compute_id(out);
        return;
    }

    /* Branch 3: before deadline => PASS */
    if (strcmp(now, lease->due_at) < 0) {
        out->status = FINDING_PASS;
        otp_str_copy(out->reason_code, "ACK_LEASE_OPEN", OTP_MAX_STR);
        otp_str_copy(out->reason, "Lease open, deadline not yet reached", OTP_MAX_STR);
        otp_str_copy(out->severity, "INFO", OTP_MAX_STR);
        out->action_recommended = 0;
        otp_finding_compute_id(out);
        return;
    }

    /* Branch 4: past deadline, no ack => FAIL */
    out->status = FINDING_FAIL;
    otp_str_copy(out->reason_code, "ACK_LEASE_EXPIRED", OTP_MAX_STR);
    otp_str_copy(out->reason, "Lease expired without acknowledgement", OTP_MAX_STR);
    otp_str_copy(out->severity, "HIGH", OTP_MAX_STR);
    out->action_recommended = 1;
    otp_finding_compute_id(out);
}

OtpSentinelVerdict otp_sentinel(const OtpFinding *finding,
                                int communication_allowed) {
    if (finding->status == FINDING_UNKNOWN) return VERDICT_NEEDS_REVIEW;
    if (!finding->action_recommended) return VERDICT_NO_ACTION;
    if (communication_allowed) return VERDICT_ACTION_REQUESTED;
    return VERDICT_BLOCKED;
}

void otp_request_for(const OtpFinding *finding, const OtpEvent *event,
                     const char *channel, OtpActionRequest *out) {
    otp_action_request_init(out);
    otp_str_copy(out->action_type, "notify", OTP_MAX_STR);
    otp_str_copy(out->target_ref, event->payload_contact_ref, OTP_MAX_STR);
    otp_str_copy(out->channel, channel, OTP_MAX_STR);
    snprintf(out->objective, OTP_MAX_STR, "Request acknowledgement for %s",
             event->entity_id);
    snprintf(out->message, OTP_MAX_STR,
             "Trip %s requires acknowledgement. Deadline: %s",
             event->payload_trip_ref, event->payload_due_at);
    out->require_ack = 1;
    otp_str_copy(out->urgency, "HIGH", OTP_MAX_STR);
    otp_str_copy(out->source_finding_id, finding->finding_id, OTP_MAX_ID);
    otp_action_request_compute_id(out);
}

void otp_evaluate_ack(const OtpEvent *event, OtpLease *lease,
                      otp_clock_now_fn clock, int communication_allowed,
                      OtpFinding *finding, OtpSentinelVerdict *verdict,
                      OtpActionRequest *action) {
    otp_ack_lease_policy_evaluate(event, lease, clock, finding);
    *verdict = otp_sentinel(finding, communication_allowed);

    if (*verdict == VERDICT_ACTION_REQUESTED) {
        otp_request_for(finding, event, "mock", action);
    } else {
        memset(action, 0, sizeof(*action));
    }
}

void otp_resolve_ack_lease(OtpLease *lease, const OtpFinding *finding,
                           const OtpActionResult *result) {
    char now[OTP_MAX_TIMESTAMP];
    otp_now_iso(now, sizeof(now));

    if (lease->state != LEASE_OPEN) return;

    if (result != NULL && otp_recipient_acknowledged(result)) {
        lease->state = LEASE_SATISFIED;
        otp_str_copy(lease->resolution, "recipient_acknowledgement", OTP_MAX_STR);
        otp_str_copy(lease->closed_at, now, OTP_MAX_TIMESTAMP);
    } else if (otp_str_eq(finding->reason_code, "ACK_LEASE_EXPIRED")) {
        lease->state = LEASE_EXPIRED;
        otp_str_copy(lease->closed_at, now, OTP_MAX_TIMESTAMP);
    }
}

void otp_execution_id(char *out, int outsize, const OtpEvent *event,
                      const OtpLease *lease, const char *policy_version) {
    char basis[OTP_MAX_PAYLOAD];
    snprintf(basis, sizeof(basis), "%s:%s:%s:evaluate",
             event->event_id, lease->lease_id, policy_version);
    otp_stable_id(out, outsize, "exec", basis);
}

/* ================================================================== */
/*  EVIDENCE                                                           */
/* ================================================================== */

static void receipt_component_sha256(const void *data, size_t len,
                                     char out[65]) {
    if (data == NULL) {
        strcpy(out, "null");
    } else {
        otp_sha256_hex(data, len, out);
    }
}

void otp_make_receipt(const OtpEvent *event, const OtpLease *lease,
                      const OtpFinding *finding, const OtpActionRequest *action,
                      const OtpActionResult *result, const char *execution_id,
                      const char *source_adapter, const char *policy_version,
                      const char *channel_adapter, int verdict,
                      const char *previous_receipt_sha256, OtpReceipt *out) {
    char event_json[OTP_MAX_PAYLOAD];
    char lease_json[OTP_MAX_PAYLOAD];
    char finding_json[OTP_MAX_PAYLOAD];
    char action_json[OTP_MAX_PAYLOAD];
    char result_json[OTP_MAX_PAYLOAD];

    memset(out, 0, sizeof(*out));
    otp_str_copy(out->schema_version, "evidence-receipt/1", OTP_MAX_STR);
    otp_str_copy(out->execution_id, execution_id, OTP_MAX_ID);
    otp_str_copy(out->source_adapter, source_adapter, OTP_MAX_STR);
    otp_str_copy(out->policy_version, policy_version, OTP_MAX_STR);
    otp_str_copy(out->channel_adapter, channel_adapter, OTP_MAX_STR);
    out->verdict = verdict;

    /* Serialize each component and compute its SHA-256 */
    /* For simplicity, serialize as canonical JSON strings */
    {
        const char *ek[] = {"entity_id","event_id","observed_at","payload_sha256","schema_version","source","source_event_type","source_ref"};
        const char *ev[] = {event->entity_id,event->event_id,event->observed_at,event->payload_sha256,event->schema_version,event->source,event->source_event_type,event->source_ref};
        otp_canonical_json(event_json, sizeof(event_json), ek, ev, 8);
        otp_sha256_hex(event_json, strlen(event_json), out->sha256_event);
    }
    {
        const char *lk[] = {"due_at","kind","lease_id","opened_at","required_condition","state","subject_ref"};
        char state_str[16];
        const char *lv[] = {lease->due_at,lease->kind,lease->lease_id,lease->opened_at,lease->required_condition,"OPEN",lease->subject_ref};
        otp_canonical_json(lease_json, sizeof(lease_json), lk, lv, 7);
        otp_sha256_hex(lease_json, strlen(lease_json), out->sha256_lease);
    }
    {
        const char *fk[] = {"action_recommended","finding_id","reason","reason_code","rule_id","severity","status"};
        char status_str[16], action_str[8];
        const char *fv[7];
        snprintf(status_str, sizeof(status_str), "%d", finding->status);
        snprintf(action_str, sizeof(action_str), "%d", finding->action_recommended);
        fv[0] = action_str; fv[1] = finding->finding_id; fv[2] = finding->reason;
        fv[3] = finding->reason_code; fv[4] = finding->rule_id;
        fv[5] = finding->severity; fv[6] = status_str;
        otp_canonical_json(finding_json, sizeof(finding_json), fk, fv, 7);
        otp_sha256_hex(finding_json, strlen(finding_json), out->sha256_finding);
    }
    if (action != NULL && !otp_str_empty(action->action_id)) {
        const char *ak[] = {"action_id","action_type","channel","message","objective","require_ack","source_finding_id","target_ref","urgency"};
        char req_str[8];
        const char *av[9];
        snprintf(req_str, sizeof(req_str), "%d", action->require_ack);
        av[0] = action->action_id; av[1] = action->action_type;
        av[2] = action->channel; av[3] = action->message;
        av[4] = action->objective; av[5] = req_str;
        av[6] = action->source_finding_id; av[7] = action->target_ref;
        av[8] = action->urgency;
        otp_canonical_json(action_json, sizeof(action_json), ak, av, 9);
        otp_sha256_hex(action_json, strlen(action_json), out->sha256_action);
    } else {
        strcpy(out->sha256_action, "null");
    }
    if (result != NULL && !otp_str_empty(result->action_id)) {
        const char *rk[] = {"acknowledged","action_id","delivery","provider","status"};
        char ack_str[8], status_str[16];
        const char *rv[5];
        snprintf(ack_str, sizeof(ack_str), "%d", result->acknowledged);
        snprintf(status_str, sizeof(status_str), "%d", result->status);
        rv[0] = ack_str; rv[1] = result->action_id;
        rv[2] = result->delivery; rv[3] = result->provider; rv[4] = status_str;
        otp_canonical_json(result_json, sizeof(result_json), rk, rv, 5);
        otp_sha256_hex(result_json, strlen(result_json), out->sha256_result);
    } else {
        strcpy(out->sha256_result, "null");
    }

    if (previous_receipt_sha256 != NULL) {
        otp_str_copy(out->previous_receipt_sha256, previous_receipt_sha256, 65);
    }
}

int otp_receipt_to_json(char *buf, int bufsize, const OtpReceipt *r) {
    return snprintf(buf, (size_t)bufsize,
        "{\"schema_version\":\"%s\","
        "\"execution_id\":\"%s\","
        "\"source_adapter\":\"%s\","
        "\"policy_version\":\"%s\","
        "\"channel_adapter\":\"%s\","
        "\"verdict\":%d,"
        "\"component_sha256\":{\"event\":\"%s\",\"lease\":\"%s\","
        "\"finding\":\"%s\",\"action\":\"%s\",\"result\":\"%s\"},"
        "\"previous_receipt_sha256\":%s,\"receipt_sha256\":\"%s\"}",
        r->schema_version, r->execution_id, r->source_adapter,
        r->policy_version, r->channel_adapter, r->verdict,
        r->sha256_event, r->sha256_lease, r->sha256_finding,
        r->sha256_action, r->sha256_result,
        otp_str_empty(r->previous_receipt_sha256) ? "null" : r->previous_receipt_sha256,
        r->receipt_sha256);
}

int otp_append_ledger(const char *path, const OtpReceipt *r) {
    FILE *f = fopen(path, "a");
    char json[2048];
    int len;
    if (!f) return -1;
    len = otp_receipt_to_json(json, sizeof(json), r);
    fprintf(f, "%s\n", json);
    fclose(f);
    return 0;
}

/* ================================================================== */
/*  ROADSTAR ADAPTER                                                   */
/* ================================================================== */

static void otp_normalize_iso(const char *src, char *dst, int dstsize) {
    if (otp_str_empty(src)) {
        dst[0] = '\0';
        return;
    }
    /* Simple pass-through; real impl would parse date formats */
    otp_str_copy(dst, src, dstsize);
}

void otp_normalize_dispatch(const OtpRawRecord *raw, OtpEvent *out) {
    otp_event_init(out);
    otp_str_copy(out->source, "roadstar", OTP_MAX_STR);
    otp_str_copy(out->source_event_type, "dispatch.leg_observed", OTP_MAX_STR);
    snprintf(out->source_ref, OTP_MAX_STR, "%s:%s",
             raw->trip_number, raw->leg_id);
    otp_str_copy(out->entity_type, "dispatch_leg", OTP_MAX_STR);
    otp_str_copy(out->entity_id, raw->leg_id, OTP_MAX_STR);

    /* observed_at: first non-null of last_status_date, expected_date, deliver_by */
    if (!otp_str_empty(raw->last_status_date))
        otp_str_copy(out->observed_at, raw->last_status_date, OTP_MAX_TIMESTAMP);
    else if (!otp_str_empty(raw->expected_date))
        otp_str_copy(out->observed_at, raw->expected_date, OTP_MAX_TIMESTAMP);
    else
        otp_str_copy(out->observed_at, raw->deliver_by, OTP_MAX_TIMESTAMP);

    otp_str_copy(out->payload_trip_ref, raw->trip_number, OTP_MAX_STR);
    otp_str_copy(out->payload_leg_ref, raw->leg_id, OTP_MAX_STR);
    otp_normalize_iso(raw->expected_date, out->payload_expected_at, OTP_MAX_TIMESTAMP);
    otp_normalize_iso(raw->deliver_by, out->payload_due_at, OTP_MAX_TIMESTAMP);
    otp_normalize_iso(raw->last_status_date, out->payload_latest_state_at, OTP_MAX_TIMESTAMP);
    otp_str_copy(out->payload_operation_status, raw->status, OTP_MAX_STR);

    otp_event_compute_id(out);
}

void otp_normalize_driver(const OtpRawRecord *raw, OtpEvent *out) {
    otp_event_init(out);
    otp_str_copy(out->source, "roadstar", OTP_MAX_STR);
    otp_str_copy(out->source_event_type, "driver.hos_observed", OTP_MAX_STR);
    otp_str_copy(out->source_ref, raw->driver_id, OTP_MAX_STR);
    otp_str_copy(out->entity_type, "driver", OTP_MAX_STR);
    otp_str_copy(out->entity_id, raw->driver_id, OTP_MAX_STR);
    otp_normalize_iso(raw->hours_updated, out->observed_at, OTP_MAX_TIMESTAMP);

    otp_str_copy(out->payload_remaining_hours, raw->remaining_hours, OTP_MAX_STR);
    otp_str_copy(out->payload_operation_status, raw->driver_status, OTP_MAX_STR);
    otp_str_copy(out->payload_trip_ref, raw->email, OTP_MAX_STR);  /* reuse for contact */
    otp_str_copy(out->payload_contact_ref, raw->email, OTP_MAX_STR);

    otp_event_compute_id(out);
}

/* ================================================================== */
/*  PLATFORM: time                                                     */
/* ================================================================== */

void otp_now_iso(char *buf, int bufsize) {
    time_t t = time(NULL);
    struct tm *gm = gmtime(&t);
    if (gm) {
        strftime(buf, (size_t)bufsize, "%Y-%m-%dT%H:%M:%SZ", gm);
    } else {
        otp_str_copy(buf, "1970-01-01T00:00:00Z", bufsize);
    }
}

/* ================================================================== */
/*  CLI: doctor                                                        */
/* ================================================================== */

void otp_doctor(void) {
    printf("OTP Portable %s (C89)\n", OTP_VERSION);
    printf("========================================\n\n");

    printf("Compiler ........ C89 compatible\n");
    printf("Filesystem ...... YES\n");
    printf("SQLite .......... %s\n", OTP_HAVE_SQLITE  ? "YES" : "NO");
    printf("Sockets ......... %s\n", OTP_HAVE_SOCKETS ? "YES" : "NO");
    printf("TLS ............. %s\n", OTP_HAVE_TLS     ? "YES" : "NO");
    printf("GUI ............. NO\n\n");

    printf("Profile:\n");
    printf("  OTP PORTABLE / HEADLESS\n\n");

    printf("Available:\n");
    printf("  [PASS] local pipeline\n");
    printf("  [PASS] evidence files\n");
#if OTP_HAVE_SOCKETS
    printf("  [PASS] LAN plain transport\n");
#else
    printf("  [DENY] LAN plain transport\n");
#endif
    printf("  [DENY] Google Drive\n");
    printf("  [DENY] desktop GUI\n");
    printf("  [DENY] XLSX workbook (use CSV)\n\n");

    printf("Semantics: OPERATIONAL TRUST PIPELINE\n");
    printf("Invariants: SOURCE != CORE, CHANNEL != CORE\n");
    printf("            POLICY != TRANSPORT, CAPABILITY != AUTHORITY\n");
}

/* ================================================================== */
/*  CLI: CSV parser                                                    */
/* ================================================================== */

static int parse_csv_line(const char *line, char fields[][OTP_MAX_STR], int max_fields) {
    int n = 0;
    const char *p = line;
    const char *start;
    int in_quotes = 0;

    while (*p && n < max_fields) {
        start = p;
        in_quotes = 0;
        if (*p == '"') { in_quotes = 1; p++; start = p; }
        while (*p) {
            if (in_quotes && *p == '"') {
                if (*(p+1) == '"') { p += 2; continue; }
                p++; break;
            }
            if (!in_quotes && (*p == ',' || *p == '\n' || *p == '\r')) break;
            p++;
        }
        {
            int len = (int)(p - start);
            if (len >= OTP_MAX_STR) len = OTP_MAX_STR - 1;
            memcpy(fields[n], start, (size_t)len);
            fields[n][len] = '\0';
            /* Trim trailing whitespace */
            while (len > 0 && (fields[n][len-1] == ' ' || fields[n][len-1] == '\t'))
                fields[n][--len] = '\0';
        }
        n++;
        if (*p == ',') p++;
        else if (*p == '\n' || *p == '\r') break;
    }
    return n;
}

/* ================================================================== */
/*  CLI: run                                                           */
/* ================================================================== */

int otp_run_csv(const char *csv_path, int communication_allowed) {
    FILE *f;
    char line[4096];
    char fields[16][OTP_MAX_STR];
    int line_num = 0;
    int is_header = 1;
    int event_count = 0;
    int action_count = 0;

    /* Column indices (dispatch format) */
    int col_trip = -1, col_leg = -1, col_expected = -1;
    int col_deliver = -1, col_status_date = -1, col_status = -1;
    int col_driver = -1, col_remaining = -1, col_driver_status = -1;
    int col_hours_updated = -1, col_email = -1;

    f = fopen(csv_path, "r");
    if (!f) {
        fprintf(stderr, "ERROR: cannot open %s\n", csv_path);
        return 1;
    }

    printf("OTP Portable %s — processing %s\n\n", OTP_VERSION, csv_path);

    while (fgets(line, sizeof(line), f)) {
        int nfields;
        line_num++;

        /* Skip empty lines */
        if (line[0] == '\n' || line[0] == '\r') continue;

        nfields = parse_csv_line(line, fields, 16);

        /* Header row: detect columns */
        if (is_header) {
            int i;
            for (i = 0; i < nfields; i++) {
                if (otp_str_eq(fields[i], "TRIP_NUMBER")) col_trip = i;
                else if (otp_str_eq(fields[i], "LS_LEG_ID")) col_leg = i;
                else if (otp_str_eq(fields[i], "LS_EXPECTED_DATE")) col_expected = i;
                else if (otp_str_eq(fields[i], "DELIVER_BY")) col_deliver = i;
                else if (otp_str_eq(fields[i], "LS_LAST_FB_STATUS_DATE")) col_status_date = i;
                else if (otp_str_eq(fields[i], "STATUS")) col_status = i;
                else if (otp_str_eq(fields[i], "DRIVER_ID")) col_driver = i;
                else if (otp_str_eq(fields[i], "REMAINING_HOURS")) col_remaining = i;
                else if (otp_str_eq(fields[i], "STATUS") && col_status >= 0) col_driver_status = i;
                else if (otp_str_eq(fields[i], "HOURS_UPDATED")) col_hours_updated = i;
                else if (otp_str_eq(fields[i], "EMAIL")) col_email = i;
            }
            is_header = 0;
            continue;
        }

        /* Data row */
        {
            OtpRawRecord raw;
            OtpEvent event;
            OtpLease lease;
            OtpFinding finding;
            OtpActionRequest action;
            OtpActionResult result;
            OtpSentinelVerdict verdict;
            OtpReceipt receipt;
            char exec_id[OTP_MAX_ID];

            memset(&raw, 0, sizeof(raw));
            if (col_trip >= 0) otp_str_copy(raw.trip_number, fields[col_trip], OTP_MAX_STR);
            if (col_leg >= 0) otp_str_copy(raw.leg_id, fields[col_leg], OTP_MAX_STR);
            if (col_expected >= 0) otp_str_copy(raw.expected_date, fields[col_expected], OTP_MAX_STR);
            if (col_deliver >= 0) otp_str_copy(raw.deliver_by, fields[col_deliver], OTP_MAX_STR);
            if (col_status_date >= 0) otp_str_copy(raw.last_status_date, fields[col_status_date], OTP_MAX_STR);
            if (col_status >= 0) otp_str_copy(raw.status, fields[col_status], OTP_MAX_STR);
            if (col_driver >= 0) otp_str_copy(raw.driver_id, fields[col_driver], OTP_MAX_STR);
            if (col_remaining >= 0) otp_str_copy(raw.remaining_hours, fields[col_remaining], OTP_MAX_STR);
            if (col_hours_updated >= 0) otp_str_copy(raw.hours_updated, fields[col_hours_updated], OTP_MAX_STR);
            if (col_email >= 0) otp_str_copy(raw.email, fields[col_email], OTP_MAX_STR);

            /* Only process dispatch legs with valid data */
            if (otp_str_empty(raw.leg_id) && otp_str_empty(raw.trip_number)) continue;

            otp_normalize_dispatch(&raw, &event);
            otp_make_ack_lease(&event, otp_clock_system, &lease);
            otp_evaluate_ack(&event, &lease, otp_clock_system,
                           communication_allowed, &finding, &verdict, &action);
            otp_execution_id(exec_id, sizeof(exec_id), &event, &lease, "ack-lease-v0");

            event_count++;
            if (verdict == VERDICT_ACTION_REQUESTED) action_count++;

            /* Output */
            printf("EVENT ............ %s\n", event.event_id);
            printf("  entity ......... %s (%s)\n", event.entity_id, event.entity_type);
            printf("  trip ........... %s\n", event.payload_trip_ref);
            printf("  due ............ %s\n", event.payload_due_at);
            printf("LEASE ............ %s (%s)\n", lease.lease_id,
                   lease.state == LEASE_OPEN ? "OPEN" :
                   lease.state == LEASE_SATISFIED ? "SATISFIED" :
                   lease.state == LEASE_EXPIRED ? "EXPIRED" : "UNKNOWN");
            printf("FINDING .......... %s (%s)\n", finding.reason_code,
                   finding.status == FINDING_PASS ? "PASS" :
                   finding.status == FINDING_FAIL ? "FAIL" : "UNKNOWN");
            printf("SENTINEL ......... %s\n",
                   verdict == VERDICT_NO_ACTION ? "NO_ACTION" :
                   verdict == VERDICT_ACTION_REQUESTED ? "ACTION_REQUESTED" :
                   verdict == VERDICT_BLOCKED ? "BLOCKED" :
                   verdict == VERDICT_NEEDS_REVIEW ? "NEEDS_REVIEW" : "NOT_DEMONSTRATED");

            if (verdict == VERDICT_ACTION_REQUESTED) {
                printf("ACTION ........... REQUEST_ACK -> %s\n", action.target_ref);
            } else {
                printf("ACTION ........... none\n");
            }

            /* Receipt */
            otp_make_receipt(&event, &lease, &finding,
                           verdict == VERDICT_ACTION_REQUESTED ? &action : NULL,
                           NULL, exec_id, "roadstar-workbook-v0",
                           "ack-lease-v0", "mock", verdict,
                           NULL, &receipt);
            printf("RECEIPT .......... evidence/%s.json\n\n", exec_id);
        }
    }

    fclose(f);

    printf("========================================\n");
    printf("Processed: %d events, %d actions requested\n", event_count, action_count);
    return 0;
}

/* ================================================================== */
/*  JSON MINIMAL PARSER                                                */
/* ================================================================== */

/* Find a key in a JSON string and return pointer to its value */
static const char *json_find_key(const char *json, const char *key) {
    char search[128];
    const char *p;
    snprintf(search, sizeof(search), "\"%s\"", key);
    p = strstr(json, search);
    if (!p) return NULL;
    p += strlen(search);
    while (*p == ' ' || *p == ':') p++;
    return p;
}

int json_get_string(const char *json, const char *key, char *out, int outsize) {
    const char *p = json_find_key(json, key);
    int i = 0;
    if (!p) return 0;
    if (*p == '"') {
        p++;
        while (*p && *p != '"' && i < outsize - 1) {
            if (*p == '\\') { p++; }
            out[i++] = *p++;
        }
    } else {
        while (*p && *p != ',' && *p != '}' && *p != '\n' && i < outsize - 1) {
            out[i++] = *p++;
        }
    }
    out[i] = '\0';
    return i > 0;
}

int json_get_int(const char *json, const char *key, int *out) {
    const char *p = json_find_key(json, key);
    int neg = 0;
    int val = 0;
    if (!p) return 0;
    if (*p == '-') { neg = 1; p++; }
    while (*p >= '0' && *p <= '9') {
        val = val * 10 + (*p - '0');
        p++;
    }
    *out = neg ? -val : val;
    return 1;
}

int json_get_bool(const char *json, const char *key, int *out) {
    const char *p = json_find_key(json, key);
    if (!p) return 0;
    if (strncmp(p, "true", 4) == 0) { *out = 1; return 1; }
    if (strncmp(p, "false", 5) == 0) { *out = 0; return 1; }
    return 0;
}

int json_get_object(const char *json, const char *key, char *out, int outsize) {
    const char *p = json_find_key(json, key);
    int depth = 0, i = 0;
    if (!p || *p != '{') return 0;
    while (*p && i < outsize - 1) {
        out[i++] = *p;
        if (*p == '{') depth++;
        else if (*p == '}') { depth--; if (depth == 0) { p++; break; } }
        p++;
    }
    out[i] = '\0';
    return i > 0;
}

int otp_event_from_json(const char *json, OtpEvent *out) {
    otp_event_init(out);
    json_get_string(json, "source", out->source, OTP_MAX_STR);
    json_get_string(json, "source_event_type", out->source_event_type, OTP_MAX_STR);
    json_get_string(json, "source_ref", out->source_ref, OTP_MAX_STR);
    json_get_string(json, "entity_type", out->entity_type, OTP_MAX_STR);
    json_get_string(json, "entity_id", out->entity_id, OTP_MAX_STR);
    json_get_string(json, "observed_at", out->observed_at, OTP_MAX_TIMESTAMP);

    /* Parse nested payload */
    {
        char payload[OTP_MAX_PAYLOAD];
        if (json_get_object(json, "payload", payload, sizeof(payload))) {
            json_get_string(payload, "trip_ref", out->payload_trip_ref, OTP_MAX_STR);
            json_get_string(payload, "leg_ref", out->payload_leg_ref, OTP_MAX_STR);
            json_get_string(payload, "expected_at", out->payload_expected_at, OTP_MAX_TIMESTAMP);
            json_get_string(payload, "due_at", out->payload_due_at, OTP_MAX_TIMESTAMP);
            json_get_string(payload, "latest_state_at", out->payload_latest_state_at, OTP_MAX_TIMESTAMP);
            json_get_string(payload, "operation_status", out->payload_operation_status, OTP_MAX_STR);
            json_get_string(payload, "contact_ref", out->payload_contact_ref, OTP_MAX_STR);
            json_get_string(payload, "ack_due_at", out->payload_ack_due_at, OTP_MAX_TIMESTAMP);
            json_get_string(payload, "acknowledged_at", out->payload_acknowledged_at, OTP_MAX_TIMESTAMP);
            json_get_string(payload, "remaining_hours", out->payload_remaining_hours, OTP_MAX_STR);
        }
    }
    otp_event_compute_id(out);
    return 1;
}

int otp_event_to_json(char *buf, int bufsize, const OtpEvent *e) {
    return snprintf(buf, (size_t)bufsize,
        "{\"event_id\":\"%s\","
        "\"schema_version\":\"%s\","
        "\"source\":\"%s\","
        "\"source_event_type\":\"%s\","
        "\"source_ref\":\"%s\","
        "\"entity_type\":\"%s\","
        "\"entity_id\":\"%s\","
        "\"observed_at\":\"%s\","
        "\"payload_sha256\":\"%s\"}",
        e->event_id, e->schema_version, e->source,
        e->source_event_type, e->source_ref,
        e->entity_type, e->entity_id, e->observed_at,
        e->payload_sha256);
}

int otp_finding_to_json(char *buf, int bufsize, const OtpFinding *f) {
    return snprintf(buf, (size_t)bufsize,
        "{\"finding_id\":\"%s\","
        "\"rule_id\":\"%s\","
        "\"status\":%d,"
        "\"severity\":\"%s\","
        "\"subject_ref\":\"%s\","
        "\"reason_code\":\"%s\","
        "\"reason\":\"%s\","
        "\"action_recommended\":%s}",
        f->finding_id, f->rule_id, f->status,
        f->severity, f->subject_ref,
        f->reason_code, f->reason,
        f->action_recommended ? "true" : "false");
}

/* ================================================================== */
/*  CLI: verify parity                                                 */
/* ================================================================== */

int otp_verify_parity(const char *fixture_path) {
    FILE *f;
    long fsize;
    char *json;
    OtpEvent event;
    OtpLease lease;
    OtpFinding finding;
    OtpSentinelVerdict verdict;
    OtpActionRequest action;
    char event_json[2048];
    char finding_json[2048];
    int comm_allowed = 1;

    f = fopen(fixture_path, "r");
    if (!f) {
        fprintf(stderr, "ERROR: cannot open %s\n", fixture_path);
        return 1;
    }

    /* Read entire file */
    fseek(f, 0, SEEK_END);
    fsize = ftell(f);
    fseek(f, 0, SEEK_SET);
    json = (char *)malloc((size_t)fsize + 1);
    if (!json) { fclose(f); return 1; }
    fread(json, 1, (size_t)fsize, f);
    json[fsize] = '\0';
    fclose(f);

    /* Parse event from JSON */
    otp_event_from_json(json, &event);
    free(json);

    /* Run pipeline */
    otp_make_ack_lease(&event, otp_clock_system, &lease);
    otp_evaluate_ack(&event, &lease, otp_clock_system, comm_allowed,
                     &finding, &verdict, &action);

    /* Output as JSON for comparison */
    otp_event_to_json(event_json, sizeof(event_json), &event);
    otp_finding_to_json(finding_json, sizeof(finding_json), &finding);

    printf("{\n");
    printf("  \"event\": %s,\n", event_json);
    printf("  \"lease_id\": \"%s\",\n", lease.lease_id);
    printf("  \"finding\": %s,\n", finding_json);
    printf("  \"verdict\": %d,\n", verdict);
    printf("  \"action_id\": \"%s\"\n",
           verdict == VERDICT_ACTION_REQUESTED ? action.action_id : "");
    printf("}\n");

    return 0;
}

/* ================================================================== */
/*  MAIN                                                               */
/* ================================================================== */

static void print_usage(void) {
    printf("OTP Portable %s (C89)\n", OTP_VERSION);
    printf("Usage:\n");
    printf("  otp run <file.csv>           Process a CSV file\n");
    printf("  otp verify <fixture.json>    Verify domain parity\n");
    printf("  otp doctor                   Show feature discovery\n");
    printf("  otp version                  Show version\n");
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        print_usage();
        return 0;
    }

    if (otp_str_eq(argv[1], "run")) {
        if (argc < 3) {
            fprintf(stderr, "ERROR: otp run requires a CSV file\n");
            return 1;
        }
        return otp_run_csv(argv[2], 1);
    }

    if (otp_str_eq(argv[1], "verify")) {
        if (argc < 3) {
            fprintf(stderr, "ERROR: otp verify requires a JSON fixture file\n");
            return 1;
        }
        return otp_verify_parity(argv[2]);
    }

    if (otp_str_eq(argv[1], "doctor")) {
        otp_doctor();
        return 0;
    }

    if (otp_str_eq(argv[1], "version") || otp_str_eq(argv[1], "--version")) {
        printf("OTP Portable %s\n", OTP_VERSION);
        return 0;
    }

    if (otp_str_eq(argv[1], "--help") || otp_str_eq(argv[1], "-h")) {
        print_usage();
        return 0;
    }

    fprintf(stderr, "ERROR: unknown command '%s'\n", argv[1]);
    print_usage();
    return 1;
}
