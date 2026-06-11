# Multi-IMSI Test Tool — Test Case & APDU Reference

Complete reference of all test cases in the suite, with description and the
APDU sequence executed for each. Companion to
`Multi_IMSI_Spec_Understanding.md`.

**Total: 65 test cases across 12 suites.**

---

## 0. Common APDU Primitives

All test cases are built from these APDUs (hex, spaces for readability):

| Operation | APDU | Notes |
|---|---|---|
| SELECT MF | `00 A4 00 0C 02 3F00` | |
| SELECT by path (DF Multi-IMSI) | `00 A4 08 0C 04 7F30 5F1A` | path from MF |
| SELECT EF by FID | `00 A4 00 0C 02 <FID>` | e.g. `4F01` |
| SELECT ADF USIM by AID | `00 A4 04 0C <Lc> <AID>` | AID from EF DIR (varies per card) |
| READ BINARY | `00 B0 <P1> <P2> <Le>` | P1P2 = offset |
| UPDATE BINARY | `00 D6 <P1> <P2> <Lc> <data>` | |
| READ RECORD | `00 B2 <rec> 04 <Le>` | absolute record mode |
| STATUS | `00 F2 00 00 00` | |
| VERIFY ADM | `00 20 00 0A 08 <8-byte key>` | key `3733323339313637` |
| TERMINAL PROFILE | `80 10 00 00 0C FF FF FF FF FF FF FF FF FF FF FF FF` | |
| FETCH | `80 12 00 00 <Le>` | Le = SW2 of preceding `91 XX` |
| TERMINAL RESPONSE (OK) | `80 14 00 00 0C 01 03 01 <type> 00 02 02 82 81 03 01 00` | |
| ENVELOPE | `80 C2 00 00 <Lc> <BER-TLV>` | see below |

### ENVELOPE — Location Status (Event Download)

Normal (SS=00) / Limited (SS=01) service, with PLMN:

```
80 C2 00 00 11
   D6 0F                       Event Download
      82 02 83 81              Device identities (network → UICC)
      99 01 SS                 Location status
      9B 06 00 00 <PLMN3> 00 00   Location info (LAC + PLMN + cell id)
```

No service (SS=02), no location info:

```
80 C2 00 00 09  D6 07  82 02 83 81  99 01 02
```

### ENVELOPE — Menu Selection

```
80 C2 00 00 0B
   D3 09
      82 02 01 82              Device identities (keypad → UICC)
      90 01 XX                 Item identifier
      91 01 00                 Help request: no
```

### PLMN encodings used in this document (TS 24.008)

| MCC/MNC | PLMN hex | | MCC/MNC | PLMN hex |
|---|---|---|---|---|
| 204/66 | `02 F4 66` | | 424/01 | `24 F4 10` |
| 460/03 | `64 F0 30` | | 424/02 | `24 F4 20` |
| 460/05 | `64 F0 50` | | 431/01 | `34 F1 10` |
| 460/99 | `64 F0 99` | | 404/01 | `04 F4 10` |
| 999/01 | `99 F9 10` | | 404/20 | `04 F4 02` |
| 000/00 | `00 F0 00` | | | |

Worked example — Normal service China 460/03:

```
TX: 80 C2 00 00 11 D6 0F 82 02 83 81 99 01 00 9B 06 00 00 64 F0 30 00 00
RX: 9000 (or 91 XX if a proactive REFRESH is pending → FETCH)
```

**Session prologue** (all suites, after ATR): TERMINAL PROFILE, then while
SW1=`91`: FETCH(SW2) + TERMINAL RESPONSE OK. AID discovery: SELECT MF →
SELECT 2F00 (`00 A4 00 04 02 2F00`) → READ BINARY → parse tag 61/4F.

Below, "Select 4FXX" implies the preceding `00 A4 08 0C 04 7F30 5F1A`
unless the DF is already current.

---

## 1. Applet Init (tc_init.py)

