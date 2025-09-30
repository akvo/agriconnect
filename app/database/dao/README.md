# DAO Layer Documentation

## Overview

The DAO (Data Access Object) layer provides a clean, organized way to interact with the SQLite database in your Expo/React Native app. It separates database logic from UI components and provides type-safe database operations.

## Architecture

```
database/
├── dao/
│   ├── types/           # TypeScript interfaces for all entities
│   ├── base.ts          # Base DAO class with common operations
│   ├── eoUserDAO.ts     # EO User database operations
│   ├── customerUserDAO.ts # Customer User database operations
│   ├── messageDAO.ts    # Message database operations
│   ├── syncLogDAO.ts    # Sync Log database operations
│   ├── utils.ts         # High-level utility functions
│   ├── index.ts         # DAO Manager and exports
│   └── DatabaseExampleScreen.tsx # Usage examples
```

## Quick Start

### Basic Usage

```typescript
import { dao, getInbox, saveProfile } from '@/database/dao';

// Get all EO users
const users = dao.eoUser.findAll();

// Get inbox for an EO
const inbox = getInbox(eoId, 20);

// Save a user profile
const user = await saveProfile.eoUser({
  email: 'user@example.com',
  phone_number: '+1234567890',
  full_name: 'John Doe'
});
```

### DAO Manager

The `DAOManager` provides centralized access to all database operations:

```typescript
import { dao } from '@/database/dao';

// Access different DAOs
dao.eoUser.findById(1);
dao.customerUser.searchByName('John');
dao.message.getConversation(customerId, eoId);
dao.syncLog.startSync('manual');
```

## Available Operations

### EO User DAO

```typescript
// CRUD operations
dao.eoUser.create(data);
dao.eoUser.findById(id);
dao.eoUser.findAll();
dao.eoUser.update(id, data);
dao.eoUser.delete(id);

// Specific queries
dao.eoUser.findByEmail(email);
dao.eoUser.findByPhoneNumber(phone);
dao.eoUser.findByAuthToken(token);
dao.eoUser.findActiveUsers();
dao.eoUser.updateAuthToken(id, token);
dao.eoUser.activate(id);
dao.eoUser.deactivate(id);
```

### Customer User DAO

```typescript
// CRUD operations
dao.customerUser.create(data);
dao.customerUser.findById(id);
dao.customerUser.findAll();
dao.customerUser.update(id, data);
dao.customerUser.delete(id);

// Specific queries
dao.customerUser.findByPhoneNumber(phone);
dao.customerUser.searchByName(name);
dao.customerUser.findByLanguage(language);
dao.customerUser.findRecent(limit);
dao.customerUser.updateLanguage(id, language);
```

### Message DAO

```typescript
// CRUD operations
dao.message.create(data);
dao.message.findById(id);
dao.message.findAll();
dao.message.update(id, data);
dao.message.delete(id);

// Messaging features
dao.message.getInbox(eoId, limit);
dao.message.getConversation(customerId, eoId, limit);
dao.message.getMessagesByCustomer(customerId, limit);
dao.message.getMessagesByEO(eoId, limit);
dao.message.findByMessageSid(sid);
dao.message.getRecentMessages(limit);
dao.message.searchMessages(query, limit);
```

### Sync Log DAO

```typescript
// CRUD operations
dao.syncLog.create(data);
dao.syncLog.findById(id);
dao.syncLog.findAll();
dao.syncLog.update(id, data);
dao.syncLog.delete(id);

// Sync management
dao.syncLog.startSync(type, details);
dao.syncLog.completeSync(id, details);
dao.syncLog.failSync(id, errorDetails);
dao.syncLog.findByStatus(status, limit);
dao.syncLog.findBySyncType(type, limit);
dao.syncLog.getPendingSyncs();
dao.syncLog.getInProgressSyncs();
dao.syncLog.getFailedSyncs();
dao.syncLog.getLastSuccessfulSync(type);
dao.syncLog.cleanupOldLogs(keepCount);
```

## High-Level Utility Functions

### Profile Management

