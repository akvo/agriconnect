export const initialsFromName = (name: string) =>
  /^\+\d{10,}$/.test(name)
    ? ""
    : name
        .split(" ")
        .map((n) => n.charAt(0).toUpperCase())
        .slice(0, 2)
        .join("");

export const capitalizeFirstLetter = (str: string | null): string => {
  if (!str) {
    return "";
  }
  return str.charAt(0).toUpperCase() + str.slice(1).replace("_", " ");
};

export default {
  initialsFromName,
  capitalizeFirstLetter,
};
