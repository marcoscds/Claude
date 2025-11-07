[app]

# Nome do app
title = Caracterizador de Antenas
package.name = myapp
package.domain = org.test

# Código fonte
source.dir = .
source.include_exts = py,png,jpg,kv,atlas

# Versão
version = 0.1

# Requisitos - ordem importa!
requirements = python3==3.10,kivy==2.3.0,numpy,pillow,pyjnius,requests,freetype,libpng,harfbuzz,matplotlib==3.6.3

# Recipes personalizadas
p4a.local_recipes = recipes
p4a.branch = develop
p4a.bootstrap = sdl2

# Configurações Python
p4a.python_version = 3.10

# Flags de compilação
p4a.extra_env_vars = CFLAGS=-Wno-error=cast-function-type-strict,CXXFLAGS=-Wno-error=cast-function-type-strict

# Arquiteturas Android
android.archs = arm64-v8a,armeabi-v7a

# API levels
android.api = 33
android.minapi = 26
android.ndk = 25b

# Ícone e orientação
icon.filename = icone.png
orientation = portrait
fullscreen = 0

# Permissões necessárias
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_SCAN,BLUETOOTH_CONNECT,ACCESS_COARSE_LOCATION,ACCESS_FINE_LOCATION,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,INTERNET

# Backup
android.allow_backup = True

# Aceitar licenças automaticamente
android.accept_sdk_license = True

# Otimizações
android.gradle_dependencies = 

[buildozer]

# Nível de log (2 = info)
log_level = 2

# Avisos
warn_on_root = 0
