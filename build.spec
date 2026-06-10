# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

_icon = 'assets/icon.ico' if Path('assets/icon.ico').exists() else None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('data/*.yaml',              'data'),
        ('security/key_store.enc',   'security'),
        ('reports/templates/*.j2',   'reports/templates'),
        ('config.yaml',              '.'),
    ],
    hiddenimports=[
        'smartcard',
        'smartcard.scard',
        'smartcard.pcsc',
        'smartcard.pcsc.PCSCContext',
        'tests.tc_init',
        'tests.tc_auto_switch',
        'tests.tc_switch_files',
        'tests.tc_round_robin',
        'tests.tc_stk_menu',
        'tests.tc_files',
        'tests.tc_isim',
        'tests.tc_5g',
        'tests.tc_ota',
        'tests.tc_negative',
        'yaml',
        'cryptography',
        'cryptography.fernet',
        'jinja2',
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='MultiIMSI_Tester',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=_icon,
)
