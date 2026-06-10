# Multi-IMSI Test Tool — APDU Sequences per Test Case

## APDU Encoding Reference

All APDUs shown use the format: `CLA INS P1 P2 [Lc Data] [Le]`

| Method | Encoding rule |
|--------|--------------|
| `select_by_path(hex)` | `00 A4 08 0C Lc <path>` |
| `select_by_id(hex)` | `00 A4 00 0C Lc <fid>` |
| `select_by_aid(hex)` | `00 A4 04 0C Lc <aid>` |
| `select_mf()` | `00 A4 00 0C 02 3F 00` |
| `read_binary(offset, len)` | `00 B0 <P1=(offset>>8)&7F> <P2=offset&FF> Le` |
| `update_binary(offset, data)` | `00 D6 <P1> <P2> Lc <data>` |
| `read_record(rec, len)` | `00 B2 <rec_num> 04 Le` |
| `send_status()` | `00 F2 00 00 00` |
| `verify_adm(key_hex)` | `00 20 00 0A 08 <8-byte key>` |
| `send_envelope(data)` | `80 C2 00 00 Lc <data>` |
| `send_location_status(...)` | see envelope breakdown per TC |
| `send_menu_selection(item)` | see envelope breakdown per TC |

---

## Pre-Test Initialization

Before any test, the tool performs the following steps:

1. **Connect to card** — Obtain ATR (Answer To Reset) via the smart-card reader.

2. **Verify ADM key**

   | Step | APDU | Description |
   |------|------|-------------|
   | 1 | `00 20 00 0A 08 <8-byte ADM key>` | Verify ADM (P2=0x0A selects ADM1 key, Lc=08) |

   Expected response: `SW 9000`. Failure (e.g., `SW 6982`, `SW 69C0`) means the ADM key is wrong or the card is blocked — all subsequent file writes will be rejected.

3. **Send TERMINAL PROFILE** (required before any ENVELOPE command)

   | Step | APDU | Description |
   |------|------|-------------|
   | 1 | `80 10 00 00 0C FF FF FF FF FF FF FF FF FF FF FF FF` | TERMINAL PROFILE — declares full proactive SIM support (12 capability bytes all 0xFF) |

   Expected response: `SW 9000`. Without this, any subsequent ENVELOPE (`80 C2 ...`) will return `SW 6985` (Conditions of use not satisfied).

---

## Applet Init

### TC-INIT-01 — Verify applet enable flag activates menu

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT by path — DF Multi-IMSI (7F305F1A) |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config (4F01) |
| 3 | `00 B0 00 00 03` | READ BINARY offset=0 length=3 — read bytes 0-2 |

**Expected response:** `SW 9000`; data byte[0]=`01` (applet enabled), byte[1]=`01` (auto mode on), byte[2] in range `01`–`0A` (active IMSI index).

**Failure meaning:** `SW != 9000` — file not accessible (ADM not verified). Byte[0]`!=01` — applet is disabled, STK menu will not appear. Byte[2] out of range — active index corrupt, switch logic may behave unexpectedly.

---

### TC-INIT-02 — Applet disabled — menu must not appear

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 00 32` | READ BINARY offset=0 length=50 — read full EF_Config |
| 4 | `00 D6 00 00 32 00 <bytes 1-49 original>` | UPDATE BINARY offset=0 — write byte[0]=00 (disable applet), preserve remaining bytes |
| 5 | `00 B0 00 00 01` | READ BINARY offset=0 length=1 — verify byte[0]=00 |
| 6 | `00 D6 00 00 32 <original 50 bytes>` | UPDATE BINARY offset=0 — restore original EF_Config |

**Expected response:** Steps 3, 5 return `SW 9000`; byte[0] after write reads back as `00`. Step 6 `SW 9000` confirms restore.

**Failure meaning:** If step 4 or 6 returns `SW 6982`, ADM was not verified. If byte[0] does not read back as `00`, UPDATE BINARY was silently ignored.

---

### TC-INIT-03 — Verify poll interval registration

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 00 32` | READ BINARY offset=0 length=50 — read full EF_Config |

**Expected response:** `SW 9000`; byte[8] = X (menu text length); byte at offset `9+X` = `1E` (30 seconds).

**Failure meaning:** `SW != 9000` — access denied. Poll interval byte `!= 0x1E` means the applet will poll the network at the wrong rate; REFRESH timing will be off.

---

### TC-INIT-04 — Max IMSI profiles field = 0x0A

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 00 06` | READ BINARY offset=0 length=6 — read bytes 0-5 |

**Expected response:** `SW 9000`; byte[5] = `0A` (max 10 profiles).

**Failure meaning:** Byte[5] `!= 0x0A` — applet will refuse to address IMSI slots beyond that value, causing a switch failure for higher-numbered profiles.

---

### TC-INIT-05 — EF_Config — ISIM / USIM AID fields valid

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 00 32` | READ BINARY offset=0 length=50 |

**Expected response:** `SW 9000`; byte[8] = X; byte at offset `X+21` = ISIM AID length (range `0A`–`10`); byte immediately following ISIM AID data = USIM AID length (range `0A`–`10`); USIM AID first 5 bytes = `A0 00 00 00 87`.