### TC-INIT-01 — Verify applet enable flag activates menu (P1)
Reads EF_Config (4F01) bytes 0–2: byte 0 = 01 (enabled), byte 1 = 01
(auto mode), byte 2 = active IMSI index in range 1–10.

```
00 A4 08 0C 04 7F30 5F1A        → 9000
00 A4 00 0C 02 4F01             → 9000
00 B0 00 00 03                  → 01 01 0X / 9000
```

### TC-INIT-02 — Applet disabled: menu must not appear (P1)
Writes 00 to byte 0 of 4F01 (disable), reads back, restores original.

```
00 A4 08 0C 04 7F30 5F1A        → 9000
00 A4 00 0C 02 4F01             → 9000
00 B0 00 00 32                  → <50 bytes config> / 9000   (save original)
00 D6 00 00 32 00 <bytes 1..49> → 9000                       (byte0=00)
00 B0 00 00 01                  → 00 / 9000
00 D6 00 00 32 <original>       → 9000                       (restore)
```

### TC-INIT-03 — Verify poll interval registration (P2)
X = menu-text length at offset 8; asserts byte at offset 9+X = 1E (30 s).

```
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F01 → 9000
00 B0 00 00 32                  → 9000 ; assert data[9+X] == 1E
```

### TC-INIT-04 — Max IMSI profiles field = 0x0A (P2)
```
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F01 → 9000
00 B0 00 00 06                  → 9000 ; assert byte 5 == 0A
```

### TC-INIT-05 — EF_Config ISIM/USIM AID fields valid (P1)
Locates ISIM AID length at offset X+21 (10–16), then validates the USIM
AID that follows (length 10–16, prefix `A000000087`).

```
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F01 → 9000
00 B0 00 00 32                  → 9000 ; parse AID fields
```

---

## 2. File Validation (tc_files.py)

### TC-FILE-01 — EF_IMSI_List (4F07): size and BCD encoding (P1)
90 bytes (10 × 9); IMSI_1 not FF×9; length byte 07 or 08.

```
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F07 → 9000
00 B0 00 00 5A                  → <90 bytes> / 9000
```

### TC-FILE-02 — EF_MCC_Mapping_List (4F03): PLMN encoding & wildcard (P1)
500 bytes in two chunks; every entry's index byte ∈ 01–0A or FF; at
least one entry contains a 0xD wildcard nibble.

```
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F03 → 9000
00 B0 00 00 FF                  → <255 bytes> / 9000
00 B0 00 FF F1                  → <245 bytes> / 9000 (or 6282 at EOF)
```

### TC-FILE-03 — EF_SPN_List (4F46): 17-byte records (P2)
170 bytes; SPN_1 personalised; display-condition byte 00/01.

```
00 A4 00 0C 02 4F46 → 9000 ; 00 B0 00 00 AA → <170 bytes> / 9000
```

### TC-FILE-04 — EF_ACC_List (4F78): 2 bytes per profile (P2)
```
00 A4 00 0C 02 4F78 → 9000 ; 00 B0 00 00 14 → <20 bytes> / 9000
```

### TC-FILE-05 — EF_AD_USIM_List (6FAD): 4-byte AD records (P2)
40 bytes; AD_1 MNC-length byte (offset 2) = 02 or 03.

```
00 A4 00 0C 02 6FAD → 9000 ; 00 B0 00 00 28 → <40 bytes> / 9000
```

### TC-FILE-06 — EF_PLMNwACT_List (4F60) = 10 × EF_PLMNwACT size (P2)
```
00 A4 04 0C <Lc> <USIM AID>     → 9000
00 A4 00 0C 02 6F60 / 00 B0 00 00 28 → 9000  (per-profile size)
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F60 → 9000
00 B0 00 00 <size×10, ≤EF>      → 9000 ; validate 5-byte PLMN+ACT entries
```

