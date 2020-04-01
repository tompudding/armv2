from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

setup(
    cmdclass={'build_ext': build_ext},
    ext_modules=[Extension("armv2", ["armv2.pyx"], extra_objects=['libarmv2.a'])]
)

setup(
    cmdclass={'build_ext': build_ext},
    ext_modules=[Extension("popcnt", ["popcnt.pyx"])]
)