**Failure meaning:** AID length out of range or wrong prefix — `select_by_aid()` calls during IMSI switch will target the wrong applet, causing `SW 6999` or `SW 6A82` (file not found).

---

## Auto Switch

### TC-AUTO-01 — Normal service — PLMN match → switch to priority IMSI

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 07` | SELECT EF_IMSI_List (4F07) |
| 3 | `00 B0 00 00 09` | READ BINARY offset=0 length=9 — read IMSI_1 |
| 4 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 04 24 F0 00 00` | ENVELOPE DOWNLOAD_LOCATION_STATUS — Normal Service, MCC=404 MNC=20 |
| 5 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 6 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 7 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — active IMSI index byte |
| 8 | `00 A4 04 0C 10 A0 00 00 00 87 10 02 FF 33 FF 01 89 00 00 01 00` | SELECT ADF USIM by AID |
| 9 | `00 A4 00 0C 02 6F 07` | SELECT EF_IMSI (6F07) in ADF USIM |
| 10 | `00 B0 00 00 09` | READ BINARY offset=0 length=9 |

**Expected response:** Step 4 `SW 9000`. Step 7 data byte[0] = `01`. Step 10 `SW 9000`; data equals IMSI_1 read in step 3.

**Failure meaning:** Step 4 `SW 6985` — TERMINAL PROFILE not sent. Step 7 byte `!= 01` — PLMN lookup failed, applet did not find MCC=404/MNC=20 in EF_MCC_Mapping_List. Step 10 mismatch — EF_IMSI was not updated (no REFRESH issued or REFRESH failed).

---

### TC-AUTO-02 — Normal service — PLMN already active, no switch

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — record current active index |
| 4 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 04 24 F0 00 00` | ENVELOPE — Normal Service MCC=404 MNC=20 (same PLMN as current) |
| 5 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 6 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 7 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — verify index unchanged |

**Expected response:** Step 4 `SW 9000`. Step 7 byte[0] = same value read in step 3.

**Failure meaning:** Index changed — applet performed an unnecessary switch on an already-active PLMN, causing spurious REFRESH and registration delay.

---

### TC-AUTO-03 — Limited service — PLI LOCI issued, preferred IMSI selected

| Step | APDU | Description |
|------|------|-------------|
| 1 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 01 9B 06 00 00 24 04 F2 00 00` | ENVELOPE DOWNLOAD_LOCATION_STATUS — Limited Service, MCC=424 MNC=02 |
| 2 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 3 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 4 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — active IMSI index |

**Expected response:** Step 1 `SW 9000`. Step 4 byte[0] = `02`.

**Failure meaning:** Byte `!= 02` — Limited-service PLMN was not matched to the UAE preferred profile; the card will attempt registration with the wrong IMSI in limited-service areas.

---

### TC-AUTO-04 — PLMN not in MCC list — switch to default IMSI index

| Step | APDU | Description |
|------|------|-------------|
| 1 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 99 09 F1 00 00` | ENVELOPE — Normal Service, MCC=999 MNC=01 (unknown PLMN) |
| 2 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 3 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 4 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 |

**Expected response:** Step 1 `SW 9000`. Step 4 byte[0] = `01` (wildcard/default profile).

**Failure meaning:** Byte `!= 01` — the applet has no wildcard entry in EF_MCC_Mapping_List or the fallback logic is broken; unknown networks will get an arbitrary IMSI.

---

### TC-AUTO-05 — Automatic mode disabled — no IMSI switch on location event

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 D6 00 01 01 00` | UPDATE BINARY offset=1 data=`00` — disable automatic mode |
| 4 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — record current active index |
| 5 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 04 24 F0 00 00` | ENVELOPE — Normal Service MCC=404 MNC=20 |
| 6 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 7 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 8 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — verify no change |
| 9 | `00 D6 00 01 01 01` | UPDATE BINARY offset=1 data=`01` — re-enable automatic mode |

**Expected response:** Step 8 byte[0] = same as step 4 (no switch occurred). Steps 3 and 9 `SW 9000`.

**Failure meaning:** Index changed — automatic-mode guard byte is not being checked by the applet before processing location events.

---

## Round Robin

### TC-RR-01 — Round robin enabled — cycles to next index on network loss

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 06 01` | READ BINARY offset=6 length=1 — Round Robin enable byte |
| 4 | `80 C2 00 00 09 D6 07 82 02 83 81 99 01 02` | ENVELOPE — No Service (service_type=2) |
| 5 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — index after 1st event |
| 6 | `80 C2 00 00 09 D6 07 82 02 83 81 99 01 02` | ENVELOPE — No Service (2nd event) |
| 7 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 8 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 9 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — index after 2nd event |

**Expected response:** Step 3 byte[0] = `01` (RR enabled). Step 9 byte[0] differs from step 5 byte[0] (index cycled).

**Failure meaning:** Step 3 byte `!= 01` — round robin is off, the remaining steps become invalid. Index unchanged — the cycle logic is not triggered by No-Service events.

---