### TC-FILE-07 — EF_FPLMN_List (4F7B): 120 bytes, 10 × 12 (P2)
```
00 A4 00 0C 02 4F7B → 9000 ; 00 B0 00 00 78 → <120 bytes> / 9000
```

---

## 3. Auto Switch (tc_auto_switch.py)

Uses the card's own PLMN decoded from `MCC_MNC_HEX = 02F466` →
MCC=204, MNC=66. `IDX` = MCC_IMSI_INDEX (3), `PRIO` = PRIO_IMSI (1).

### TC-AUTO-01 — Normal service: PLMN match → mapped IMSI (P1)
```
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F07 → 9000
00 B0 00 12 09                  → <expected IMSI slot 3> / 9000
80 C2 00 00 11 D6 0F 82 02 83 81 99 01 00 9B 06 00 00 02 F4 66 00 00 → 9000/91XX
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F01 → 9000
00 B0 00 02 01                  → 03 / 9000     (active index = IDX)
00 A4 04 0C <Lc> <USIM AID>     → 9000
00 A4 00 0C 02 6F07 / 00 B0 00 00 09 → must equal saved IMSI slot
```

### TC-AUTO-02 — Same PLMN again: no switch (P1)
Read index → send same Location Status envelope (`…02 F4 66…`) → re-read
index at `00 B0 00 02 01` → unchanged.

### TC-AUTO-03 — Limited service → priority IMSI (P1)
```
80 C2 00 00 11 D6 0F 82 02 83 81 99 01 01 9B 06 00 00 02 F4 66 00 00 → 9000
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F01 / 00 B0 00 02 01 → 01 / 9000
```

### TC-AUTO-04 — Unknown PLMN (999/01) → default index (P1)
```
80 C2 00 00 11 D6 0F 82 02 83 81 99 01 00 9B 06 00 00 99 F9 10 00 00 → 9000
00 B0 00 02 01 (after select 4F01) → 01 / 9000   (= PRIO_IMSI)
```

### TC-AUTO-05 — Auto mode disabled: no switch on location event (P2)
```
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F01 → 9000
00 D6 00 01 01 00               → 9000          (disable auto mode)
00 B0 00 02 01                  → save index
80 C2 00 00 11 D6 0F 82 02 83 81 99 01 00 9B 06 00 00 02 F4 66 00 00 → 9000
00 B0 00 02 01 (re-select 4F01) → unchanged
00 D6 00 01 01 01               → 9000          (restore)
```

---

## 4. MCC List (tc_mcc_list.py)

Validates the 12-entry personalization (see spec doc §5) and the
Normal/Limited matching algorithm. After each envelope the active index
is read with: select 7F30/5F1A → select 4F01 → `00 B0 00 02 01`.

### TC-MCC-01 — File size and first entry structure (P1)
```
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F03 → 9000
00 B0 00 00 30                  → <48 bytes> / 9000
assert data[0:4] == 46 D2 DD 01 (Burundi 642/DD → IMSI 1)
```

### TC-MCC-02 — Verify all 12 personalised entries (P1)
Same read; full 48 bytes must equal
`46D2DD01 43D6DD01 26D3DD01 24D4DD02 34D1DD02 64F03002 64F05003 64D0DD01 04D4DD03 04D4DD02 02D4DD03 DDDDDD01`.

### TC-MCC-03 — Normal, exact match China 460/03 → IMSI 2 (P1)
```
80 C2 00 00 11 D6 0F 82 02 83 81 99 01 00 9B 06 00 00 64 F0 30 00 00 → 9000
read active index → 02
```

### TC-MCC-04 — Normal, exact match China 460/05 → IMSI 3 (P1)
Envelope with PLMN `64 F0 50`; index → 03.

### TC-MCC-05 — Normal, wildcard MNC UAE 424/01 → IMSI 2 (P1)
Envelope with PLMN `24 F4 10`; entry `24D4DD02` matches; index → 02.

### TC-MCC-06 — Normal, wildcard MNC Netherlands 204/66 → IMSI 3 (P1)
Envelope with PLMN `02 F4 66`; entry `02D4DD03` matches; index → 03.

