# Mobile system design

This round often decides between senior and staff level. You have 45-60 minutes to design an app or feature. Interviewers care more about your process and trade-offs than about the final diagram.

### 13.1 A framework to follow every time

**In one line:** clarify requirements, sketch the high-level design, define the API and data model, go deep on two or three hard parts, then wrap up with trade-offs.

**Say this in the interview:** "Before designing, I'd like to clarify a few things: what users can do, whether it must work offline, whether it's real-time, rough scale, supported devices, and what's out of scope. Then I'll sketch the screens and layers, define the API and local data model, and go deep on the hardest parts, probably offline sync and pagination. I'll finish with trade-offs and how I'd measure and roll it out."

**Example, a time plan:**

1. **Requirements (5 min):** features, offline, real-time, scale, platforms, accessibility, security.
2. **High-level design (10 min):** screens and navigation, modules, UI to ViewModel to repository to local and remote data.
3. **API and data model (10 min):** endpoints or GraphQL queries, pagination, real-time channel, database tables.
4. **Deep dives (15-20 min):** two or three of offline sync, caching, pagination, images, real-time, conflicts, background work, performance, security.
5. **Wrap-up (5 min):** trade-offs, metrics, rollout, what you'd do with more time.

### 13.2 Worked example: a chat app

**In one line:** Room is the source of truth, messages are sent through an outbox with idempotency keys, a WebSocket delivers live updates in the foreground, and push messages trigger sync in the background.

**Say this in the interview:** "The chat screen always reads messages from Room. When the user sends a message, I insert it locally as pending with a client-generated ID, so it shows instantly, and a WorkManager job sends it, using that ID as an idempotency key so retries never duplicate it. While the app is open, a WebSocket delivers new messages and receipts; in the background, a push message triggers a sync of everything since the last cursor, which also fills any gaps. Older messages load with Paging as the user scrolls up."

**Example:**

```kotlin
@Entity(indices = [Index("conversationId", "createdAt")])
data class MessageEntity(
    @PrimaryKey val localId: String,    // UUID created on the device, also the idempotency key
    val serverId: String?,              // null until the server confirms
    val conversationId: String,
    val body: String?,
    val createdAt: Long,
    val status: Status                  // PENDING, SENT, DELIVERED, READ, FAILED
)
```

**Deep-dive points to mention:**

- **Ordering:** sort by server sequence when available, local time for pending messages.
- **Socket lifecycle:** connect when the app comes to the foreground (`ProcessLifecycleOwner`), disconnect in the background, heartbeat, reconnect with exponential backoff and jitter.
- **Notifications:** `MessagingStyle`, direct reply, one group per conversation.
- **Images:** compress and upload first (resumable), then send the message with the media URL.
- **Security:** TLS, pinning for high-risk apps; mention end-to-end encryption as a separate deep topic.

### 13.3 Worked example: a news feed

**In one line:** an infinite feed paged by cursor into Room through a `RemoteMediator`, with images sized for the screen, optimistic likes and a capped local cache.

**Say this in the interview:** "The API returns pages with an opaque cursor, because offset paging duplicates items when new posts arrive at the top. A `RemoteMediator` writes pages into Room, and the UI reads `PagingData` from Room, so offline reading and process death come for free. Pull to refresh clears and reloads the first page in one transaction. Likes are optimistic: written locally first, sent in the background, rolled back on failure. Images come from a CDN at the right width, cached by Coil and prefetched a few items ahead, and I cap the cache at a few hundred posts."

**Example, the API:**

```text
GET  /feed?cursor=<opaque>&limit=20     -> { posts: [...], nextCursor: "..." }
GET  /feed/new-count?since=<postId>     -> { count: 7 }
POST /posts/{id}/like                   (idempotent)
```

**Deep-dive points to mention:** ranking stays on the server so it can change without a release; video uses one shared player that autoplays muted only when mostly visible and the network allows; stable keys and precomputed UI models keep scrolling smooth; JankStats and a Macrobenchmark scroll test track performance.