### TC-RR-02 — Round robin disabled — no cycling on network loss

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 D6 00 06 01 00` | UPDATE BINARY offset=6 data=`00` — disable Round Robin |
| 4 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — record current active index |
| 5 | `80 C2 00 00 09 D6 07 82 02 83 81 99 01 02` | ENVELOPE — No Service |
| 6 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 7 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 8 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — verify no change |
| 9 | `00 D6 00 06 01 01` | UPDATE BINARY offset=6 data=`01` — re-enable Round Robin |

**Expected response:** Step 8 byte[0] = same as step 4. Steps 3 and 9 `SW 9000`.

**Failure meaning:** Index changed while RR is disabled — the RR guard byte is not respected by the applet.

---

### TC-RR-03 — Periodic switching via STATUS command counter

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 03 02` | READ BINARY offset=3 length=2 — periodic switch enable + counter bytes |
| 4–(3+N-1) | `00 F2 00 00 00` | STATUS command × (counter−1) — should not trigger switch |
| 3+N | `00 F2 00 00 00` | Final STATUS command — should trigger PLI LOCI switch |

Where N = counter value read from byte[1] of step 3 result.

**Expected response:** Step 3 byte[0] = `01` (periodic switching enabled). All STATUS commands return `SW 9000` or `SW 91XX`. The Nth STATUS triggers the REFRESH sequence.

**Failure meaning:** Step 3 byte `!= 01` — periodic switching is off. STATUS commands never triggering a switch — the internal STATUS counter is not decrementing.

---

### TC-RR-04 — Fallback mode — return to priority IMSI after counter expires

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 00 32` | READ BINARY offset=0 length=50 — read fallback mode (byte X+14) and counter (byte X+13) |
| 4 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 24 04 F2 00 00` | ENVELOPE — Normal Service MCC=424 MNC=02 → switch to index 2 |
| 5 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — verify index=02 |
| 6–(5+K) | `00 F2 00 00 00` | STATUS command × K (fallback counter value from step 3) |
| 6+K | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 7+K | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 8+K | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — verify reverted to index 01 |

**Expected response:** Step 5 byte[0] = `02`. Step 8+K byte[0] = `01` (priority index restored). Byte at offset `X+14` in step 3 = `01` (fallback mode enabled).

**Failure meaning:** Fallback mode byte `!= 01` — test precondition fails. Index still `02` after K STATUS commands — fallback counter is not decrementing or the restore logic is broken.

---

## STK Menu

### TC-STK-01 — STK 'Next IMSI' menu item

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — record index before |
| 4 | `80 C2 00 00 0C D3 0A 82 02 01 82 90 01 01 91 01 00` | ENVELOPE MENU SELECTION item=01 (Next IMSI), no help |
| 5 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 6 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 7 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — index after Next IMSI |

**Envelope breakdown (step 4):** Tag `D3` = MENU SELECTION; inner TLV: `82 02 01 82` device identities (keypad→card), `90 01 01` item identifier=01, `91 01 00` help request=false.

**Expected response:** Step 4 `SW 9000`. Step 7 byte[0] differs from step 3 byte[0] (incremented, with wrap 10→1 allowed).

**Failure meaning:** `SW 6985` on step 4 — TERMINAL PROFILE not sent. Index unchanged — applet did not handle MENU SELECTION or item 01 is not mapped to "Next IMSI".

---

### TC-STK-02 — STK 'Priority IMSI' menu item

| Step | APDU | Description |
|------|------|-------------|
| 1 | `80 C2 00 00 0C D3 0A 82 02 01 82 90 01 02 91 01 00` | ENVELOPE MENU SELECTION item=02 (Priority IMSI) |
| 2 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 3 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 4 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 |

**Expected response:** Step 1 `SW 9000`. Step 4 byte[0] = `01`.

**Failure meaning:** Index `!= 01` — item 02 is not mapped to the priority profile or the priority index is misconfigured.

---

### TC-STK-03 — STK 'Lock IMSI' menu item

| Step | APDU | Description |
|------|------|-------------|
| 1 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 24 04 F2 00 00` | ENVELOPE — Normal Service MCC=424 MNC=02 → switch to index 2 |
| 2 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 3 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 4 | `00 B0 00 02 01` | READ BINARY — verify index=02 |
| 5 | `80 C2 00 00 0C D3 0A 82 02 01 82 90 01 03 91 01 00` | ENVELOPE MENU SELECTION item=03 (Lock IMSI) |
| 6 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 04 24 F0 00 00` | ENVELOPE — Normal Service MCC=404 MNC=20 (would normally switch to index 1) |
| 7 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 8 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 9 | `00 B0 00 02 01` | READ BINARY — verify index still locked at 02 |

**Expected response:** Step 4 byte[0] = `02`. Steps 5 and 6 `SW 9000`. Step 9 byte[0] = `02` (locked, no switch despite location event).

**Failure meaning:** Index changed to `01` in step 9 — lock flag is not being set by item 03, or the lock check is missing in the location event handler.

---

