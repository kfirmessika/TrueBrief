@echo off
set JAVA_HOME=C:\Program Files\Microsoft\jdk-21.0.12.8-hotspot
set ANDROID_HOME=D:\android-sdk
cd /d "%~dp0"
call gradlew.bat assembleDebug --no-daemon
