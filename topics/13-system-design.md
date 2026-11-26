# Mobile system design

This round decides senior vs staff level. You have 45-60 minutes to design a feature or app. The interviewer cares about your **process and trade-offs** more than the final diagram.

### 13.1 A repeatable framework (talk through it aloud)

1. **Clarify requirements (5 min).** Functional: what can the user do? Non-functional: offline support, real-time, scale (DAU, data size), supported devices/OS, accessibility, i18n, security. Out of scope.
2. **High-level design (10 min).** Screens and navigation, client modules, the layers (UI → ViewModel → repository → local/remote).
3. **API and data model (10 min).** Endpoints or GraphQL queries, pagination, real-time channel, DB schema, models.
4. **Deep dives (15-20 min).** Pick 2-3: offline sync, caching, pagination, image loading, real-time updates, conflict resolution, background work, performance, security.
5. **Trade-offs and wrap-up (5 min).** What you would measure, how you would roll out, what you would do with more time.

### 13.2 Worked example: design a chat app (like WhatsApp)

**Requirements.** 1:1 and group chat, text + images, offline reading and sending, delivery and read receipts, push notifications, message history with pagination. Non-functional: messages must never be lost, appear in < 1 s when online, work on poor networks, battery friendly.

**Client architecture.**

- `:feature:conversations`, `:feature:chat`, `:core:data`, `:core:database`, `:core:network`, `:core:sync`.
- **Room is the single source of truth.** The chat screen observes `messageDao.observe(conversationId)`.
- A **WebSocket** (OkHttp) carries new messages and receipts while the app is in the foreground; **FCM** wakes the app in the background to sync.

**Data model.**

```kotlin
@Entity(indices = [Index("conversationId", "createdAt")])
data class MessageEntity(
    @PrimaryKey val localId: String,      // UUID created on device
    val serverId: String?,                // null until server acks
    val conversationId: String,
    val senderId: String,
    val body: String?,
    val mediaUri: String?,
    val createdAt: Long,
    val status: Status                    // PENDING, SENT, DELIVERED, READ, FAILED
)
```

**Sending a message (outbox pattern).**

1. Insert the message with `status = PENDING` and a client-generated UUID; the UI shows it instantly.
2. Enqueue a unique `SendMessageWorker` (network constraint, exponential backoff).
3. The worker sends it with the UUID as an **idempotency key**, so a retry never duplicates the message.
4. On server ack, update `serverId` and `status = SENT`. Receipts over the socket update DELIVERED / READ.
5. Images: compress and upload first (resumable/chunked upload), then send the message with the media URL.

**Receiving and syncing.** Keep a per-conversation `lastSyncedCursor`. On reconnect or FCM push, fetch `GET /messages?since=cursor` and upsert. This closes gaps from missed socket events.

**Pagination.** Paging 3 with `RemoteMediator`: load the latest page from the DB first, fetch older pages by cursor as the user scrolls up.

**Deep-dive talking points.**

- Ordering: sort by server timestamp/sequence when available, fall back to local `createdAt` for pending messages.
- Socket lifecycle: connect in `ProcessLifecycleOwner` ON\_START, disconnect ON\_STOP; heartbeat; reconnect with exponential backoff + jitter; observe `ConnectivityManager` callbacks.
- Notifications: `MessagingStyle`, direct reply via `RemoteInput`, grouping per conversation, notification channels.
- Security: TLS + certificate pinning; mention end-to-end encryption (Signal protocol) as a deep topic.
- Performance: `LazyColumn` with `reverseLayout`, stable keys, image thumbnails, DB indices.
- Scale on device: prune old media from cache, keep text forever; DB size monitoring.

### 13.3 Other common prompts and their key deep dives

| Prompt | Key deep dives |
| --- | --- |
| News feed / Instagram | Pagination, prefetching, image caching, feed ranking from server, video autoplay, offline cache |
| Image gallery / photo upload | Large uploads, WorkManager, resumable uploads, thumbnails, memory limits |
| Ride-hailing (Uber) driver/rider | Location updates (fused provider, foreground service), maps, real-time tracking, battery |
| E-commerce checkout | State machine, payment SDK, idempotency, process death in checkout, deep links |
| Offline-first notes / to-do | Sync engine, conflict resolution (CRDT / last-write-wins / version vectors), search (FTS) |
| Video streaming (YouTube) | ExoPlayer/Media3, adaptive bitrate (HLS/DASH), downloads, PiP, background playback |
| Analytics SDK | Batching, persistence, upload windows, tiny footprint, thread safety, privacy |
| Image loading library | Memory + disk cache (LRU), request deduplication, cancellation, downsampling, bitmap pooling |

### Interview questions

1. **How do you make sending a message reliable on flaky networks?** Local outbox, WorkManager with backoff, idempotency keys, explicit statuses, and a retry UI for `FAILED` messages. {Hard}
2. **REST vs GraphQL vs gRPC for mobile?** REST is simple and cacheable; GraphQL lets the client fetch exactly what a screen needs in one round trip (good for many screens, varied data); gRPC/protobuf is compact and fast, with streaming, but has weaker tooling for browser/debugging. Choose based on team and backend. {Medium}
3. **How would you design for 10 teams contributing to one app?** Feature modules owned per team, a shared design system, API contracts between modules, convention plugins, CODEOWNERS, feature flags, a release train, and per-module build/test in CI. {Hard}