### TC-STK-04 — STK 'Automatic Mode' toggle

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 01 01` | READ BINARY offset=1 length=1 — auto mode byte before toggle |
| 4 | `80 C2 00 00 0C D3 0A 82 02 01 82 90 01 04 91 01 00` | ENVELOPE MENU SELECTION item=04 (Automatic Mode toggle) |
| 5 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 6 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 7 | `00 B0 00 01 01` | READ BINARY offset=1 length=1 — auto mode byte after toggle |
| 8 *(optional)* | `80 C2 00 00 0C D3 0A 82 02 01 82 90 01 04 91 01 00` | ENVELOPE MENU SELECTION item=04 — restore original state |

**Expected response:** Step 4 `SW 9000`. Step 7 byte[0] = `01` if step 3 was `00`, or `00` if step 3 was `01`.

**Failure meaning:** Byte unchanged — item 04 is not toggling the auto-mode flag in EF_Config. Auto-switch tests run after this with the wrong mode.

---

## Switch Files

### TC-SWITCH-01 — IMSI file correctly updated after switch

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 D6 00 02 01 01` | UPDATE BINARY offset=2 data=`01` — force active index to 01 |
| 4 | `00 A4 00 0C 02 4F 07` | SELECT EF_IMSI_List (4F07) |
| 5 | `00 B0 00 09 09` | READ BINARY offset=9 length=9 — read IMSI_2 |
| 6 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 24 04 F2 00 00` | ENVELOPE — Normal Service MCC=424 MNC=02 → trigger switch to index 2 |
| 7 | `00 A4 04 0C 10 A0 00 00 00 87 10 02 FF 33 FF 01 89 00 00 01 00` | SELECT ADF USIM |
| 8 | `00 A4 00 0C 02 6F 07` | SELECT EF_IMSI (6F07) |
| 9 | `00 B0 00 00 09` | READ BINARY offset=0 length=9 — read active IMSI |

**Expected response:** Steps 3, 5, 6, 9 all `SW 9000`. Step 9 data = step 5 data (IMSI_2).

**Failure meaning:** Mismatch — the applet did not copy the IMSI_2 entry from the list EF into the live EF_IMSI, or the REFRESH was not issued.

---

### TC-SWITCH-02 — SPN updated after switch

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 46` | SELECT EF_SPN_List (4F46) |
| 3 | `00 B0 00 11 11` | READ BINARY offset=17 length=17 — read SPN_2 |
| 4 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 24 04 F2 00 00` | ENVELOPE — Normal Service MCC=424 MNC=02 |
| 5 | `00 A4 04 0C 10 A0 00 00 00 87 10 02 FF 33 FF 01 89 00 00 01 00` | SELECT ADF USIM |
| 6 | `00 A4 00 0C 02 6F 46` | SELECT EF_SPN (6F46) |
| 7 | `00 B0 00 00 11` | READ BINARY offset=0 length=17 |

**Expected response:** Step 7 data = step 3 data (SPN_2).

**Failure meaning:** Mismatch — EF_SPN was not updated; the network display name will remain from the previous profile.

---

### TC-SWITCH-03 — ACC updated after switch

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 78` | SELECT EF_ACC_List (4F78) |
| 3 | `00 B0 00 02 02` | READ BINARY offset=2 length=2 — read ACC_2 |
| 4 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 24 04 F2 00 00` | ENVELOPE — Normal Service MCC=424 MNC=02 |
| 5 | `00 A4 04 0C 10 A0 00 00 00 87 10 02 FF 33 FF 01 89 00 00 01 00` | SELECT ADF USIM |
| 6 | `00 A4 00 0C 02 6F 78` | SELECT EF_ACC (6F78) |
| 7 | `00 B0 00 00 02` | READ BINARY offset=0 length=2 |

**Expected response:** Step 7 data = step 3 data (ACC_2).

**Failure meaning:** Wrong ACC after switch — emergency call class access bits will be incorrect for the active profile.

---

### TC-SWITCH-04 — SMSP updated after switch

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 42` | SELECT EF_SMSP_List (4F42) |
| 3 | `00 B0 00 1C 1C` | READ BINARY offset=28 length=28 — read SMSP_2 |
| 4 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 24 04 F2 00 00` | ENVELOPE — Normal Service MCC=424 MNC=02 |
| 5 | `00 A4 04 0C 10 A0 00 00 00 87 10 02 FF 33 FF 01 89 00 00 01 00` | SELECT ADF USIM |
| 6 | `00 A4 00 0C 02 6F 42` | SELECT EF_SMSP (6F42) |
| 7 | `00 B2 01 04 1C` | READ RECORD record=1 mode=04 (current) length=28 |

**Expected response:** Step 7 data = step 3 data (SMSP_2).

**Failure meaning:** SMS centre number from profile 1 will be active while roaming under profile 2.

---

### TC-SWITCH-05 — PLMNwACT / OPLMNwACT / HPLMNwACT updated

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 60` | SELECT EF_PLMNwACT_List (4F60) |
| 3 | `00 B0 00 28 28` | READ BINARY offset=40 length=40 — read PLMNwACT_2 |
| 4 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 24 04 F2 00 00` | ENVELOPE — Normal Service MCC=424 MNC=02 |
| 5 | `00 A4 04 0C 10 A0 00 00 00 87 10 02 FF 33 FF 01 89 00 00 01 00` | SELECT ADF USIM |
| 6 | `00 A4 00 0C 02 6F 60` | SELECT EF_PLMNwACT (6F60) |
| 7 | `00 B0 00 00 28` | READ BINARY offset=0 length=40 |

**Expected response:** Step 7 data = step 3 data (PLMNwACT_2).

**Failure meaning:** Preferred network list not updated — handset may attempt registration on wrong RATs for the new profile.

---

### TC-SWITCH-06 — FPLMN cleared before REFRESH

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 04 0C 10 A0 00 00 00 87 10 02 FF 33 FF 01 89 00 00 01 00` | SELECT ADF USIM |
| 2 | `00 A4 00 0C 02 6F 7B` | SELECT EF_FPLMN (6F7B) |
| 3 | `00 D6 00 00 03 24 F2 99` | UPDATE BINARY offset=0 data=`24 F2 99` — write dummy FPLMN entry |
| 4 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 24 04 F2 00 00` | ENVELOPE — Normal Service MCC=424 MNC=02 → trigger IMSI switch |
| 5 | `00 A4 04 0C 10 A0 00 00 00 87 10 02 FF 33 FF 01 89 00 00 01 00` | SELECT ADF USIM |
| 6 | `00 A4 00 0C 02 6F 7B` | SELECT EF_FPLMN |
| 7 | `00 B0 00 00 0C` | READ BINARY offset=0 length=12 — verify all FF |

**Expected response:** Step 7 `SW 9000`; data = `FF FF FF FF FF FF FF FF FF FF FF FF`.

**Failure meaning:** Non-FF bytes after switch — the old FPLMN list carried over, causing the device to barr known-good cells of the new profile's network.

---

### TC-SWITCH-07 — Location files reset to default value before REFRESH

| Step | APDU | Description |
|------|------|-------------|
| 1 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 04 24 F0 00 00` | ENVELOPE — Normal Service MCC=404 MNC=20 → trigger IMSI switch |
| 2 | `00 A4 04 0C 10 A0 00 00 00 87 10 02 FF 33 FF 01 89 00 00 01 00` | SELECT ADF USIM |
| 3 | `00 A4 00 0C 02 6F 7E` | SELECT EF_LOCI (6F7E) |
| 4 | `00 B0 00 00 0B` | READ BINARY offset=0 length=11 |
| 5 | `00 A4 00 0C 02 6F E3` | SELECT EF_EPSLOCI (6FE3) |
| 6 | `00 B0 00 00 12` | READ BINARY offset=0 length=18 |

