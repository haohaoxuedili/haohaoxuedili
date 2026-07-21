[app]

# (str) Title of the application
title = NCM 转 MP3 / FLAC

# (str) Package name
package.name = ncm2mp3

# (str) Package domain (needed for android/ios packaging)
package.domain = io.github.idoknow

# (str) Source code directory
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,ttf,bin,so

# (str) Application versionning (method 1)
version = 1.0.3

# (str) Application icon
icon.filename = app.png

# (list) Application requirements
# python3, kivy: framework
# pycryptodome: AES decrypt of ncm metadata/key
# mutagen: write audio metadata
# Android 版先不使用 numpy，避免 python-for-android 编译 numpy 失败
requirements = python3,kivy,pycryptodome,mutagen,android,plyer

# (list) Application permissions
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE

# (int) Target Android API
android.api = 33

# (int) Minimum API required
android.minapi = 24

# (int) Android SDK version to use
android.sdk = 33

# (str) Android NDK version to use
android.ndk = 25b

# (list) Architectures of Android APKs to build
android.archs = arm64-v8a, armeabi-v7a

# (list) Android additional libraries to copy into lib/<abi>
android.add_libs_arm64_v8a = libs/arm64-v8a/libffmpeg.so
android.add_libs_armeabi_v7a = libs/armeabi-v7a/libffmpeg.so

# (bool) Indicate if the application should be compiled in debug mode
debug = 0

# (str) Android release keystore path (relative to source.dir)
android.keystore.path = release-key.keystore
# (str) The Android keystore alias
android.keystore.alias = __KEY_ALIAS__
# (str) Keystore password
android.keystore.storepass = __STOREPASS__
# (str) Key password
android.keystore.keypass = __KEYPASS__

# (str) Orientation of app
orientation = portrait

# (bool) Full screen mode
fullscreen = 0

[buildozer]

# (int) Log level, 0 = error only, 1 = info, 2 = debug (more verbose)
log_level = 2

# (str) Error output level
warn_on_skip = 1

# (bool) Accept SDK license automatically
android.accept_sdk_license = True