### TC-MCC-07 — Normal, no match → default DDDDDD → IMSI 1 (P1)
Envelope with PLMN `99 F9 10` (999/01); index → 01.

### TC-MCC-08 — Limited, second entry same PLMN: India → IMSI 2 (P1)
```
80 C2 00 00 11 D6 0F 82028381 990100 9B06 0000 04F410 0000 → 9000  (setup: Normal 404/01)
read index → 03                                  (entry 9 priority)
80 C2 00 00 11 D6 0F 82028381 990101 9B06 0000 04F410 0000 → 9000  (Limited)
read index → 02                                  (entry 10 preferred)
```

### TC-MCC-09 — Limited, next same-MCC entry: China → IMSI 3 (P1)
Normal `64 F0 30` → index 02; Limited `64 F0 30` → forward scan hits
`64F05003` → index 03.

### TC-MCC-10 — Limited, no second entry: UAE → fallback PRIO (P1)
Normal `24 F4 10` → index 02; Limited `24 F4 10` → no second 424 entry →
index = PRIO_IMSI (01).

### TC-MCC-11 — Normal, China 460/99 → wildcard entry → IMSI 1 (P2)
Envelope with PLMN `64 F0 99`; exact entries don't match, `64D0DD01`
does; index → 01.

### TC-MCC-12 — Normal, UAE 431/01 → IMSI 2 (P2)
Envelope with PLMN `34 F1 10`; entry `34D1DD02` matches; index → 02.

---

## 5. Switch Files (tc_switch_files.py)

Pattern: read expected per-profile value from the 7F30/5F1A list EF,
trigger a switch with Location Status envelope (Normal 424/02 →
`24 F4 20` → index 2), then verify the standard EF in ADF USIM.

### TC-SWITCH-01 — EF_IMSI updated after switch (P1)
```
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F01 → 9000
00 D6 00 02 01 01               → 9000          (force index 01 first)
00 A4 00 0C 02 4F07 / 00 B0 00 09 09 → save IMSI_2
80 C2 00 00 11 D6 0F 82028381 990100 9B06 0000 24F420 0000 → 9000
00 A4 04 0C <Lc> <USIM AID> / 00 A4 00 0C 02 6F07 / 00 B0 00 00 09 → = IMSI_2
```

### TC-SWITCH-02 — SPN updated (P1)
`4F46` read at offset 17 (`00 B0 00 11 11`) → switch → ADF USIM `6F46`
`00 B0 00 00 11` → must equal SPN_2.

### TC-SWITCH-03 — ACC updated (P1)
`4F78` `00 B0 00 02 02` → switch → `6F78` `00 B0 00 00 02` → = ACC_2.

### TC-SWITCH-04 — SMSP updated (P2)
`4F42` `00 B0 00 1C 1C` → switch → `6F42` READ RECORD 1
(`00 B2 01 04 1C`) → = SMSP_2.

### TC-SWITCH-05 — PLMNwACT updated (P2)
`4F60` `00 B0 00 28 28` → switch → `6F60` `00 B0 00 00 28` → = slot 2.

### TC-SWITCH-06 — FPLMN cleared before REFRESH (P1)
```
00 A4 04 0C <Lc> <USIM AID> / 00 A4 00 0C 02 6F7B → 9000
00 D6 00 00 03 24 F2 99         → 9000          (plant dummy FPLMN)
80 C2 00 00 11 D6 0F 82028381 990100 9B06 0000 24F420 0000 → 9000
00 A4 04 0C <AID> / 00 A4 00 0C 02 6F7B / 00 B0 00 00 0C → FF×12 / 9000
```

### TC-SWITCH-07 — Location files reset before REFRESH (P1)
Switch (Normal 404/20 → `04 F4 02`), then:
```
00 A4 00 0C 02 6F7E / 00 B0 00 00 0B → 9000 ; last byte ∈ {00,01}
00 A4 00 0C 02 6FE3 / 00 B0 00 00 12 → 9000   (EPSLOCI accessible)
```