**Expected response:** Step 4 `SW 9000`; last byte (update status) ∈ {`00`, `01`}. Step 6 `SW 9000`.

**Failure meaning:** Update status byte `> 01` — stale location context from previous profile will cause the ME to perform unnecessary location update procedures after the switch.

---

### TC-SWITCH-08 — REFRESH command issued at end of switch

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 00 32` | READ BINARY offset=0 length=50 — read REFRESH type from offset X+8 |
| 4 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 24 04 F2 00 00` | ENVELOPE — Normal Service MCC=424 MNC=02 → switch + REFRESH |
| 5 | `00 A4 00 0C 02 3F 00` | SELECT MF — verify card still responsive after REFRESH |

**Expected response:** Step 4 `SW 9000`. Step 5 `SW 9000`.

**Failure meaning:** Step 5 failure (`SW 6F00`, `SW 6999` or timeout) — the REFRESH left the card in an inconsistent state or the transport layer was not re-initialised correctly after the SIM reset.

---

## File Validation

### TC-FILE-01 — EF_IMSI_List (4F07) — size and BCD encoding

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 07` | SELECT EF_IMSI_List |
| 3 | `00 B0 00 00 5A` | READ BINARY offset=0 length=90 |

**Expected response:** `SW 9000`; 90 bytes returned; bytes 0-8 `!= FF×9`; byte[0] ∈ {`07`, `08`} (IMSI BCD length).

**Failure meaning:** Wrong size — the card was not personalised correctly. All-FF IMSI_1 — no IMSI loaded in slot 1. Invalid length byte — ME will reject the EF_IMSI value as malformed.

---

### TC-FILE-02 — EF_MCC_Mapping_List (4F03) — PLMN encoding and wildcard

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 03` | SELECT EF_MCC_Mapping_List (4F03) |
| 3 | `00 B0 00 00 FF` | READ BINARY offset=0 length=255 — first chunk |
| 4 | `00 B0 00 FF F1` | READ BINARY offset=255 length=241 — second chunk (total 500 bytes) |

**Expected response:** Both reads `SW 9000`; combined 500 bytes; at least one valid entry (index byte 01–0A); at least one wildcard entry (nibble `D` in the PLMN bytes).

**Failure meaning:** No valid entries — the mapping table is empty; every location event will select the default index. No wildcard — unknown PLMNs will not fall back to a sensible default.

---

