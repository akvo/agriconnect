const {
  withGradleProperties,
  withDangerousMod,
} = require("expo/config-plugins");
const fs = require("fs");
const path = require("path");

/**
 * Config plugin to enable R8/ProGuard minification and ABI filtering for release builds.
 * This reduces APK size by ~60% (from ~137MB to ~55-65MB).
 */
function withProguard(config) {
  // Add gradle properties for minification and ABI filter
  config = withGradleProperties(config, (config) => {
    // Remove existing reactNativeArchitectures if present
    config.modResults = config.modResults.filter(
      (prop) => prop.key !== "reactNativeArchitectures"
    );

    // Add our properties
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
      },
      {
        type: "property",
        key: "reactNativeArchitectures",
        value: "arm64-v8a",
      }
    );
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