### TC-SWITCH-08 — REFRESH issued at end of switch (P1)
Read 4F01 (50 bytes, extract REFRESH-type offset), switch via
`24 F4 20` envelope, then `00 A4 00 0C 02 3F00` → 9000 (card responsive).

---

## 6. STK Menu (tc_stk_menu.py)

Menu selections via ENVELOPE `D3` (see §0). Active index read =
select 7F30/5F1A → 4F01 → `00 B0 00 02 01`.

### TC-STK-01 — 'Next IMSI' item (P1)
```
read index (before)
80 C2 00 00 0B D3 09 82 02 01 82 90 01 01 91 01 00 → 9000/91XX
read index (after) → changed (increment, wraps 10→1)
```

### TC-STK-02 — 'Priority IMSI' item (P1)
```
80 C2 00 00 0B D3 09 82 02 01 82 90 01 02 91 01 00 → 9000/91XX
read index → 01
```

### TC-STK-03 — 'Lock IMSI' item (P2)
```
80 C2 00 00 11 D6 0F … 24F420 …  → switch to index 02
80 C2 00 00 0B D3 09 82 02 01 82 90 01 03 91 01 00 → 9000  (lock)
80 C2 00 00 11 D6 0F … 04F402 …  → location event for other PLMN
read index → still 02 (locked)
```

### TC-STK-04 — 'Automatic Mode' toggle (P2)
```
00 B0 00 01 01 (after select 4F01) → save auto-mode byte
80 C2 00 00 0B D3 09 82 02 01 82 90 01 04 91 01 00 → 9000
00 B0 00 01 01 → flipped (00↔01) ; toggle again to restore if needed
```

---

## 7. STK PCOM-style (tc_stk_pcom.py)

Full end-to-end flows with ADM auth and FETCH/TERMINAL RESPONSE
handling; after each switch all four standard EFs (6F07/6F78/6F46/6F42)
are verified against the per-index expected vectors in card_config.

Common prologue:
```
00 20 00 0A 08 37 33 32 33 39 31 36 37   → 9000   (VERIFY ADM)
00 A4 00 0C 02 7F30 / 00 A4 00 0C 02 5F1A / 00 A4 00 0C 02 4F01 → 9000
00 B0 00 00 36                            → current index = byte 2
80 10 00 00 0C FF×12 ; while 91XX: 80 12 00 00 XX + 80 14 … (drain STK)
```

### TC-STK-NEXT-IMSI — switch to next profile (P1)
Open menu (`…90 01 80…`), select item 01; on `91 XX` FETCH the REFRESH
and send TERMINAL RESPONSE; verify EF_IMSI/ACC/SPN/SMSP equal the
vectors for index (current % MAX_PROFILES)+1.

### TC-STK-PRIORITY-IMSI — switch to priority profile (P1)
Menu item 02; handle REFRESH; verify all standard EFs match PRIO_IMSI
(index 1) vectors: IMSI `082940809073135906`, SMSC `…1356039930F0…`,
SPN "IMSI 1", ACC `0001`.

### TC-STK-LOCK-IMSI — LOCI event blocked after lock (P2)
Menu item 03 (lock); then Location Status envelope with `02 F4 66` →
expect 9000 with **no** switch; `00 B0 00 02 01` → index unchanged.

### TC-STK-AUTO-MODE — toggle and verify location switching (P2)
Menu item 04; `00 B0 00 00 02` confirms auto-mode byte flipped; send
`02 F4 66` envelope → expect 9000 (no switch) if already on
MCC_IMSI_INDEX, else `91 0B` + REFRESH; verify EFs for the expected index.

### TC-STK-DEFAULT-SWITCH — default switching via LOCI (P1)
Location Status envelope with PLMN `55 F5 66` (unlisted → default
entry); on `91 XX` FETCH/RESPOND (REFRESH); verify standard EFs match
PRIO_IMSI profile.

