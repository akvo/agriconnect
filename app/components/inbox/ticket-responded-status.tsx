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
  return (
    <View style={[styles.container, containerStyle]}>
      <Text style={[typography.caption1, { color: themeColors.dark3 }]}>
        {`Ticket: #${ticketNumber}`}
      </Text>
      <View style={[styles.flexRow]}>
        <Text style={[typography.body4, { color: themeColors.textPrimary }]}>
          Responded by:
        </Text>
        {respondedBy ? (
          <View style={[styles.flexRow, { justifyContent: "space-between" }]}>
            <Text
              style={[typography.body4, { color: themeColors["green-500"] }]}
            >
              {respondedBy.name}
            </Text>
            <Text style={[typography.caption2, { color: themeColors.dark4 }]}>
              {formatResolved(resolvedAt)}
            </Text>
          </View>
        ) : (
          <Text
            style={[
              typography.body4,
              { color: themeColors.error, fontWeight: 500 },
            ]}
          >
            No response yet
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
  },
});

export default TicketRespondedStatus;
