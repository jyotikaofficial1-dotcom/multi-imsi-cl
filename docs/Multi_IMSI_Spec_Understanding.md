# Tata Communications Generic Multi-IMSI v2.6 — Specification Understanding

This document captures the working understanding of the Multi-IMSI applet
behaviour, file system, and encoding rules used by this test tool. It is
derived from the Tata Generic Multi-IMSI v2.6 specification, the card
personalization data (Variables.txt), and observed behaviour on real cards.

---

## 1. Overview

The Multi-IMSI applet allows a single UICC to hold several IMSI profiles
(typically one roaming IMSI and one or more home IMSIs) and switch the
active profile automatically based on the serving network (PLMN) reported
by the handset, or manually via the STK menu / OTA.

When a switch occurs, the applet rewrites the standard network files
(EF_IMSI, EF_SMSP, EF_SPN, EF_ACC, …) from its internal per-profile
storage and issues a proactive **REFRESH** so the handset re-reads them
and re-attaches with the new IMSI.

| Term | Meaning |
|---|---|
| IMSI Index | 1-based slot number of a profile (1 = roaming/priority, 2..N = home) |
| PRIO_IMSI | Fallback/priority index used when no mapping applies (index 1) |
| Normal service | Handset successfully registered on the PLMN |
| Limited service | Emergency-only / registration rejected on the PLMN |

---

## 2. Application Selection (AIDs)

AIDs **differ between card batches** — they must not be hardcoded.
The tool reads **EF DIR (2F00) under the MF (3F00)** at connect time and
parses the Application Template TLVs:

```
61 LL                      Application Template
   4F LL <AID>             Application Identifier
   50 LL <label>           Application Label (e.g. "USIM")
```

Classification: RID `A000000087` + PIX starting `1002` → USIM,
`1004` → ISIM. Examples seen on real cards:

| Card | USIM AID |
|---|---|
| Reference card | `A0000000871002FF33FF018900000100` |
| User card | `A0000000871002FFFFFFFF89010300` |

All test cases obtain the AID at runtime via
`tests.card_config.get_usim_aid()` / `get_isim_aid()`.

---

## 3. File System Layout

```
MF (3F00)
├── EF DIR (2F00)                — application AIDs
├── DF GSM (7F20)
│   ├── EF_IMSI (6F07)           — active IMSI (rewritten on switch)
│   ├── EF_ACC  (6F78)           — access control class (per profile)
│   ├── EF_SPN  (6F46)           — service provider name (per profile)
│   └── EF_SMSP (6F42)           — SMS parameters / SMSC (per profile)
├── DF TELECOM (7F10)
└── DF 7F30
    └── DF 5F1A                  — Multi-IMSI proprietary directory
        ├── EF 4F01  Config
        ├── EF 4F03  MCC Mapping List
        ├── EF 4F07  IMSI List
        └── (other per-profile storage EFs: SMSP/SPN/ACC lists, FPLMN, …)
```

Selection path used by the tool: `select_by_path("7F305F1A")` then
`select_by_id("4FXX")`.

> Note: reads at end-of-file return **SW=6282** (End of File reached
> before Le bytes) with data — this is a warning, not an error, and the
> returned data is valid.

---

## 4. EF 4F01 — Config

Transparent EF holding applet configuration and runtime state.
Key fields (offsets from observed personalization
`01010301040A01FF10526F616D696E67…`):

| Offset | Meaning |
|---|---|
| 0 | Applet enabled / mode flag |
| 1 | Number of profiles personalised |
| 2 | **Active IMSI index** (read by tests to verify a switch occurred) |
| 3+ | Priority IMSI, timers/retry, STK menu title ("Roaming Service"), embedded USIM AID, … |

The tool reads byte at offset 2 to determine the currently active profile.

---

## 5. EF 4F03 — MCC Mapping List

Transparent EF, **500 bytes**, up to **125 entries**, **4 bytes each**:

```
Bytes 0-2 : PLMN (GSM TS 24.008 §10.5.1.13 encoding, see §8)
Byte  3   : mapped IMSI index (1-based)
```

Special values:

- Nibble **0xD** in any PLMN digit position = **wildcard** (proprietary,
  matches any digit). `DDDDDD` = match-all default entry, normally last.
- MNC digit 3 = **0xF** = standard 2-digit-MNC filler (exact 2-digit match).
- `FFFFFFFF` entries = unused/padding.
- IMSI index `0xDD` observed on production cards = wildcard/default index
  marker; `0xFF` = unused.

### Reference personalization (12 entries)

| # | Raw | PLMN | Country | IMSI idx |
|---|---|---|---|---|
| 1 | `46D2DD01` | 642/DD | Burundi | 1 |
| 2 | `43D6DD01` | 346/DD | Cayman Islands | 1 |
| 3 | `26D3DD01` | 623/DD | Central African Rep. | 1 |
| 4 | `24D4DD02` | 424/DD | UAE | 2 |
| 5 | `34D1DD02` | 431/DD | UAE | 2 |
| 6 | `64F03002` | 460/03 | China (exact MNC) | 2 |
| 7 | `64F05003` | 460/05 | China (exact MNC) | 3 |
| 8 | `64D0DD01` | 460/DD | China (wildcard MNC) | 1 |
| 9 | `04D4DD03` | 404/DD | India (1st entry) | 3 |
| 10 | `04D4DD02` | 404/DD | India (2nd entry) | 2 |
| 11 | `02D4DD03` | 204/DD | Netherlands | 3 |
| 12 | `DDDDDD01` | DDD/DD | Default (match-all) | 1 |