---

## 8. Round Robin (tc_round_robin.py)

### TC-RR-01 — RR enabled: cycles index on network loss (P1)
```
00 B0 00 06 01 (after select 4F01) → 01 (RR enabled)
80 C2 00 00 09 D6 07 82 02 83 81 99 01 02 → 9000   (No Service #1)
00 B0 00 02 01 → save idx1
80 C2 00 00 09 D6 07 82 02 83 81 99 01 02 → 9000   (No Service #2)
00 B0 00 02 01 (re-select 4F01) → ≠ idx1 (cycled)
```

### TC-RR-02 — RR disabled: no cycling (P1)
```
00 D6 00 06 01 00 → 9000      (disable RR)
00 B0 00 02 01    → save index
80 C2 00 00 09 D6 07 82 02 83 81 99 01 02 → 9000
00 B0 00 02 01    → unchanged
00 D6 00 06 01 01 → 9000      (restore)
```

### TC-RR-03 — Periodic switching via STATUS counter (P2)
```
00 B0 00 03 02 (after select 4F01) → byte0=01 (periodic on), byte1=counter N
repeat N-1×: 00 F2 00 00 00 → 9000          (no trigger)
00 F2 00 00 00 → 91 XX expected             (PLI LOCI fires)
```

### TC-RR-04 — Fallback to priority IMSI after counter expiry (P2)
```
00 B0 00 00 32 → X=data[8]; assert data[X+14]=01 (fallback mode); N=data[X+13]
80 C2 00 00 11 D6 0F … 24F420 … → 9000 ; index → 02
repeat N×: 00 F2 00 00 00
read index → 01 (reverted to priority)
```

---

## 9. 5G Files (tc_5g.py)

### TC-5G-01 — EF_5GS3GPPNSC_List (4F53): NAS security context (P2)
```
00 A4 00 0C 02 4F53 / 00 B0 00 00 FF → 9000
assert data[0]=A0 (SEQUENCE); inner tags 80 (ngKSI), 81 (keys),
82 (UL count), 83 (DL count) all present
```

### TC-5G-02 — EF_UAC_AIC_List (4F56): 4 bytes/profile (P2)
```
00 A4 00 0C 02 4F56 / 00 B0 00 00 28 → <40 bytes>/9000 ; slot 1 ≠ FFFFFFFF
```

### TC-5G-03 — EF_SUCI_Calc_Info_List (4F57): ECIES key 32 bytes (P2)
```
00 A4 00 0C 02 4F57 / 00 B0 00 00 FF → 9000
assert tag A0; find A1 → inner 81 length = 32
```

### TC-5G-04 — 5G files updated after IMSI switch (P1)
```
00 A4 00 0C 02 4F56 / 00 B0 00 04 04 → save UAC_AIC_2
80 C2 00 00 11 D6 0F … 24F420 …      → 9000  (switch to index 2)
00 A4 04 0C <USIM AID> / 00 A4 00 0C 02 4F56 / 00 B0 00 00 04 → = UAC_AIC_2
```

### TC-5G-05 — EF_Routing_Indicator_List (4F5A): BCD check (P2)
```
00 A4 00 0C 02 4F5A / 00 B0 00 00 28 → <40 bytes>/9000
RI_1 nibbles all ∈ {0–9, F}
```

---

## 10. Negative Tests (tc_negative.py)

### TC-NEG-01 — Read EF_Config without ADM → 6982 (P1)
```
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F01
00 B0 00 00 01 → expected SW = 6982
```
(Run on a fresh session with no prior VERIFY ADM.)

### TC-NEG-02 — UPDATE with wrong Lc → 6700 (P1)
```
00 A4 00 0C 02 4F07
00 D6 00 00 08 08 30 99 41 04 00 00 00 → expected SW = 6700
```
(8 data bytes against the required 9-byte IMSI slot.)

