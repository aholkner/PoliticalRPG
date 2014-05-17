# -*- mode: python -*-
a = Analysis(['run_game.py'],
             pathex=[''],
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
          name='GoodbyeMrPresident.exe',
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
               name='dist/GoodbyeMrPresident')
app = BUNDLE(coll,
             name='GoodbyeMrPresident.app',
             icon=None)