```typescript
import { saveProfile } from '@/database/dao';

// Save EO user profile
const eoUser = await saveProfile.eoUser({
  email: 'user@example.com',
  phone_number: '+1234567890',
  full_name: 'John Doe',
  user_type: 'eo'
});

// Update existing profile
const updatedUser = await saveProfile.eoUser({
  id: 1,
  full_name: 'John Smith'
});
```

### Messaging

```typescript
import { getInbox, getMessages, sendMessage } from '@/database/dao';

// Get inbox conversations
const conversations = getInbox(eoId, 20);

// Get conversation messages
const messages = getMessages(customerId, eoId, 50);

// Send a new message
const message = sendMessage({
  from_source: '+1234567890',
  message_sid: 'whatsapp_sid_123',
  customer_id: 1,
  eo_id: 2,
  body: 'Hello, how can I help you?',
  message_type: 'text'
});
```

### User Search

```typescript
import { findUser, searchCustomers } from '@/database/dao';

// Find user by email
const user = findUser.byEmail('user@example.com');

// Find user by phone (checks both EO and customer)
const userResult = findUser.byPhone('+1234567890');
if (userResult) {
  console.log(`Found ${userResult.type} user:`, userResult.user);
}

// Search customers by name
const customers = searchCustomers('John');
```

### Sync Operations

```typescript
import { syncOperations } from '@/database/dao';

// Start a sync operation
const syncLog = syncOperations.start('full_sync', 'Syncing all data');

// Complete the sync
if (syncLog) {
  syncOperations.complete(syncLog.id, 'Successfully synced 100 records');
}

// Handle sync failure
// syncOperations.fail(syncLog.id, 'Network error occurred');

// Get sync status
const pendingSyncs = syncOperations.getPending();
const recentSyncs = syncOperations.getRecent(10);
```

### Statistics

```typescript
import { getStats } from '@/database/dao';

const stats = getStats();
console.log('Database stats:', {
  totalEoUsers: stats.totalEoUsers,
  totalCustomers: stats.totalCustomers,
  totalMessages: stats.totalMessages,
  activeEoUsers: stats.activeEoUsers
});
```

## React Component Usage

```typescript
import React, { useEffect, useState } from 'react';
import { dao, getInbox } from '@/database/dao';
import { ConversationSummary } from '@/database/dao/types';

const InboxScreen: React.FC = () => {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadInbox();
  }, []);

  const loadInbox = () => {
    try {
      const eoId = 1; // Get from auth context
      const inbox = getInbox(eoId, 20);
      setConversations(inbox);
    } catch (error) {
      console.error('Error loading inbox:', error);
    } finally {
      setLoading(false);
    }
  };

  // Rest of component...
};
```

## Error Handling

All DAO operations include proper error handling:

```typescript
try {
  const user = dao.eoUser.create(userData);
  console.log('User created:', user);
} catch (error) {
  console.error('Failed to create user:', error);
  // Handle error appropriately
}
```

## Type Safety

All operations are fully typed with TypeScript interfaces:

```typescript
import { EoUser, CreateEoUserData, ConversationSummary } from '@/database/dao/types';

const createUser = (data: CreateEoUserData): EoUser => {
  return dao.eoUser.create(data);
};
```

## Best Practices

1. **Use High-Level Utils**: Prefer `getInbox()`, `saveProfile.eoUser()` over direct DAO calls for common operations

2. **Error Handling**: Always wrap database operations in try-catch blocks

3. **Type Safety**: Use provided TypeScript interfaces for type safety

4. **Performance**: Use appropriate limits on queries to avoid loading too much data

5. **Singleton Pattern**: The DAOManager uses singleton pattern - always use `dao` export

6. **Testing**: Use `DAOManager.resetInstance()` in tests to ensure clean state

## Migration Compatibility

The DAO layer is designed to work with the migration system. When database schema changes:

1. Update the migration files
2. Update corresponding type interfaces
3. Update DAO methods if needed
4. Test thoroughly

## Performance Tips

- Use appropriate LIMIT clauses for large datasets
- Consider pagination for message lists
- Use indexes (already created in migrations)
- Clean up old sync logs periodically
- Use transactions for bulk operations when needed