### 13.4 Quick estimates

**In one line:** do quick arithmetic out loud to show your design fits the device and the network.

**Say this in the interview:** "Let me sanity-check sizes. 500 cached posts at about 2 KB of JSON is 1 MB in Room, which is fine. Images at about 150 KB each would be 75 MB, so I cap the disk cache at 100 to 250 MB and let LRU evict. A 20-post page with images is about 3 MB, so on metered networks I'd request smaller images."

**Example, server-side scale:** 10M daily users x 10 feed opens x 3 pages = 300M requests a day, about 3,500 per second on average. That's a reason for the client to cache and avoid refetching on every visit.

### 13.5 What a strong opening sounds like

**In one line:** clarify scope, name the hardest problem early, propose a concrete approach with its trade-off, and let the interviewer steer.

**Example:**

- **Interviewer:** Design an offline-capable notes app.
- **You:** Before designing, a few questions. Do notes sync across devices? Can two devices edit the same note at the same time? Are there attachments? Roughly how many notes per user?
- **Interviewer:** Yes, they sync; concurrent edits are rare but possible; images are allowed; a few thousand notes.
- **You:** Then the hard parts are offline edits and conflicts. Room is the source of truth, each note has a version and an `updatedAt`, local changes go into an outbox, and WorkManager syncs them. For conflicts I'd use last-write-wins per field, and if both sides changed the same field, keep both and show a conflict copy, so nothing is lost. Shall I start with the overall architecture and then go deep on sync?

### 13.6 Common prompts and what to go deep on

| Prompt | Key deep dives |
| --- | --- |
| Chat app | Outbox and idempotency, WebSocket lifecycle, push-triggered sync, ordering |
| News feed | Cursor pagination, image loading, optimistic likes, cache limits |
| Photo upload or gallery | WorkManager, resumable uploads, thumbnails, memory limits |
| Ride-hailing | Location updates, foreground service, real-time tracking, battery |
| Checkout | State machine, payment SDK, idempotency, process death mid-checkout |
| Offline notes or to-do | Sync engine, conflict resolution, full-text search |
| Video streaming | Media3, adaptive bitrate, downloads, picture-in-picture |
| Analytics SDK | Batching, persistence, upload windows, small footprint, privacy |
| Image loading library | Memory and disk LRU caches, request deduplication, cancellation, downsampling |

### Interview questions

1. **How do you approach a mobile system design question?** Clarify requirements, sketch the high-level design, define the API and data model, go deep on two or three hard parts, and finish with trade-offs, metrics and rollout. {Easy}
2. **How do you make sending a chat message reliable on a flaky network?** Save it locally as pending, send it with WorkManager and backoff, use the client-generated ID as an idempotency key, track status explicitly, and offer retry for failed messages. {Medium}
3. **Why use cursor pagination for a feed?** New posts arriving at the top shift offsets and cause duplicates or gaps; a cursor points at a specific item, so pages stay stable. {Medium}
4. **REST, GraphQL or gRPC for a mobile app?** REST is simple and cacheable; GraphQL fetches exactly what each screen needs in one request; gRPC is compact and fast with streaming but harder to debug. Choose based on the team and backend. {Medium}
5. **How would you resolve conflicts when two devices edit the same note offline?** Give each record a version and timestamps, sync through an outbox, and use a clear rule, such as last-write-wins per field, keeping a conflict copy when both changed the same field so no data is lost. {Hard}
6. **How would you design an app that 10 teams contribute to?** Feature modules owned by teams, a shared design system, clear module contracts, convention plugins, code owners, feature flags, a release train and per-module CI. {Hard}
7. **How do you keep real-time updates battery-friendly?** Keep a WebSocket only while the app is in the foreground, use push messages to trigger syncs in the background, and reconnect with exponential backoff and jitter. {Medium}
