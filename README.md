# AgriConnect

[![Test](https://github.com/akvo/agriconnect/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/akvo/agriconnect/actions/workflows/test.yml)
[![Coverage Status](https://coveralls.io/repos/github/akvo/agriconnect/badge.svg?branch=main)](https://coveralls.io/github/akvo/agriconnect?branch=main)
[![GitHub repo size](https://img.shields.io/github/repo-size/akvo/agriconnect)](https://github.com/akvo/agriconnect)
[![GitHub top language](https://img.shields.io/github/languages/top/akvo/agriconnect)](https://github.com/akvo/agriconnect)
[![GitHub issues](https://img.shields.io/github/issues/akvo/agriconnect)](https://github.com/akvo/agriconnect/issues)
[![GitHub last commit](https://img.shields.io/github/last-commit/akvo/agriconnect)](https://github.com/akvo/agriconnect/commits/main)

## Development Setup

1. Create the Docker sync volume:
```bash
docker volume create agriconnect-docker-sync
```

2. Start the development environment:
```bash
./dc.sh up -d
```

That's it! Your development environment should now be running.

## Usage

The `./dc.sh` script is a wrapper around Docker Compose that combines multiple compose files for the full development environment. It supports all standard Docker Compose commands:

### Common Commands

- **Start the development environment:**
  ```bash
  ./dc.sh up -d
  ```

- **Stop the development environment:**
  ```bash
  ./dc.sh down
  ```

- **View running services:**
  ```bash
  ./dc.sh ps
  ```

- **View logs:**
  ```bash
  ./dc.sh logs
  ./dc.sh logs -f  # Follow logs
  ./dc.sh logs backend  # View specific service logs
  ```

### Development Commands

- **Execute commands in the backend container:**
  ```bash
  ./dc.sh exec backend <command>
  ```

  Examples:
  ```bash
  ./dc.sh exec backend tests     # Run backend tests
  ./dc.sh exec backend flake8    # Run backend linter
  ./dc.sh exec backend bash      # Open bash shell
  ```

- **Execute commands in the frontend container:**
  ```bash
  ./dc.sh exec frontend <command>
  ```

  Examples:
  ```bash
  ./dc.sh exec frontend prettier --write .  # Format frontend code
  ./dc.sh exec frontend bash                # Open bash shell
  ```

### Available Services

The environment includes the following services:

- **db**: PostgreSQL database (port 5432)
- **backend**: Python FastAPI backend (port 8000)
- **frontend**: Node.js frontend application (port 3000)
- **mobileapp**: React Native mobile app development (port 8081)
- **pgadmin**: Database management interface (port 5050)
- **mainnetwork**: Network service with port mappings

### Access URLs

Once the environment is running, you can access:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- pgAdmin: http://localhost:5050
- Mobile app development via [Expo GO](https://play.google.com/store/apps/details?id=host.exp.exponent&hl=en): exp://<your_ip_address>:14000

## Mobile App Development

### Development with Expo Go (For Quick Testing)

The mobile app runs in the Docker container and can be accessed via Expo Go on your physical device:

```bash
# Make sure the services are running
./dc.sh up -d

# The mobile app will be available at:
# exp://<your_ip_address>:8081
```

Scan the QR code displayed in the terminal with:
- iOS: Camera app
- Android: Expo Go app

**Note:** Expo Go has limitations and doesn't support all native features like push notifications.

### Local Development Build (For Full Features)

For features that require native code (push notifications, SQLite with encryption, etc.), you need to build a development build on your **host machine** (not in Docker):

#### Prerequisites
- Node.js v22.20.0 (recommended) installed on your host machine
- Android Studio with SDK tools (for Android builds)
- Physical Android device or emulator

#### Build Instructions

1. **Exit Docker** if you're currently in a container

2. **Navigate to the app directory** on your host machine:
   ```bash
   cd /home/iwan/Akvo/agriconnect/app
   ```

3. **Configure Firebase** (required for push notifications):
   - Get your `google-services.json` from Firebase Console
   - Place it in `/home/iwan/Akvo/agriconnect/app/google-services.json`
   - The file is already configured in `app.json` and excluded from git

4. **Run the build script**:
   ```bash
   ./build-android.sh
   ```

   This script will:
   - Check your environment (Node.js, Android SDK)
   - Create `.env` file with backend URL
   - Install dependencies
   - Generate native Android project
   - Build and install the APK on your device
   - Start Metro bundler

5. **Development workflow**:
   - The app auto-connects to Metro bundler
   - Code changes hot-reload automatically
   - To manually start Metro: `npx expo start --dev-client`

#### Troubleshooting

**Port 8081 Already in Use**

If you see an error that port 8081 is already in use (likely because the Docker mobileapp container is running):

1. **Option 1: Stop the Docker container** (Recommended)
   ```bash
   ./dc.sh stop mobileapp
   ```

2. **Option 2: Use a different port**

   If Metro asks to use port 8082, you can accept it, but note that you'll need to update your connection settings in the app.

#### Testing Push Notifications

After building the development build:

1. Login to the app
2. Check the console logs for your push token
3. Device will automatically register with the backend
4. Send test notifications via:
   - Backend API (`/api/devices` endpoints)
   - Expo Push Notification Tool
   - Create/update tickets to trigger notifications

**Important:** Push notifications only work in development builds, not in Expo Go.