### TC-NEG-03 — Out-of-range index (0x0B): card stays operational (P2)
Read full 4F01, write copy with byte2=0B (`00 D6 00 00 32 …`), fire
`04 F4 02` location envelope, then `00 A4 00 0C 02 3F00` → 9000;
restore original config.

### TC-NEG-04 — Read beyond EOF of 4F03 → error (P2)
```
00 A4 00 0C 02 4F03
00 B0 01 F8 04 → expected SW ∈ {6B00, 6700, 6A86}
```

### TC-NEG-05 — Consistency after switch (P1)
Switch via `24 F4 20` envelope; read active index N from 4F01;
read `6F07` in ADF USIM (`00 B0 00 00 09`) and slot N of 4F07
(`00 B0 <(N-1)×9> 09`); both 9-byte values must be identical.

---

## 11. OTA (tc_ota.py)

### TC-OTA-01 — Remote update of EF_IMSI_List slot 3 (P1)
```
00 A4 00 0C 02 4F07 / 00 B0 00 12 09 → save original IMSI_3
00 D6 00 12 09 08 39 94 10 40 00 00 00 F0 → 9000   (write new IMSI)
00 B0 00 12 09 → read-back equals written value
00 A4 00 0C 02 3F00 → 9000                          (responsive)
00 A4 08 0C 04 7F30 5F1A / 00 A4 00 0C 02 4F07
00 D6 00 12 09 <original> → 9000                     (restore)
```

### TC-OTA-02 — External update of EF_Config poll interval (P2)
poll_offset = 9+X (X = byte 8 of 4F01):
```
00 B0 00 00 32 → 9000 ; compute offset
00 D6 <off> 01 3C → 9000 ; 00 B0 <off> 01 → 3C
00 A4 00 0C 02 3F00 → 9000 ; restore original byte
```

---

## 12. ISIM Files (tc_isim.py)

### TC-ISIM-01 — EF_IMPI_List (4F32): NAI TLV (P2)
```
00 A4 00 0C 02 4F32 / 00 B0 00 00 FF → 9000
assert tag 80; NAI personalised and contains '@'
```

### TC-ISIM-02 — EF_DOMAIN_List (4F33): home domain FQDN (P2)
```
00 A4 00 0C 02 4F33 / 00 B0 00 00 FF → 9000
assert tag 80; ASCII value contains '.', no NUL/space
```

### TC-ISIM-03 — ISIM files updated after IMSI switch (P1)
```
00 A4 00 0C 02 4F32 / 00 B0 00 00 04 → slot size = data[1]+2
00 B0 <size> <size>                  → save IMPI_2
80 C2 00 00 11 D6 0F … 24F420 …      → 9000  (switch to index 2)
00 B0 00 00 32 (4F01)                → extract ISIM AID at offset X+21
00 A4 04 0C <Lc> <ISIM AID>          → 9000
00 A4 00 0C 02 6F02 / 00 B0 00 00 <size> → = IMPI_2
```

---

## Appendix A — Expected per-profile vectors (reference card)

| Index | EF_IMSI (6F07) | EF_ACC | EF_SPN alpha | SMSC in EF_SMSP |
|---|---|---|---|---|
| 1 | `082940809073135906` | `0001` | "IMSI 1" | `07911356039930F0` |
| 2 | `082980106122870000` | `0001` | "IMSI 2" | `07913386098025F0` |
| 3 | `082940700100873000` | `0001` | "IMSI 3" | `07911336078829F2` |

## Appendix B — Status Words

| SW | Meaning |
|---|---|
| 9000 | Success |
| 91 XX | Success, XX-byte proactive command pending (FETCH it) |
| 6282 | End of file before Le — data returned, treat as success |
| 6700 | Wrong length (Lc/Le) |
| 6982 | Security status not satisfied (ADM needed) |
| 6A82 | File / application not found |
| 6A86 / 6B00 | Wrong P1-P2 (offset out of range) |
