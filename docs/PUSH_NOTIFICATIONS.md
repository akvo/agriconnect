# Push Notifications Guide

This guide covers the push notification system for the AgriConnect mobile application, including setup, architecture, and troubleshooting.

## Overview

AgriConnect uses **Expo Push Notifications** with **Firebase Cloud Messaging (FCM)** to deliver real-time notifications to mobile devices. The system notifies Extension Officers and Admin users when:

1. **New Ticket Created**: A new support ticket is created in their assigned ward
2. **New Message**: A new message arrives on an open ticket in their ward (excluding the sender)

### Key Features

- **Device-Ward Association**: Devices are associated with administrative areas (wards) rather than individual users
- **Smart Notification Suppression**: Notifications are suppressed when users are actively viewing the relevant ticket
- **Deep Linking**: Tapping notifications opens the app directly to the ticket thread
- **Batch Processing**: Efficient batch sending (up to 100 notifications per request)
- **Retry Mechanism**: Exponential backoff retry logic for failed deliveries
- **Invalid Token Handling**: Automatic cleanup of expired/invalid device tokens

## Architecture

### Backend Components

#### 1. Device Model (`backend/models/device.py`)
Stores device registration information:
- **push_token**: Expo push token (unique identifier)
- **administrative_id**: Associated ward (foreign key)
- **app_version**: Mobile app version
- **is_active**: Status flag (automatically set to false for invalid tokens)

#### 2. Push Notification Service (`backend/services/push_notification_service.py`)
Core service for sending notifications:
- **send_notification()**: Send push notifications to multiple devices
- **notify_new_ticket()**: Handle new ticket notifications
- **notify_new_message()**: Handle new message notifications
- **get_ward_user_tokens()**: Get tokens for devices in a specific ward
- **get_admin_user_tokens()**: Get tokens for devices in admin wards

#### 3. Device Router (`backend/routers/devices.py`)
REST API endpoints for device management:
- **POST /devices**: Register/update a device
- **GET /devices**: List all devices for current user's ward
- **DELETE /devices/{device_id}**: Remove a device
- **DELETE /devices/token/{push_token}**: Remove device by token

#### 4. WebSocket Integration (`backend/routers/ws.py`)
Real-time notifications triggered via WebSocket events:
- **ticket_created**: Triggers push notifications for new tickets
- **message_created**: Triggers push notifications for new messages
- **Active viewer detection**: Prevents notifications for active users

### Mobile App Components

#### 1. Notification Context (`app/contexts/NotificationContext.tsx`)
Manages notification state and permissions:
- **registerForPushNotificationsAsync()**: Request permissions and get token
- **registerDevice()**: Register device with backend API
- **setActiveTicket()**: Track currently viewed ticket for suppression
- **Deep linking**: Handle notification taps and navigate to tickets

#### 2. Firebase Configuration (`app/config/firebase.ts`)
Initializes Firebase for Android and iOS platforms.

#### 3. Device Registration
Automatic registration when:
- User logs in successfully
- Push token is available
- User has an assigned administrative location

## Setup Instructions

### Prerequisites

