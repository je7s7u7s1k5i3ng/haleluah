# PyInstaller spec for Windows scout.exe
# Build: pyinstaller scout.spec
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['src/item_scout/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules('item_scout') + [
        'httpx', 'h2', 'hpack', 'hyperframe',
        'orjson', 'aiolimiter', 'tenacity',
        'pydantic', 'pydantic_settings',
        'rich', 'typer', 'click', 'shellingham',
        'pandas', 'openpyxl',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'IPython', 'jupyter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='scout',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
