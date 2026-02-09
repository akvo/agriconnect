const {
  withGradleProperties,
  withDangerousMod,
  withAppBuildGradle,
} = require("expo/config-plugins");
const fs = require("fs");
const path = require("path");

/**
 * Config plugin to enable R8/ProGuard minification and ABI filtering for release builds.
 * This reduces APK size by ~60% (from ~137MB to ~55-65MB).
 */
function withProguard(config) {
  // Add gradle properties for minification
  config = withGradleProperties(config, (config) => {
    config.modResults.push(
      {
        type: "property",
        key: "android.enableMinifyInReleaseBuilds",
        value: "true",
      },
      {
        type: "property",
        key: "android.enableShrinkResourcesInReleaseBuilds",
        value: "true",
      }
    );
    return config;
  });

  // Add ABI filter for arm64-v8a only (reduces APK size by ~40-50%)
  config = withAppBuildGradle(config, (config) => {
    const buildGradle = config.modResults.contents;

    // Check if abiFilters is already configured
    if (buildGradle.includes("abiFilters")) {
      return config;
    }

    // Find defaultConfig block and add ndk abiFilters
    const defaultConfigRegex = /(defaultConfig\s*\{[^}]*)(})/;
    const match = buildGradle.match(defaultConfigRegex);

    if (match) {
      const abiFilterConfig = `
        ndk {
            abiFilters "arm64-v8a"
        }
    `;

      config.modResults.contents = buildGradle.replace(
        defaultConfigRegex,
        `$1${abiFilterConfig}$2`
      );
    }

    return config;
  });

  // Add custom ProGuard rules
  config = withDangerousMod(config, [
    "android",
    async (config) => {
      const proguardRulesPath = path.join(
        config.modRequest.platformProjectRoot,
        "app",
        "proguard-rules.pro"
      );

      const customRules = `
# Hermes engine
-keep class com.facebook.hermes.unicode.** { *; }
-keep class com.facebook.jni.** { *; }

# Expo modules
-keep class expo.modules.** { *; }
-keepclassmembers class * {
    @expo.modules.core.interfaces.ExpoProp *;
}

# SQLCipher / expo-sqlite
-keep class net.sqlcipher.** { *; }
-keep class net.sqlcipher.database.* { *; }

# Firebase (for push notifications)
-keep class com.google.firebase.** { *; }
-keep class com.google.android.gms.** { *; }

# Keep native methods
-keepclassmembers class * {
    native <methods>;
}
`;

      // Read existing rules and append custom ones if not already present
      let existingRules = "";
      if (fs.existsSync(proguardRulesPath)) {
        existingRules = fs.readFileSync(proguardRulesPath, "utf-8");
      }

      // Only add if not already present
      if (!existingRules.includes("# Hermes engine")) {
        fs.writeFileSync(proguardRulesPath, existingRules + customRules);
      }

      return config;
    },
  ]);

  return config;
}

module.exports = withProguard;