### Matching algorithm

**Normal service** (location status = 0):
1. Scan the list top-down; first entry whose PLMN matches (wildcards
   allowed) wins → switch to its IMSI index.
2. Exact-MNC entries only match that MNC; the wildcard-MNC entry for the
   same MCC catches all other MNCs (ordering in the list matters: exact
   entries are placed before the wildcard entry).
3. No match at all → the `DDDDDD` default entry → PRIO_IMSI.

**Limited service** (location status = 1) on the currently mapped IMSI:
1. Find the first matching entry (the "priority" mapping).
2. Continue scanning **forward** for another entry with the **same
   MCC/PLMN** → switch to that entry's IMSI index (the "preferred"
   fallback). Example: India limited on entry 9 (idx 3) → entry 10 → idx 2;
   China limited on `460/03` (idx 2) → next 460 entry `460/05` → idx 3.
3. If no second entry exists for that MCC (e.g. UAE) → fall back to
   **PRIO_IMSI** (index 1), then iterate through remaining indices if
   still limited.

---

## 6. EF 4F07 — IMSI List

Stores the per-profile IMSI values, each in the standard EF_IMSI format:
9 bytes = length byte (`08`) + 8 bytes BCD with parity/oddness nibble
(TS 31.102 §4.2.2). Reference card profiles:

| Index | Raw | Role |
|---|---|---|
| 1 | `082940809073135906` | Roaming / priority |
| 2 | `082980106122870000` | Home 1 |
| 3 | `082940700100873000` | Home 2 |

On switch, the entry for the new index is copied into `7F20/6F07`.

---

## 7. Per-profile network files

Each profile has its own copy of these, swapped into DF GSM on switch:

| EF | Record size | Content |
|---|---|---|
| EF_SMSP (6F42) | 43 bytes (0x2B) | alpha id + 27-byte fixed trailer: TP-PI(1) TP-DA(10) TP-SCA(10) TP-PID(1) TP-DCS(1) TP-VP(1…) — SMSC number per profile |
| EF_SPN (6F46) | 17 bytes (0x11) | display-condition byte + GSM-7 name (e.g. "IMSI 1/2/3") |
| EF_ACC (6F78) | 2 bytes | access class bitmask (e.g. `0001` = class 0) |

---

## 8. PLMN Encoding (GSM TS 24.008 §10.5.1.13)

3 bytes, nibble-swapped BCD:

```
Byte 0 : MCC digit 2 (hi) | MCC digit 1 (lo)
Byte 1 : MNC digit 3 (hi) | MCC digit 3 (lo)     MNC3 = 0xF for 2-digit MNC
Byte 2 : MNC digit 2 (hi) | MNC digit 1 (lo)
```

Examples:
- `02F466` → MCC 204, MNC 66 (Netherlands, 2-digit)
- `64F030` → MCC 460, MNC 03 (China)
- `04D4DD` → MCC 404, MNC DD (India, wildcard MNC)

The tool's MCC→country mapping follows ITU-T E.212
(`engine/mcc_lookup.py`).

---

## 9. Triggering a Switch (test method)

The tool simulates network events with an
**ENVELOPE (EVENT DOWNLOAD – Location Status)**:

```
80 C2 00 00 Lc
  D6 LL                       Event Download tag
     82 02 83 81              Device identities (network → UICC)
     99 01 SS                 Location status: 00=Normal 01=Limited 02=No service
     9B 06 0000 <PLMN> 0000   Location information (LAC + PLMN + cell id)
                              (omitted for No-service)
```

Required prologue after reset:
**TERMINAL PROFILE** (`80 10 00 00 0C FF…FF`) then drain proactive
commands: while SW1=`91`, **FETCH** (`80 12 00 00 SW2`) and reply
**TERMINAL RESPONSE** OK (`80 14 …`). A switch typically surfaces as a
fetched **REFRESH** proactive command.

Verification after a triggered event: re-select `7F30/5F1A/4F01` and read
the active-index byte (offset 2), and/or read `7F20/6F07` and compare with
the expected entry from EF 4F07.

---

## 10. Status Word handling

| SW | Meaning | Tool behaviour |
|---|---|---|
| 9000 | OK | success |
| 91XX | OK, proactive command pending | FETCH XX bytes |
| 6282 | End of file reached before Le | **success** — keep data, stop chunked read |
| 6A82 | File/application not found | wrong AID/path — triggers AID discovery fallback |
| 6982 | Security status not satisfied | ADM verify required (`00 20 00 0A 08 <key>`) |

---

## 11. Test coverage map

| Suite | Covers |
|---|---|
| `tc_mcc_list.py` (TC-MCC-01…12) | 4F03 structure, Normal exact/wildcard match, Limited second-entry & PRIO_IMSI fallback, default entry |
| `tc_auto_switch.py` | Location-status driven switching using the card's own PLMN |
| `tc_switch_files.py` | EF_IMSI/SMSP/SPN/ACC contents after switch |
| `tc_files.py` | Multi-IMSI EF presence/sizes |
| `tc_stk_menu.py` / `tc_stk_pcom.py` | Manual switch via STK menu selection |
| `tc_ota.py`, `tc_5g.py`, `tc_negative.py`, `tc_isim.py` | OTA, 5G files, negative paths, ISIM |

The **Card Info** tab in the GUI auto-reads 4F01/4F03/4F07 and the
standard EFs on power-on and shows the ETSI-decoded contents, including
country names per MCC.
