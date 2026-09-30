const IS_TEST = process.env.APP_VARIANT === "test";

const getPackageName = () => {
  if (IS_TEST) return "com.akvo.comhydroponics.test";
  return "com.akvo.comhydroponics";
};

const getAppName = () => {
  if (IS_TEST) return "CoM Hydroponics (Test)";
  return "CoM Hydroponics";
};

module.exports = {
  expo: {
    name: getAppName(),
    slug: "com-hydroponics-mobile",
    version: "1.4.1",
    owner: "akvo",
    orientation: "portrait",
    icon: "./assets/images/icon.png",
    scheme: "agriconnect",
    userInterfaceStyle: "light",
    newArchEnabled: true,
    android: {
      package: getPackageName(),
      adaptiveIcon: {
        backgroundColor: "#E6F4FE",
        foregroundImage: "./assets/images/android-icon-foreground.png",
        backgroundImage: "./assets/images/android-icon-background.png",
        monochromeImage: "./assets/images/android-icon-monochrome.png",
      },
      edgeToEdgeEnabled: true,
      predictiveBackGestureEnabled: false,
      softwareKeyboardLayoutMode: "pan",
      googleServicesFile:
        process.env.GOOGLE_SERVICES_JSON || "./google-services.json",
      useNextNotificationsApi: true,
    },
    web: {
      output: "static",
      favicon: "./assets/images/favicon.png",
    },
    plugins: [
      [
        "expo-router",
        {
          root: "./app",
        },
      ],
      [
        "expo-splash-screen",
        {
          image: "./assets/images/splash-icon.png",
          imageWidth: 200,
          resizeMode: "contain",
          backgroundColor: "#027E5D",
        },
      ],
      [
        "expo-sqlite",
        {
          enableFTS: false,
          useSQLCipher: true,
        },
      ],
      [
        "expo-notifications",
        {
          icon: "./assets/images/notification-icon.png",
          color: "#ffffff",
          sounds: [],
        },
      ],
      "expo-secure-store",
      "./plugins/withProguard",
    ],
    androidNavigationBar: {
      visible: "overscan",
      barStyle: "light-content",
      backgroundColor: "#000000",
    },
    experiments: {
      typedRoutes: true,
      reactCompiler: true,
    },
    platforms: ["android", "web"],
    extra: {
      eas: {
        projectId: "7e9f4622-d223-4d99-a005-5b96293bd978",
      },
    },
  },
};
