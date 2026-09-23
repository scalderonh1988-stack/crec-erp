# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

block_cipher = None

datas = [
    ('app.py', '.'),
    ('.streamlit', '.streamlit'),
    ('modulos', 'modulos'),
    ('permisos_negocios.json', '.'),
]

datas += collect_data_files('streamlit')
datas += collect_data_files('altair')
datas += copy_metadata('streamlit')

hiddenimports = [
    'streamlit',
    'streamlit.web.cli',
    'streamlit.runtime.scriptrunner.magic_funcs',
    'supabase',
    'postgrest',
    'gotrue',
    'realtime',
    'storage3',
    'httpx',
    'pandas',
    'openpyxl',
    'xlsxwriter',
    'requests',
    'sqlite3',
    'json',
    'conexion',
    'db_local',
    'app_local',
    'actualizar_precios_stock',
] + collect_submodules('modulos') + collect_submodules('streamlit')

a = Analysis(
    ['lanzador.py', 'app.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CREC_ERP_POS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CREC_ERP_POS',
)