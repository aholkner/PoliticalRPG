# -*- mode: python -*-
a = Analysis(['GoodnightMrPresident.py'],
             pathex=['GoodnightMrPresident'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
res_tree = Tree('res', prefix='res')
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          res_tree,
          name='GoodnightMrPresident.exe',
          icon='icon.ico',
          debug=False,
          strip=None,
          upx=True,
          console=False)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               #res_tree,
               strip=None,
               upx=True,
               name='dist/GoodnightMrPresident')
app = BUNDLE(coll,
             name='GoodnightMrPresident.app',
             icon=None)