### TC-FILE-03 — EF_SPN_List (4F46) — 17-byte records

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 46` | SELECT EF_SPN_List |
| 3 | `00 B0 00 00 AA` | READ BINARY offset=0 length=170 |

**Expected response:** `SW 9000`; 170 bytes; bytes 0-16 `!= FF×17`; byte[0] ∈ {`00`, `01`} (display condition).

**Failure meaning:** All-FF SPN_1 — no service provider name loaded. Invalid display condition — handset may not display the SPN or may display it in incorrect circumstances.

---

### TC-FILE-04 — EF_ACC_List (4F78) — 2 bytes per profile

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 78` | SELECT EF_ACC_List |
| 3 | `00 B0 00 00 14` | READ BINARY offset=0 length=20 |

**Expected response:** `SW 9000`; 20 bytes.

**Failure meaning:** Wrong size — personalization did not write ACC data for all 10 slots.

---

### TC-FILE-05 — EF_AD_USIM_List (6FAD) — 4-byte AD records

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 6F AD` | SELECT EF_AD_USIM_List (6FAD) |
| 3 | `00 B0 00 00 28` | READ BINARY offset=0 length=40 |

**Expected response:** `SW 9000`; 40 bytes; byte[2] ∈ {`02`, `03`} (MNC digit length for profile 1).

**Failure meaning:** Wrong MNC length byte — ME will parse IMSI digits incorrectly, extracting a wrong MNC and thus misidentifying the HPLMN.

---

### TC-FILE-06 — EF_PLMNwACT_List (4F60) — size = 10 × EF_PLMNwACT size

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 04 0C 10 A0 00 00 00 87 10 02 FF 33 FF 01 89 00 00 01 00` | SELECT ADF USIM |
| 2 | `00 A4 00 0C 02 6F 60` | SELECT EF_PLMNwACT in ADF USIM |
| 3 | `00 B0 00 00 28` | READ BINARY offset=0 length=40 — determine per-profile size |
| 4 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 5 | `00 A4 00 0C 02 4F 60` | SELECT EF_PLMNwACT_List (4F60) |
| 6 | `00 B0 00 00 EF` | READ BINARY offset=0 length=239 — first portion of list |

**Expected response:** Step 3 `SW 9000`; step 6 `SW 9000`; first 5-byte entry has valid PLMN (bytes 0-2) and ACT bitmap (bytes 3-4).

**Failure meaning:** Cannot read USIM EF_PLMNwACT — AID wrong in EF_Config. List size mismatch — profiles may be truncated or over-allocated.

---

### TC-FILE-07 — EF_FPLMN_List (4F7B) — 120 bytes, 10 profiles × 12 bytes

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 7B` | SELECT EF_FPLMN_List (4F7B) |
| 3 | `00 B0 00 00 78` | READ BINARY offset=0 length=120 |

**Expected response:** `SW 9000`; 120 bytes; structure validates as 10 blocks × 12 bytes (4 × 3-byte FPLMN entries per profile).

**Failure meaning:** Wrong size — FPLMN slots for some profiles will overlap on switch, causing random FPLMN entries to be applied.

---

## ISIM Files

### TC-ISIM-01 — EF_IMPI_List (4F32) — IMS private identity TLV encoding

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 32` | SELECT EF_IMPI_List (4F32) |
| 3 | `00 B0 00 00 FF` | READ BINARY offset=0 length=255 |

**Expected response:** `SW 9000`; byte[0] = `80` (TLV tag); byte[1] = length L; bytes 2..(2+L-1) contain `@`; not all-FF.

**Failure meaning:** Wrong tag — NAI is stored without the required TLV wrapper; ADF ISIM EF_IMPI will not be parseable. Missing `@` — NAI format invalid for IMS registration.

---

### TC-ISIM-02 — EF_DOMAIN_List (4F33) — home network domain FQDN

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 33` | SELECT EF_DOMAIN_List (4F33) |
| 3 | `00 B0 00 00 FF` | READ BINARY offset=0 length=255 |

**Expected response:** `SW 9000`; byte[0] = `80`; decoded ASCII string contains `.` and has no null or space; valid FQDN format.

**Failure meaning:** Invalid FQDN — IMS registration will fail as the P-CSCF domain cannot be derived from EF_DOMAIN.

---

### TC-ISIM-03 — ISIM files updated after IMSI switch

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 32` | SELECT EF_IMPI_List |
| 3 | `00 B0 00 00 04` | READ BINARY offset=0 length=4 — read IMPI_1 TLV header to determine slot size |
| 4 | `00 B0 00 <slot_size> <slot_size>` | READ BINARY offset=slot_size length=slot_size — read IMPI_2 |
| 5 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 24 04 F2 00 00` | ENVELOPE — Normal Service MCC=424 MNC=02 → switch to index 2 |
| 6 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 7 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 8 | `00 B0 00 00 32` | READ BINARY offset=0 length=50 — locate ISIM AID at offset X+21 |
| 9 | `00 A4 04 0C <Lc> <ISIM AID bytes>` | SELECT ADF ISIM by AID (AID read from EF_Config) |
| 10 | `00 A4 00 0C 02 6F 02` | SELECT EF_IMPI (6F02) in ADF ISIM |
| 11 | `00 B0 00 00 <slot_size>` | READ BINARY offset=0 length=slot_size |

**Expected response:** Step 11 data = step 4 data (IMPI_2).

**Failure meaning:** Mismatch — the applet updated EF_IMSI (USIM) but not EF_IMPI (ISIM); VoLTE/IMS calls will use the wrong private identity after the switch.

---

## 5G Files

### TC-5G-01 — EF_5GS3GPPNSC_List (4F53) — NAS security context ASN.1

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 53` | SELECT EF_5GS3GPPNSC_List (4F53) |
| 3 | `00 B0 00 00 FF` | READ BINARY offset=0 length=255 |

