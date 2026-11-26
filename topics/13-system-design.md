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

### 13.4 Deeper dive: second worked example, a news feed

**Clarified requirements.** Infinite scrolling feed of posts (text, images, short videos), like and comment counts, pull to refresh, offline reading of the last feed, new-post banner. Assume 10M DAU, posts average 2 KB of JSON plus media.

**API.**

```text
GET  /feed?cursor=<opaque>&limit=20      -> { posts: [...], nextCursor: "..." }
GET  /feed/new-count?since=<postId>      -> { count: 7 }        (polled or pushed)
POST /posts/{id}/like                    (idempotent: PUT-like semantics)
```

Cursor pagination is essential: with offset pagination, new posts arriving at the top shift every page and the user sees duplicates.

**Client data flow.**

- `FeedRemoteMediator` (Paging 3) loads pages from the API into Room, storing `nextCursor` in a `RemoteKeys` table.
- The UI reads `PagingData` from Room only, so offline reading and process death are handled for free.
- Pull to refresh calls `refresh()`, which clears the cache table and reloads the first page in one transaction.
- Likes use an optimistic update: write to Room immediately, send in the background, roll back on failure.

**Media.**

- Request image sizes that fit the screen (server provides several resolutions or an image CDN with width parameters).
- Coil with memory + disk caching; prefetch images for the next few items as the user scrolls.
- Video: Media3 ExoPlayer, one shared player instance re-attached to the visible item, autoplay muted only when more than 50% visible and on Wi-Fi or if the user allows it.

**Performance and scale on device.**

- Cap the cached feed (e.g. the last 500 posts) and evict older rows to bound DB size.
- Stable keys and `contentType` in `LazyColumn`; precomputed UI models (formatted dates, counts) so composition is cheap.
- Track scroll jank with JankStats and a Macrobenchmark scroll test.

**Trade-offs to state.** Polling for the new-post count is simple but costs battery; a push or WebSocket only while the app is in the foreground is better at scale. Ranking stays on the server so it can change without an app release.

### 13.5 Deeper dive: quick estimates

Interviewers like you to sanity-check sizes. Show the arithmetic briefly:

- Feed cache: 500 posts x 2 KB = about 1 MB of JSON in Room, which is fine.
- Images: 500 posts x 1 image x 150 KB = 75 MB, so cap the disk cache (e.g. 100-250 MB) and let LRU evict.
- Data use: 20 posts per page x (2 KB + 150 KB) is about 3 MB per page, so prefer smaller images on metered networks.
- Server load: 10M DAU x 10 feed opens x 3 pages = 300M requests per day, about 3,500 per second on average; that is why the client should cache and avoid refetching on every screen visit.

### 13.6 Deeper dive: what a strong answer sounds like

A short sample of the opening minutes:

- **Interviewer:** Design an offline-capable notes app.
- **You:** Before designing, a few questions. Do notes sync across devices? Can two devices edit the same note at the same time? Do notes have attachments? Roughly how many notes per user? Which Android versions?
- **Interviewer:** Yes, sync across devices; concurrent edits are possible but rare; images allowed; up to a few thousand notes.
- **You:** Then the key problems are offline edits and conflicts. I will make Room the source of truth, give every note a `version` and an `updatedAt`, keep an outbox of local changes, and sync with WorkManager. For conflicts I propose last-write-wins per field for title and body, and if both changed I keep both versions and show a conflict copy, which is simple and loses no data. Shall I start with the high-level architecture, then go deep on sync?

Why this works: it clarifies scope, names the hard problem early, proposes a concrete approach with a trade-off, and lets the interviewer steer.

### Interview questions

1. **How do you make sending a message reliable on flaky networks?** Local outbox, WorkManager with backoff, idempotency keys, explicit statuses, and a retry UI for `FAILED` messages. {Hard}
2. **REST vs GraphQL vs gRPC for mobile?** REST is simple and cacheable; GraphQL lets the client fetch exactly what a screen needs in one round trip (good for many screens, varied data); gRPC/protobuf is compact and fast, with streaming, but has weaker tooling for browser/debugging. Choose based on team and backend. {Medium}
3. **How would you design for 10 teams contributing to one app?** Feature modules owned per team, a shared design system, API contracts between modules, convention plugins, CODEOWNERS, feature flags, a release train, and per-module build/test in CI. {Hard}
