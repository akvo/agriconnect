import { View, Text, StyleSheet } from "react-native";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import { formatResolved } from "@/utils/time";

interface TicketRespondedStatusProps {
  ticketNumber: string;
  respondedBy: { name: string } | null;
  resolvedAt: string | null | undefined;
  containerStyle?: object | object[];
}

const TicketRespondedStatus = ({
  ticketNumber,
  respondedBy,
  resolvedAt,
  containerStyle,
}: TicketRespondedStatusProps) => {
  const label = resolvedAt ? "Closed by:" : "Responded by:";

  return (
    <View style={[styles.container, containerStyle]}>
      <Text style={[typography.caption1, { color: themeColors.dark3 }]}>
        {`Ticket: #${ticketNumber}`}
      </Text>
      <View style={[styles.flexRow]}>
        <View
          style={{
            flexDirection: "row",
            alignItems: "flex-start",
            gap: 4,
          }}
        >
          <Text style={[typography.body4, { color: themeColors.textPrimary }]}>
            {label}
          </Text>

          <Text
            style={[
              typography.body4,
              {
                color: respondedBy
                  ? themeColors["green-500"]
                  : themeColors.error,
              },
            ]}
          >
            {respondedBy ? respondedBy.name : "No response yet"}
          </Text>
        </View>

        {resolvedAt && (
          <Text style={[typography.caption2, { color: themeColors.dark4 }]}>
            {formatResolved(resolvedAt)}
          </Text>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: "100%",
    flexDirection: "column",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 4,
  },
  flexRow: {
    width: "100%",
    gap: 4,
    flexDirection: "row",
    justifyContent: "space-between",
  },
});

export default TicketRespondedStatus;
