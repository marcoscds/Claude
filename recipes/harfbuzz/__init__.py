from pythonforandroid.recipe import CompiledComponentsPythonRecipe

class HarfbuzzPatchedRecipe(CompiledComponentsPythonRecipe):
    version = "5.3.1"
    url = "https://github.com/harfbuzz/harfbuzz/archive/refs/tags/{version}.tar.gz"
    depends = ["freetype"]
    
    def get_recipe_env(self, arch=None, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        
        cflags = env.get("CFLAGS", "")
        cxxflags = env.get("CXXFLAGS", "")
        warning_flag = " -Wno-error=cast-function-type-strict"
        
        if warning_flag not in cflags:
            env["CFLAGS"] = cflags + warning_flag
        if warning_flag not in cxxflags:
            env["CXXFLAGS"] = cxxflags + warning_flag
        
        return env

recipe = HarfbuzzPatchedRecipe()
