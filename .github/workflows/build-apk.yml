name: Build APK

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:  # Permite executar manualmente

jobs:
  build:
    runs-on: ubuntu-22.04  # Mais estável que 24.04 para Buildozer

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Setup Python 3.10
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'

    - name: Install system dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y \
          git zip unzip openjdk-17-jdk \
          autoconf automake libtool pkg-config \
          zlib1g-dev libncurses5-dev libffi-dev libssl-dev \
          build-essential ccache python3-pip python3-venv \
          libltdl-dev wget curl

    - name: Setup Android SDK environment
      run: |
        echo "ANDROID_SDK_ROOT=$HOME/.buildozer/android/platform/android-sdk" >> $GITHUB_ENV
        echo "ANDROID_HOME=$HOME/.buildozer/android/platform/android-sdk" >> $GITHUB_ENV

    - name: Cache Buildozer global
      uses: actions/cache@v4
      with:
        path: ~/.buildozer
        key: buildozer-global-${{ runner.os }}-${{ hashFiles('buildozer.spec') }}
        restore-keys: |
          buildozer-global-${{ runner.os }}-

    - name: Cache Buildozer local
      uses: actions/cache@v4
      with:
        path: .buildozer
        key: buildozer-local-${{ runner.os }}-${{ hashFiles('buildozer.spec') }}
        restore-keys: |
          buildozer-local-${{ runner.os }}-

    - name: Install Buildozer and dependencies
      run: |
        python3 -m pip install --upgrade pip setuptools wheel
        pip install buildozer==1.5.0 cython==0.29.37

    - name: Ensure recipes folder exists
      run: |
        mkdir -p recipes
        
    - name: Create matplotlib recipe
      run: |
        cat > recipes/matplotlib/__init__.py << 'EOF'
        import os
        from pythonforandroid.recipes.matplotlib import MatplotlibRecipe

        class FixedMatplotlibRecipe(MatplotlibRecipe):
            need_stl_shared = True
            patches = []

            def get_recipe_env(self, arch=None, **kwargs):
                env = super().get_recipe_env(arch, **kwargs)
                env["MPLBACKEND"] = "Agg"
                env["USE_OPENMP"] = "0"
                return env

        recipe = FixedMatplotlibRecipe()
        EOF

    - name: Create harfbuzz recipe
      run: |
        cat > recipes/harfbuzz/__init__.py << 'EOF'
        from pythonforandroid.recipe import Recipe

        class HarfbuzzPatchedRecipe(Recipe):
            version = "5.3.1"
            url = "https://github.com/harfbuzz/harfbuzz/archive/refs/tags/{version}.tar.gz"

            def get_recipe_env(self, arch=None, **kwargs):
                env = super().get_recipe_env(arch, **kwargs)
                env["CFLAGS"] = env.get("CFLAGS", "") + " -Wno-error=cast-function-type-strict"
                env["CXXFLAGS"] = env.get("CXXFLAGS", "") + " -Wno-error=cast-function-type-strict"
                return env
                
        recipe = HarfbuzzPatchedRecipe()
        EOF

    - name: Create placeholder icon if missing
      run: |
        if [ ! -f icone.png ]; then
          echo "Creating placeholder icon..."
          python3 << 'PYEOF'
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGB', (512, 512), color='#2196F3')
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 200)
        except:
            font = ImageFont.load_default()
        d.text((256, 256), "A", fill='white', anchor='mm', font=font)
        img.save('icone.png')
        PYEOF
        fi

    - name: Verify buildozer.spec
      run: |
        if [ ! -f buildozer.spec ]; then
          echo "ERROR: buildozer.spec not found!"
          exit 1
        fi
        cat buildozer.spec

    - name: Build APK with Buildozer
      run: |
        # Aceita licenças automaticamente
        yes | buildozer android debug 2>&1 | tee build.log
      env:
        BUILDOZER_WARN_ON_ROOT: 0
      continue-on-error: true

    - name: Check build status
      run: |
        if [ -f bin/*.apk ] || [ -f .buildozer/android/platform/build-*/dists/*/bin/*.apk ]; then
          echo "✅ APK gerado com sucesso!"
          exit 0
        else
          echo "❌ Falha ao gerar APK. Verifique os logs."
          exit 1
        fi

    - name: Upload build logs
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: build-logs
        path: |
          build.log
          .buildozer/android/platform/build-*/build.log
        if-no-files-found: warn

    - name: Upload APK
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: app-debug-apk
        path: |
          bin/*.apk
          .buildozer/android/platform/build-*/dists/*/bin/*.apk
        if-no-files-found: warn

    - name: Find and display APK location
      if: always()
      run: |
        echo "Procurando APKs gerados..."
        find . -name "*.apk" -type f 2>/dev/null || echo "Nenhum APK encontrado"
