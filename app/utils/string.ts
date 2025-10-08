export const initialsFromName = (name: string) =>
  name
    .split(" ")
    .map((n) => n.charAt(0).toUpperCase())
    .slice(0, 2)
    .join("");

export default {
  initialsFromName,
};