**Expected response:** `SW 9000`; byte[0] = `A0` (ASN.1 SEQUENCE); inner TLV contains mandatory tags `80` (ngKSI), `81` (keys), `82` (UL count), `83` (DL count).

**Failure meaning:** Wrong outer tag or missing inner tags — 5G NAS security context is malformed; the ME will reject the cached security context and force a full authentication.

---

### TC-5G-02 — EF_UAC_AIC_List (4F56) — 4 bytes per profile

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 56` | SELECT EF_UAC_AIC_List (4F56) |
| 3 | `00 B0 00 00 28` | READ BINARY offset=0 length=40 |

**Expected response:** `SW 9000`; 40 bytes; bytes 0-3 `!= FF FF FF FF`.

**Failure meaning:** All-FF UAC_AIC_1 — unified access control / access identity configuration not personalised; 5G slice selection may fail.

---

### TC-5G-03 — EF_SUCI_Calc_Info_List (4F57) — ECIES public key 32 bytes

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 57` | SELECT EF_SUCI_Calc_Info_List (4F57) |
| 3 | `00 B0 00 00 FF` | READ BINARY offset=0 length=255 |

**Expected response:** `SW 9000`; byte[0] = `A0`; inner `A1` sub-tag present; inner tag `81` (key bytes) length = `20` (32 decimal).

**Failure meaning:** Wrong tag or key length — SUCI computation using ECIES will fail; IMSI privacy on 5G SA will not work.

---

### TC-5G-04 — 5G files updated after IMSI switch

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 56` | SELECT EF_UAC_AIC_List |
| 3 | `00 B0 00 04 04` | READ BINARY offset=4 length=4 — read UAC_AIC_2 |
| 4 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 24 04 F2 00 00` | ENVELOPE — Normal Service MCC=424 MNC=02 → switch to index 2 |
| 5 | `00 A4 04 0C 10 A0 00 00 00 87 10 02 FF 33 FF 01 89 00 00 01 00` | SELECT ADF USIM |
| 6 | `00 A4 00 0C 02 4F 56` | SELECT EF_UAC_AIC (4F56) in ADF USIM |
| 7 | `00 B0 00 00 04` | READ BINARY offset=0 length=4 |

**Expected response:** Step 7 data = step 3 data (UAC_AIC_2).

**Failure meaning:** Mismatch — 5G access identity class configuration not updated; slice selection and emergency access will use profile 1's values while on profile 2.

---

### TC-5G-05 — EF_Routing_Indicator_List (4F5A) — BCD format check

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 5A` | SELECT EF_Routing_Indicator_List (4F5A) |
| 3 | `00 B0 00 00 28` | READ BINARY offset=0 length=40 |

**Expected response:** `SW 9000`; 40 bytes; bytes 0-3 not all-FF; every nibble of bytes 0-3 is in range `0`–`9` or `F` (valid BCD / padding).

**Failure meaning:** Invalid BCD nibbles — the routing indicator cannot be decoded; 5G SUCI computation will produce a malformed SUPI concealment result.

---

## OTA

### TC-OTA-01 — Remote update of EF_IMSI_List triggers config reload + REFRESH

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 07` | SELECT EF_IMSI_List |
| 3 | `00 B0 00 12 09` | READ BINARY offset=18 length=9 — read current IMSI_3 (slot 3) |
| 4 | `00 D6 00 12 09 08 39 94 10 40 00 00 00 F0` | UPDATE BINARY offset=18 data=`08 39 94 10 40 00 00 00 F0` — write new IMSI_3 |
| 5 | `00 B0 00 12 09` | READ BINARY offset=18 length=9 — verify write |
| 6 | `00 A4 00 0C 02 3F 00` | SELECT MF — card responsiveness check after internal REFRESH |
| 7 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 8 | `00 A4 00 0C 02 4F 07` | SELECT EF_IMSI_List |
| 9 | `00 D6 00 12 09 <original IMSI_3>` | UPDATE BINARY — restore original IMSI_3 |

**Expected response:** Step 4 `SW 9000`. Step 5 data = `08 39 94 10 40 00 00 00 F0`. Step 6 `SW 9000`.

**Failure meaning:** Step 4 failure — OTA writes are not authorised at the required security level. Step 6 failure — the internal REFRESH after EF_IMSI_List update crashed the card.

---

