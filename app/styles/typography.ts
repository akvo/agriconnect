import { StyleSheet, TextStyle } from "react-native";
import themeColors from "./colors";

export const typographyTokens = {
  familyPrimary: "Inter",
  weights: {
    thin: 100,
    extralight: 200,
    light: 300,
    regular: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
    extrabold: 800,
    black: 900,
  },

  // Titles
  title1: { fontSize: 72, lineHeight: 88, letterSpacing: -0.8 },
  title2: { fontSize: 64, lineHeight: 76, letterSpacing: -0.8 },
  title3: { fontSize: 56, lineHeight: 68, letterSpacing: -0.6 },

  // Headings
  heading1: { fontSize: 56, lineHeight: 68, letterSpacing: -0.5 },
  heading2: { fontSize: 48, lineHeight: 58, letterSpacing: -0.4 },
  heading3: { fontSize: 40, lineHeight: 48, letterSpacing: -0.3 },
  heading4: { fontSize: 32, lineHeight: 38, letterSpacing: -0.2 },
  heading5: { fontSize: 24, lineHeight: 30, letterSpacing: -0.15 },
  heading6: { fontSize: 20, lineHeight: 24, letterSpacing: 0 },

  // Labels
  label1: { fontSize: 16, lineHeight: 22, letterSpacing: -0.18 },
  label2: { fontSize: 14, lineHeight: 20, letterSpacing: -0.16 },
  label3: { fontSize: 12, lineHeight: 16, letterSpacing: -0.12 },

  // Body
  body1: { fontSize: 18, lineHeight: 28, letterSpacing: 0 },
  body2: { fontSize: 16, lineHeight: 24, letterSpacing: 0 },
  body3: { fontSize: 14, lineHeight: 20, letterSpacing: 0 },
  body4: { fontSize: 12, lineHeight: 16, letterSpacing: 0 },

  // Caption
  caption1: { fontSize: 10, lineHeight: 12, letterSpacing: 0 },
  caption2: { fontSize: 9, lineHeight: 10, letterSpacing: 0 },

  // Colors moved to colors.ts
};

// Create typed text styles for common usages
type TextStyles = {
  title1: TextStyle;
  title2: TextStyle;
  title3: TextStyle;
  heading1: TextStyle;
  heading2: TextStyle;
  heading3: TextStyle;
  heading4: TextStyle;
  heading5: TextStyle;
  heading6: TextStyle;
  label1: TextStyle;
  label2: TextStyle;
  label3: TextStyle;
  body1: TextStyle;
  body2: TextStyle;
  body3: TextStyle;
  body4: TextStyle;
  caption1: TextStyle;
  caption2: TextStyle;
};

const baseFontFamily = typographyTokens.familyPrimary;
const weights = typographyTokens.weights;

