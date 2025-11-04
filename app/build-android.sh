#!/bin/bash

# AgriConnect Mobile - Android Development Build Script
# Run this on your HOST machine (not in Docker)

set -e

echo "================================"
echo "AgriConnect - Android Dev Build"
echo "================================"
echo ""

# Check if running in Docker (don't allow that)
if [ -f "/.dockerenv" ]; then
    echo "❌ ERROR: This script should be run on HOST machine, not inside Docker!"
    echo ""
    echo "Exit Docker container and run:"
    echo "  ./build-android.sh"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ ERROR: Node.js is not installed"
    echo "Install Node.js 18+ first"
    exit 1
fi

echo "✅ Node.js version: $(node --version)"

# Check npm/yarn
if command -v yarn &> /dev/null; then
    PKG_MANAGER="yarn"
else
    PKG_MANAGER="npm"
fi
echo "✅ Package manager: $PKG_MANAGER"

# Check Android SDK
if [ -z "$ANDROID_HOME" ]; then
    echo "⚠️  WARNING: ANDROID_HOME is not set"
    echo "Expo will try to detect Android SDK automatically"
    echo ""
else
    echo "✅ ANDROID_HOME: $ANDROID_HOME"
fi

# Check adb and detect devices
if ! command -v adb &> /dev/null; then
    echo "⚠️  WARNING: adb not found in PATH"
    echo "Make sure Android SDK platform-tools is in your PATH"
else
    echo "✅ adb found"
    echo ""
    echo "Connected devices:"
    adb devices
    echo ""

    # Prioritize physical devices over emulators
    PHYSICAL_DEVICE=$(adb devices | grep -v "List of devices" | grep -v "emulator" | grep "device$" | awk '{print $1}' | head -1)

    if [ -n "$PHYSICAL_DEVICE" ]; then
        echo "✅ Physical device found: $PHYSICAL_DEVICE"
        echo "Will use this device for installation"
        export ANDROID_SERIAL=$PHYSICAL_DEVICE
        echo ""
    else
        echo "⚠️  No physical device found. Will try to use emulator if available."
        echo ""
    fi
fi

# Check .env file
if [ ! -f ".env" ]; then
    echo "⚠️  WARNING: .env file not found"
    echo ""
    echo "Creating .env file..."

    # Try to detect IP address
    if command -v ip &> /dev/null; then
        HOST_IP=$(ip addr show | grep "inet 192" | awk '{print $2}' | cut -d/ -f1 | head -1)
    elif command -v ifconfig &> /dev/null; then
        HOST_IP=$(ifconfig | grep "inet 192" | awk '{print $2}' | head -1)
    else
        HOST_IP="localhost"
    fi

    echo "EXPO_PUBLIC_AGRICONNECT_SERVER_URL=http://${HOST_IP}:8000" > .env
    echo "✅ Created .env with backend URL: http://${HOST_IP}:8000"
    echo ""
    echo "If this IP is wrong, edit .env file manually"
else
    echo "✅ .env file exists"
    echo "Backend URL: $(cat .env | grep EXPO_PUBLIC_AGRICONNECT_SERVER_URL)"
fi

echo ""
echo "================================"
echo "Installing dependencies..."
echo "================================"
echo ""

$PKG_MANAGER install

echo ""
echo "================================"
echo "Building Android app..."
echo "================================"
echo ""
echo "This will:"
echo "  1. Generate native Android project (android/ folder)"
echo "  2. Build the APK"
echo "  3. Install on connected device/emulator"
echo "  4. Start Metro bundler"
echo ""
echo "Make sure your device is connected or emulator is running!"
echo ""

# Generate native Android project
echo "Step 1: Generating native Android project..."
npx expo prebuild --platform android

if [ $? -ne 0 ]; then
    echo "❌ Prebuild failed!"
    exit 1
fi

echo ""
echo "Step 2: Building and installing APK..."
cd android

# Build and install using Gradle (more reliable than expo run:android)
./gradlew installDebug

if [ $? -ne 0 ]; then
    echo "❌ Build/Install failed!"
    exit 1
fi

cd ..

echo ""
echo "================================"
echo "✅ Build complete!"
echo "================================"
echo ""
echo "The development build is now installed on your device."
echo ""
echo "Starting Metro bundler..."
echo ""

# Start Metro bundler in dev-client mode
npx expo start --dev-client

echo ""
echo "================================"
echo "Development Tips"
echo "================================"
echo ""
echo "To start development:"
echo "  1. App should auto-connect to Metro bundler"
echo "  2. Make code changes - hot reload will apply automatically"
echo "  3. To manually start Metro: npx expo start --dev-client"
echo ""
echo "To test push notifications:"
echo "  1. Login to the app"
echo "  2. Check logs for push token"
echo "  3. Send test notification via backend or Expo tool"
echo ""
echo "See README.md for more details"
echo ""
