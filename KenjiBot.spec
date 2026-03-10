# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for KenjiBot — bundles everything into a single folder."""

import os

block_cipher = None

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('Kenji_bot_prompt.txt', '.'),
        ('config.py', '.'),
    ],
    hiddenimports=[
        'bot',
        'claude_client',
        'tts',
        'stream_listener',
        'config',
        'twitchio',
        'twitchio.ext.commands',
        'anthropic',
        'pygame',
        'pyaudio',
        'numpy',
        'faster_whisper',
        'ctranslate2',
        'huggingface_hub',
        'tokenizers',
        'onnxruntime',
        'requests',
        'aiohttp',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='KenjiBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window — GUI only
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='KenjiBot',
)
