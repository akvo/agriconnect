import { SplashScreen } from "expo-router";
import { useAuth } from "@/contexts/AuthContext";

SplashScreen.preventAutoHideAsync();

const SplashScreenController = () => {
  const { isLoading } = useAuth();
  console.log("SplashScreenController - isLoading:", isLoading);

  if (!isLoading) {
    SplashScreen.hide();
  }

  return null;
};

export default SplashScreenController;