const typography = StyleSheet.create<TextStyles>({
  title1: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.bold) as any,
    fontSize: typographyTokens.title1.fontSize,
    lineHeight: typographyTokens.title1.lineHeight,
    letterSpacing: typographyTokens.title1.letterSpacing,
  color: themeColors.textPrimary,
  },
  title2: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.bold) as any,
    fontSize: typographyTokens.title2.fontSize,
    lineHeight: typographyTokens.title2.lineHeight,
    letterSpacing: typographyTokens.title2.letterSpacing,
  color: themeColors.textPrimary,
  },
  title3: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.bold) as any,
    fontSize: typographyTokens.title3.fontSize,
    lineHeight: typographyTokens.title3.lineHeight,
    letterSpacing: typographyTokens.title3.letterSpacing,
  color: themeColors.textPrimary,
  },

  heading1: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.semibold) as any,
    fontSize: typographyTokens.heading1.fontSize,
    lineHeight: typographyTokens.heading1.lineHeight,
    letterSpacing: typographyTokens.heading1.letterSpacing,
  color: themeColors.textPrimary,
  },
  heading2: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.semibold) as any,
    fontSize: typographyTokens.heading2.fontSize,
    lineHeight: typographyTokens.heading2.lineHeight,
    letterSpacing: typographyTokens.heading2.letterSpacing,
  color: themeColors.textPrimary,
  },
  heading3: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.semibold) as any,
    fontSize: typographyTokens.heading3.fontSize,
    lineHeight: typographyTokens.heading3.lineHeight,
    letterSpacing: typographyTokens.heading3.letterSpacing,
  color: themeColors.textPrimary,
  },
  heading4: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.medium) as any,
    fontSize: typographyTokens.heading4.fontSize,
    lineHeight: typographyTokens.heading4.lineHeight,
    letterSpacing: typographyTokens.heading4.letterSpacing,
  color: themeColors.textPrimary,
  },
  heading5: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.medium) as any,
    fontSize: typographyTokens.heading5.fontSize,
    lineHeight: typographyTokens.heading5.lineHeight,
    letterSpacing: typographyTokens.heading5.letterSpacing,
  color: themeColors.textPrimary,
  },
  heading6: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.regular) as any,
    fontSize: typographyTokens.heading6.fontSize,
    lineHeight: typographyTokens.heading6.lineHeight,
    letterSpacing: typographyTokens.heading6.letterSpacing,
  color: themeColors.textPrimary,
  },

  label1: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.semibold) as any,
    fontSize: typographyTokens.label1.fontSize,
    lineHeight: typographyTokens.label1.lineHeight,
    letterSpacing: typographyTokens.label1.letterSpacing,
  color: themeColors.textSecondary,
  },
  label2: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.medium) as any,
    fontSize: typographyTokens.label2.fontSize,
    lineHeight: typographyTokens.label2.lineHeight,
    letterSpacing: typographyTokens.label2.letterSpacing,
  color: themeColors.textSecondary,
  },
  label3: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.regular) as any,
    fontSize: typographyTokens.label3.fontSize,
    lineHeight: typographyTokens.label3.lineHeight,
    letterSpacing: typographyTokens.label3.letterSpacing,
  color: themeColors.textSecondary,
  },

  body1: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.regular) as any,
    fontSize: typographyTokens.body1.fontSize,
    lineHeight: typographyTokens.body1.lineHeight,
    letterSpacing: typographyTokens.body1.letterSpacing,
  color: themeColors.textPrimary,
  },
  body2: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.regular) as any,
    fontSize: typographyTokens.body2.fontSize,
    lineHeight: typographyTokens.body2.lineHeight,
    letterSpacing: typographyTokens.body2.letterSpacing,
  color: themeColors.textPrimary,
  },
  body3: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.regular) as any,
    fontSize: typographyTokens.body3.fontSize,
    lineHeight: typographyTokens.body3.lineHeight,
    letterSpacing: typographyTokens.body3.letterSpacing,
  color: themeColors.textPrimary,
  },
  body4: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.regular) as any,
    fontSize: typographyTokens.body4.fontSize,
    lineHeight: typographyTokens.body4.lineHeight,
    letterSpacing: typographyTokens.body4.letterSpacing,
  color: themeColors.textPrimary,
  },

  caption1: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.regular) as any,
    fontSize: typographyTokens.caption1.fontSize,
    lineHeight: typographyTokens.caption1.lineHeight,
    letterSpacing: typographyTokens.caption1.letterSpacing,
  color: themeColors.textTertiary,
  },
  caption2: {
    fontFamily: baseFontFamily,
    fontWeight: String(weights.regular) as any,
    fontSize: typographyTokens.caption2.fontSize,
    lineHeight: typographyTokens.caption2.lineHeight,
    letterSpacing: typographyTokens.caption2.letterSpacing,
  color: themeColors.textTertiary,
  },
  bold: {
    fontWeight: String(weights.bold) as any,
  },
  textPrimary: {
  color: themeColors.textPrimary,
  },
  textGreen500: {
    color: themeColors["green-500"],
  },
});

export default typography;
