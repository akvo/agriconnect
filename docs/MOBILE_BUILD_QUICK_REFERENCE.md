# Mobile App Build - Quick Reference

> Quick commands and references for mobile app deployment

## Prerequisites

- ✅ `EXPO_TOKEN` added to GitHub Secrets
- ✅ Expo account with project access
- ✅ EAS CLI installed: `npm install -g eas-cli`

## Quick Commands

### Build Commands

```bash
# Build production APK via EAS
cd app && eas build --platform android --profile production

# Build preview APK
cd app && eas build --platform android --profile preview

# Build locally (faster, requires Android SDK)
cd app && eas build --platform android --profile preview --local

# Check build status
eas build:list

# View specific build
eas build:view [BUILD_ID]
```

### Local Testing

```bash
# Start dev server
./dc.sh exec mobileapp yarn start

# Run linter
./dc.sh exec mobileapp yarn lint

# Clear cache
./dc.sh stop mobileapp && ./dc.sh up -d mobileapp
```

## Build Profiles

| Profile | Use Case | Distribution | Wait Time |
|---------|----------|--------------|-----------|
| `development` | Local dev/testing | Internal | ~10-15 min |
| `preview` | Internal testing | Internal | ~10-15 min |
| `production` | Release builds | Public/Internal | ~10-15 min |

## GitHub Workflow

**Automatic trigger:** Push to `main` branch

```bash
git add .
git commit -m "feat: new feature"
git push origin main
```

**Manual trigger:** Run workflow from GitHub Actions UI

## Download APK

### From Expo Dashboard
1. Visit https://expo.dev
2. Go to your project
3. Click "Builds" tab
4. Download completed build

### From CLI
```bash
# List builds
eas build:list

# Download specific build
eas build:download [BUILD_ID]
```

## Install APK

### Via ADB
```bash
adb install path/to/app.apk
```

### Direct Transfer
1. Transfer APK to Android device
2. Enable "Install from Unknown Sources"
3. Tap APK to install

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Not authenticated" | Check `EXPO_TOKEN` in GitHub Secrets |
| "Project not found" | Run `eas build:configure` locally |
| Build stuck in queue | Check Expo plan limits |
| Dependencies error | Run `cd app && yarn install` |

## File Locations

```
app/
├── eas.json              # Build configuration
├── app.json              # App metadata
└── package.json          # Dependencies

.github/workflows/
└── deploy.yml            # CI/CD workflow

ci/
└── build.sh              # Build script
```

## Useful Links

- 📱 [Expo Dashboard](https://expo.dev)
- 📚 [EAS Build Docs](https://docs.expo.dev/build/introduction/)
- 🔧 [GitHub Actions](https://github.com/akvo/agriconnect/actions)
- 📖 [Full Documentation](./MOBILE_APP_DEPLOYMENT.md)

## Version Info

- **Expo SDK**: 54
- **React Native**: 0.81.4
- **Node**: 24
- **Build Type**: APK (Android)

---

**Last Updated:** 2025-10-14
