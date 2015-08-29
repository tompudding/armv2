# -*- mode: python -*-
a = Analysis(['emulate.py'],
             pathex=['/Users/alex/Projects/rebellion'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='emulate',
          debug=True,
          strip=None,
          upx=True,
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               Tree('tapes', prefix = 'tapes'),
               Tree('fonts', prefix = 'fonts'),
               [('boot.rom', 'boot.rom', None)],
               [('petscii.txt', 'petscii.txt', None)],
               strip=None,
               upx=True,
               name='emulate')
app = BUNDLE(coll,
             name='emulate.app',
             icon=None)