1. **Expo Account**: Sign up at [expo.dev](https://expo.dev)
2. **EAS CLI**: Install with `npm install -g eas-cli`
3. **Firebase Project**: Create project at [firebase.google.com](https://firebase.google.com)

### Backend Setup

#### 1. Environment Variables

Add to `.env` file:

```bash
# Expo Token for Push Notification Service
EXPO_TOKEN=your_expo_access_token_here

# Firebase configuration path (for mobile app)
GOOGLE_SERVICES_JSON=./google-services.json
```

**Getting your Expo Token:**
1. Log in to [expo.dev](https://expo.dev)
2. Navigate to **Account Settings** → **Access Tokens**
3. Create a new token with **"Read and write"** permissions
4. Copy the token and add to `.env`

#### 2. Database Migration

The device table is created automatically via Alembic migration:
```bash
./dc.sh exec backend bash
# Migration runs automatically on startup
```

### Mobile App Setup

#### 1. Firebase Project Setup

**For Android:**
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project or select existing
3. Add an Android app:
   - **Package name**: `com.agriconnect` (must match `app.json`)
   - Download `google-services.json`
   - Place file in `app/google-services.json`

**For iOS:**
1. In Firebase Console, add an iOS app:
   - **Bundle ID**: `com.agriconnect` (must match `app.json`)
   - Download `GoogleService-Info.plist`
   - Place file in `app/GoogleService-Info.plist`

#### 2. Update Environment Variables

Ensure `.env` includes:
```bash
GOOGLE_SERVICES_JSON=./google-services.json
```

#### 3. Configure EAS Build

The `app.json` is already configured with:
```json
{
  "expo": {
    "android": {
      "googleServicesFile": "./google-services.json"
    },
    "ios": {
      "googleServicesFile": "./GoogleService-Info.plist"
    },
    "plugins": [
      [
        "expo-notifications",
        {
          "icon": "./assets/images/notification-icon.png",
          "color": "#ffffff"
        }
      ]
    ]
  }
}
```

#### 4. Build the App

For local development build:
```bash
cd app
./build-android.sh  # For Android
```

For EAS build:
```bash
eas build --platform android --profile preview
```

## Testing Push Notifications

### Local Testing

1. **Start the development environment:**
   ```bash
   ./dc.sh up -d
   ```

2. **Install development build on physical device:**
   - Push notifications **DO NOT work in Expo Go**
   - Use `./build-android.sh` to create a development build
   - Install the APK on your Android device

3. **Log in to the app:**
   - Device will automatically register with backend
   - Check logs for successful registration

4. **Test notification triggers:**
   - Create a new ticket via WhatsApp or web interface
   - Send a message to an existing ticket
   - Verify notifications appear on device

### Debugging

**Check device registration:**
```bash
# View backend logs
./dc.sh logs -f backend

# Look for device registration logs
[Device Registration] ✅ Device registered successfully
```

**Check push notification sending:**
```bash
# Backend logs will show notification attempts
Successfully sent 2 push notifications (batch 1)
```

**Mobile app logs:**
```bash
# Check device logs in development build
adb logcat | grep -E "Notification|Device Registration"
```

## Notification Flow

### New Ticket Created

1. Customer sends WhatsApp message or creates ticket via web
2. Backend creates ticket and first message
3. WebSocket broadcasts `ticket_created` event
4. `PushNotificationService.notify_new_ticket()` called:
   - Gets all devices in ticket's ward
   - Gets all devices in admin wards
   - Sends notification with deep link data:
     ```json
     {
       "type": "ticket_created",
       "ticketNumber": "AG001234",
       "name": "John Farmer",
       "messageId": "42"
     }
     ```
5. Mobile app receives notification:
   - If app in foreground and viewing different ticket → show banner
   - If app in foreground and viewing same ticket → suppress
   - If app in background → show notification
6. User taps notification → deep link to chat screen

### New Message

1. User sends message via mobile app, web, or WhatsApp
2. Backend creates message record
3. WebSocket broadcasts `message_created` event with active viewers
4. `PushNotificationService.notify_new_message()` called:
   - Gets all devices in ticket's ward (excluding sender)
   - Gets all devices in admin wards (excluding sender)
   - Checks if users are actively viewing ticket (via Socket.IO)
   - Sends notification to non-active viewers only
5. Mobile app handles notification (same as above)

## Device-Ward Association Model

Unlike traditional user-device models, AgriConnect uses a **device-administrative area** association:

### Why Device-Ward Association?

- **Shared Devices**: Multiple Extension Officers may use the same device
- **Ward-Based Notifications**: Notifications are sent to all devices in a ward
- **Simplified Management**: No need to track which user is currently using a device

### Device Registration Flow

1. User logs in to mobile app
2. App requests notification permissions
3. App gets Expo push token
4. App registers device with:
   ```json
   {
     "push_token": "ExponentPushToken[...]",
     "administrative_id": 42,  // User's assigned ward
     "app_version": "1.0.0"
   }
   ```
5. Backend creates or updates device record
6. Device is now registered to receive notifications for that ward

### Multiple Users, Same Device

If a different user logs in on the same device:
- Device record is updated with new ward (if different)
- Previous ward association is replaced
- Device continues to receive notifications for new ward

## Troubleshooting

### Notifications Not Received

**Problem**: Device not receiving push notifications

**Solutions**:
1. **Verify device is registered:**
   ```bash
   ./dc.sh exec backend bash
   python -c "from database import SessionLocal; from models.device import Device; db = SessionLocal(); print([(d.id, d.push_token[:30], d.is_active) for d in db.query(Device).all()])"
   ```

2. **Check Expo token format:**
   - Must start with `ExponentPushToken[`
   - Check mobile app logs for token generation

3. **Verify Firebase configuration:**
   - Ensure `google-services.json` exists in `app/` directory
   - Check package name matches: `com.agriconnect`

4. **Check notification permissions:**
   - Android: Settings → Apps → AgriConnect → Notifications → Enabled
   - iOS: Settings → AgriConnect → Notifications → Allow Notifications

5. **Verify using development/production build:**
   - Push notifications **DO NOT** work in Expo Go
   - Use `./build-android.sh` or EAS build

### Invalid Token Errors

**Problem**: Backend logs show `DeviceNotRegistered` errors

**Solution**: This is automatically handled by the backend:
- Invalid tokens are marked as `is_active = false`
- Device will re-register on next app launch
- No manual intervention required

### Notification Suppression Issues

**Problem**: Notifications shown when user is actively viewing ticket

**Solution**: Check active ticket tracking:
1. **Mobile app**: `setActiveTicket()` should be called when entering/leaving chat screen
2. **Backend**: WebSocket should track active viewers via Socket.IO manager
3. **Verify Socket.IO connection**: Check `app/app/chat.tsx:` socket connection logs

### Push Token Not Generated

**Problem**: Mobile app logs show "EAS Project ID not found"

**Solution**:
1. Ensure `app.json` includes:
   ```json
   {
     "extra": {
       "eas": {
         "projectId": "your-project-id"
       }
     }
   }
   ```
2. Get project ID from `eas project:info`
3. Rebuild the app after updating configuration

## API Reference

### Register Device

**Endpoint**: `POST /api/devices`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body**:
```json
{
  "push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
  "administrative_id": 42,
  "app_version": "1.0.0"
}
```

**Response**:
```json
{
  "id": 1,
  "administrative_id": 42,
  "push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
  "app_version": "1.0.0",
  "is_active": true,
  "created_at": "2025-10-14T12:34:56Z",
  "updated_at": "2025-10-14T12:34:56Z"
}
```

### List Devices

**Endpoint**: `GET /api/devices`

**Response**:
```json
[
  {
    "id": 1,
    "administrative_id": 42,
    "push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
    "app_version": "1.0.0",
    "is_active": true,
    "created_at": "2025-10-14T12:34:56Z",
    "updated_at": "2025-10-14T12:34:56Z"
  }
]
```

### Delete Device

**Endpoint**: `DELETE /api/devices/{device_id}`

**Response**: `204 No Content`

## Security Considerations

1. **Token Privacy**: Push tokens are treated as sensitive data
2. **Ward-Based Access**: Users can only register devices for their assigned ward
3. **Token Validation**: Backend validates Expo push token format
4. **HTTPS Only**: All API communication uses HTTPS in production
5. **Token Expiration**: Invalid tokens are automatically deactivated

## Performance

- **Batch Sending**: Up to 100 notifications per API request
- **Retry Logic**: 3 retries with exponential backoff (2s, 4s, 8s)
- **Database Indexing**: `push_token` and `administrative_id` are indexed
- **Token Cleanup**: Invalid tokens automatically marked inactive

## Related Documentation

- [Mobile App Deployment](MOBILE_APP_DEPLOYMENT.md) - Building and deploying the mobile app
- [CLAUDE.md](../CLAUDE.md) - Project architecture and development guidelines
- [Expo Push Notifications](https://docs.expo.dev/push-notifications/overview/) - Official Expo documentation
- [Firebase Cloud Messaging](https://firebase.google.com/docs/cloud-messaging) - FCM documentation