### TC-OTA-02 — External file update of EF_Config triggers applet re-init

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 00 32` | READ BINARY offset=0 length=50 — read poll offset from byte 8 (X) |
| 4 | `00 D6 00 <9+X> 01 3C` | UPDATE BINARY offset=`9+X` data=`3C` — set poll interval to 60 s |
| 5 | `00 B0 00 <9+X> 01` | READ BINARY — verify poll byte = `3C` |
| 6 | `00 A4 00 0C 02 3F 00` | SELECT MF — card responsiveness check |
| 7 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 8 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 9 | `00 D6 00 <9+X> 01 <original_byte>` | UPDATE BINARY — restore original poll interval |

Note: P1/P2 for offset `9+X` are computed as P1=`(offset>>8)&0x7F`, P2=`offset&0xFF`. For typical X≤30 this fits in P2 only (P1=`00`).

**Expected response:** Step 4 `SW 9000`. Step 5 byte[0] = `3C`. Step 6 `SW 9000`.

**Failure meaning:** Step 4 failure — EF_Config write access not granted. Step 6 failure — the applet crashed or entered error state after detecting an EF_Config change.

---

## Negative Tests

### TC-NEG-01 — Read EF_Config without ADM authentication → 6982

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 00 01` | READ BINARY offset=0 length=1 — without prior ADM verification |

**Expected response:** `SW 6982` (Security status not satisfied).

**Failure meaning:** `SW 9000` returned — EF_Config has no read-access control; any application can read sensitive IMSI switching configuration without authentication.

---

### TC-NEG-02 — Write EF_IMSI_List with wrong Lc → 6700

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 07` | SELECT EF_IMSI_List |
| 3 | `00 D6 00 00 08 08 30 99 41 04 00 00 00` | UPDATE BINARY offset=0 data=8 bytes (wrong — IMSI slot requires 9) |

**Expected response:** `SW 6700` (Wrong length).

**Failure meaning:** `SW 9000` returned — partial writes are accepted; an interrupted OTA update could corrupt an IMSI slot with a truncated value.

---

### TC-NEG-03 — Write IMSI index out of range (0x0B) — card remains operational

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 3 | `00 B0 00 00 32` | READ BINARY — save original EF_Config |
| 4 | `00 D6 00 00 32 <original with byte[2]=0B>` | UPDATE BINARY — write out-of-range active index `0B` |
| 5 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 04 24 F0 00 00` | ENVELOPE — Normal Service MCC=404 MNC=20 |
| 6 | `00 A4 00 0C 02 3F 00` | SELECT MF — verify card still operational |
| 7 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 8 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 9 | `00 D6 00 00 32 <original bytes>` | UPDATE BINARY — restore original EF_Config |

**Expected response:** Steps 4 and 5 may return `SW 9000` (card-level write accepted). Step 6 `SW 9000` (card operational).

**Failure meaning:** Step 6 failure — applet threw an unhandled exception on an out-of-range index, leaving the card non-responsive until cold reset.

---

### TC-NEG-04 — Read beyond EOF of EF_MCC_Mapping_List → 6B00

| Step | APDU | Description |
|------|------|-------------|
| 1 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 2 | `00 A4 00 0C 02 4F 03` | SELECT EF_MCC_Mapping_List (4F03, 500 bytes) |
| 3 | `00 B0 01 F8 04` | READ BINARY P1=`01` P2=`F8` (offset=504) length=4 — beyond EOF |

**Expected response:** `SW 6B00` (Incorrect parameters in P1/P2), or `SW 6700`, or `SW 6A86`.

**Failure meaning:** `SW 9000` with data returned — the card wraps around and returns bytes from the beginning of the file; the switch logic might read a wrong PLMN mapping if it ever sends an out-of-bounds READ BINARY.

---

### TC-NEG-05 — Cold reset during IMSI switch — consistency check

| Step | APDU | Description |
|------|------|-------------|
| 1 | `80 C2 00 00 12 D6 10 82 02 83 81 99 01 00 9B 06 00 00 24 04 F2 00 00` | ENVELOPE — Normal Service MCC=424 MNC=02 → trigger IMSI switch |
| 2 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 3 | `00 A4 00 0C 02 4F 01` | SELECT EF_Config |
| 4 | `00 B0 00 02 01` | READ BINARY offset=2 length=1 — get active index |
| 5 | `00 A4 04 0C 10 A0 00 00 00 87 10 02 FF 33 FF 01 89 00 00 01 00` | SELECT ADF USIM |
| 6 | `00 A4 00 0C 02 6F 07` | SELECT EF_IMSI (6F07) |
| 7 | `00 B0 00 00 09` | READ BINARY — current active IMSI |
| 8 | `00 A4 08 0C 04 7F 30 5F 1A` | SELECT DF Multi-IMSI |
| 9 | `00 A4 00 0C 02 4F 07` | SELECT EF_IMSI_List |
| 10 | `00 B0 00 <(active_idx-1)*9> 09` | READ BINARY — IMSI from list at slot = active_idx |

Where P1/P2 offset for step 10 = `(active_idx - 1) × 9`. For index 2: offset = 9 (`P1=00 P2=09`).

**Expected response:** Step 7 data = step 10 data (EF_IMSI consistent with EF_IMSI_List slot).

**Failure meaning:** Mismatch — a previous partial switch left EF_IMSI pointing to a different profile than what EF_Config byte 2 indicates; the ME is using a different IMSI than the applet believes, causing subscription conflicts.
