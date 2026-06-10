"""
Test vector constants derived from Variables.txt.
Replace with real values for your specific card personalisation.
"""

# ADM key in hex (from Variables.txt: 3733323339313637)
ADM_KEY_HEX = "3733323339313637"

# IMSI slots (9-byte BCD-encoded, from EF_IMSI_List)
IMSI_ROAMING  = bytes.fromhex("082940809073135906")  # index 01
IMSI_HOME_01  = bytes.fromhex("082980106122870000")  # index 02
IMSI_HOME_02  = bytes.fromhex("082940700100873000")  # index 03

IMSI_BY_INDEX = {
    1: IMSI_ROAMING,
    2: IMSI_HOME_01,
    3: IMSI_HOME_02,
}

# SMSP records (43 bytes = 0x2B, linear-fixed EF 6F42)
SMSC_ROAMING = bytes.fromhex(
    "534D5343FFFFFFFFFFFFFFFFFFFFFFE1FFFFFFFFFFFFFFFFFFFFFFFF"
    "07911356039930F0FFFFFFFF0000A9"
)
SMSC_HOME_01 = bytes.fromhex(
    "534D5343FFFFFFFFFFFFFFFFFFFFFFE1FFFFFFFFFFFFFFFFFFFFFFFF"
    "07913386098025F0FFFFFFFF0000A9"
)
SMSC_HOME_02 = bytes.fromhex(
    "534D5343FFFFFFFFFFFFFFFFFFFFFFE1FFFFFFFFFFFFFFFFFFFFFFFF"
    "07911336078829F2FFFFFFFF0000A9"
)

SMSC_BY_INDEX = {
    1: SMSC_ROAMING,
    2: SMSC_HOME_01,
    3: SMSC_HOME_02,
}

# SPN records (17 bytes = 0x11, EF 6F46)
SPN_ROAMING = bytes.fromhex("00494D53492031FFFFFFFFFFFFFFFFFFFF")
SPN_HOME_01 = bytes.fromhex("00494D53492032FFFFFFFFFFFFFFFFFFFF")
SPN_HOME_02 = bytes.fromhex("00494D53492033FFFFFFFFFFFFFFFFFFFF")

SPN_BY_INDEX = {
    1: SPN_ROAMING,
    2: SPN_HOME_01,
    3: SPN_HOME_02,
}

# ACC records (2 bytes, EF 6F78)
ACC_ROAMING = bytes.fromhex("0001")
ACC_HOME_01 = bytes.fromhex("0001")
ACC_HOME_02 = bytes.fromhex("0001")

ACC_BY_INDEX = {
    1: ACC_ROAMING,
    2: ACC_HOME_01,
    3: ACC_HOME_02,
}

# Location switching config (from Variables.txt)
# MCC_MNC = 02F466 (used in ENVELOPE LOCATION STATUS)
MCC_MNC_HEX    = "02F466"
MCC_IMSI_INDEX = 3      # IMSI index mapped to this PLMN
PRIO_IMSI      = 1      # Priority IMSI index

# EF_Config full personalisation data (from %4F01 in Variables.txt)
EF_CONFIG_DATA = bytes.fromhex(
    "01010301040A01FF10526F616D696E672053657276696365"
    "1EFFFFFF1401FF"
    "040101010010A0000000871002FFFFFFFF8901030000"
)

# Number of personalised IMSI profiles on this card
MAX_PROFILES = 3

# DF navigation path (step-by-step, matching PCOM)
DF_7F30 = "7F30"
DF_5F1A = "5F1A"

# Standard EF file IDs under DF GSM (7F20)
EF_IMSI  = "6F07"
EF_ACC   = "6F78"
EF_SPN   = "6F46"
EF_SMSP  = "6F42"
DF_GSM   = "7F20"
DF_TELECOM = "7F10"

# Multi-IMSI proprietary EFs
EF_CONFIG    = "4F01"
EF_IMSI_LIST = "4F07"
