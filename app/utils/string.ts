export const initialsFromName = (name: string) =>
  name
    .split(" ")
    .map((n) => n.charAt(0).toUpperCase())
    .slice(0, 2)
    .join("");

export const validJSONString = (str: string): boolean => {
  const jsonRegex = /^[\],:{}\s]*$/;
  return jsonRegex.test(
    str
      .replace(/\\["\\\/bfnrtu]/g, "@")
      .replace(
        /"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g,
        "]",
      )
      .replace(/(?:^|:|,)(?:\s*\[)+/g, ""),
  );
};

export default {
  initialsFromName,
  validJSONString,
};
