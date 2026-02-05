# -*- mode: python ; coding: utf-8 -*-
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""
PyInstaller spec file for health_checks CLI.
"""
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, get_package_paths

block_cipher = None

# Read version from version.txt
version_file = Path('gcm/version.txt')
if version_file.exists():
    version = version_file.read_text().strip()
else:
    version = os.environ.get('GCM_VERSION', 'unknown')

# Set version in environment for runtime
os.environ['GCM_VERSION'] = version

# Collect all data/binaries for packages with mypyc or complex structure
datas = [
    ('gcm/version.txt', 'gcm'),
    ('gcm/py.typed', 'gcm'),
]
binaries = []
hiddenimports = []

# Packages that need full collection (mypyc compiled or complex)
packages_to_collect = ['pydantic', 'pydantic_core', 'click']
for pkg in packages_to_collect:
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
        datas.extend(pkg_datas)
        binaries.extend(pkg_binaries)
        hiddenimports.extend(pkg_hiddenimports)
    except Exception:
        pass

a = Analysis(
    ['gcm/health_checks/cli/health_checks.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        'gcm',
        'gcm._version',
        'gcm.health_checks',
        'gcm.health_checks.cli',
        'gcm.health_checks.cli.health_checks',
        'gcm.health_checks.checks',
        'gcm.health_checks.click',
        'gcm.monitoring',
        'gcm.monitoring.click',
        'gcm.monitoring.features',
        'gcm.monitoring.features.gen',
        'gcm.monitoring.features.gen.generated_features_healthchecksfeatures',
        'gcm.exporters',
        'gcm.exporters.registry',
        'gcm.exporters.do_nothing',
        'gcm.exporters.stdout',
        'gcm.exporters.file',
        'gcm.exporters.otel',
        'gcm.exporters.graph_api',
        'opentelemetry',
        'opentelemetry.sdk',
        'opentelemetry.sdk.trace',
        'opentelemetry.sdk.metrics',
        'opentelemetry.exporter.otlp',
        'opentelemetry.exporter.otlp.proto.grpc',
        'cffi',
        'pynvml',
        'omegaconf',
        'gni',
        'psutil',
        'daemon',
        'clusterscope',
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
    name='health_checks',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
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
    name='health_checks',
)
