import os
from pythonforandroid.recipes.matplotlib import MatplotlibRecipe

class FixedMatplotlibRecipe(MatplotlibRecipe):
    need_stl_shared = True
    patches = []

    def get_recipe_env(self, arch=None, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        env["MPLBACKEND"] = "Agg"
        env["USE_OPENMP"] = "0"
        
        if "CFLAGS" not in env:
            env["CFLAGS"] = ""
        if "CXXFLAGS" not in env:
            env["CXXFLAGS"] = ""
            
        env["CFLAGS"] += " -Wno-error"
        env["CXXFLAGS"] += " -Wno-error -std=c++17"
        
        return env

recipe = FixedMatplotlibRecipe()
