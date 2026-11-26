# Data layer: networking, storage and offline-first

The data layer owns your app's data. Interviewers check that you can load it efficiently, store it in the right place, keep it in sync, and handle the network failing.

### 7.1 Retrofit and OkHttp

**In one line:** OkHttp is the HTTP client that does the actual networking; Retrofit turns an annotated Kotlin interface into HTTP calls on top of it.

**Say this in the interview:** "I declare the API as an interface with suspend functions, and Retrofit generates the implementation. OkHttp underneath handles connection pooling, HTTP/2, compression, caching and interceptors. I use kotlinx.serialization or Moshi rather than Gson, because Gson uses reflection and ignores Kotlin nullability and default values. Interceptors add things like auth headers and logging to every request."

**Example:**

```kotlin
interface ArticleApi {
    @GET("articles") suspend fun getArticles(@Query("page") page: Int, @Query("size") size: Int = 20): List<ArticleDto>
    @POST("articles/{id}/like") suspend fun like(@Path("id") id: String): Response<Unit>
}

class AuthInterceptor @Inject constructor(private val tokens: TokenStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response =
        chain.proceed(chain.request().newBuilder().header("Authorization", "Bearer ${tokens.accessToken()}").build())
}
```

**Common mistake:** Creating a new `OkHttpClient` for each request, which loses connection and thread reuse.

**Follow-ups:**

- *Application vs network interceptor?* An application interceptor (`addInterceptor`) runs once and sees the original request; a network interceptor (`addNetworkInterceptor`) sees redirects and what actually goes over the network.

### 7.2 Refreshing tokens safely

**In one line:** when the server returns 401, OkHttp's `Authenticator` refreshes the token once and retries, even if many requests fail at the same moment.

**Say this in the interview:** "I use an `Authenticator`, which OkHttp calls on a 401. The tricky part is concurrency: if five requests fail together, only one should refresh. So I take a lock, check whether another thread already refreshed the token, and if so just retry with the new one; otherwise I refresh. If the refresh fails, I clear the session and send the user to sign in, and I never retry more than once to avoid loops."

**Example:**

```kotlin
override fun authenticate(route: Route?, response: Response): Request? {
    if (response.priorResponse != null) return null                       // already retried: give up
    synchronized(this) {
        val current = tokens.accessToken()
        val sent = response.request.header("Authorization")?.removePrefix("Bearer ")
        if (sent != current) return response.request.withToken(current)    // someone else refreshed
        val fresh = runCatching { authApi.get().refreshBlocking(tokens.refreshToken()) }.getOrNull()
            ?: run { tokens.clear(); return null }                          // refresh failed: sign out
        tokens.save(fresh)
        return response.request.withToken(fresh.accessToken)
    }
}
```

**Common mistake:** Letting every failed request start its own token refresh.

**Follow-ups:**

- *How do you stop endless refresh attempts?* Give up when the request has already been retried or the refresh fails, then ask the user to sign in again.

### 7.3 Room

**In one line:** Room is a SQLite library that checks your SQL at compile time and returns results as suspend functions or Flows.

**Say this in the interview:** "I define entities, DAOs and a database class. DAO queries that return `Flow` re-emit whenever the table changes, which is what makes the database a live single source of truth. I use `@Transaction` for multi-step writes and `@Relation` for one-to-many reads. For schema changes I write migrations, export the schema and test migrations with `MigrationTestHelper`; I never use destructive migration for user data."

**Example:**

```kotlin
@Entity(tableName = "articles", indices = [Index("topic")])
data class ArticleEntity(@PrimaryKey val id: String, val title: String, val topic: String, val publishedAt: Long)

@Dao interface ArticleDao {
    @Query("SELECT * FROM articles ORDER BY publishedAt DESC") fun observeAll(): Flow<List<ArticleEntity>>
    @Upsert suspend fun upsertAll(items: List<ArticleEntity>)
}

val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(db: SupportSQLiteDatabase) { db.execSQL("ALTER TABLE articles ADD COLUMN likes INTEGER NOT NULL DEFAULT 0") }
}
```

**Common mistake:** Using a destructive migration for tables that hold user data.

**Follow-ups:**

- *Room's Flow emits when unrelated rows change. Fix?* Add `distinctUntilChanged()` after mapping, or narrow the query.
- *Simple schema changes?* `@AutoMigration(from = 1, to = 2)` handles added columns and tables; renames need an `AutoMigrationSpec`.

### 7.4 DataStore vs SharedPreferences

**In one line:** DataStore is the modern replacement for SharedPreferences: asynchronous, transactional and Flow-based.

**Say this in the interview:** "SharedPreferences reads synchronously on first access and `apply()` can still block during lifecycle changes, which is a known ANR source, and it has no error handling. Preferences DataStore exposes data as a Flow and writes in transactions with coroutines; Proto DataStore adds a typed schema. The one rule is a single DataStore instance per file per process, so I create it as a top-level delegate or a singleton."

**Example:**

```kotlin
val Context.settings by preferencesDataStore(name = "settings")
val DARK_MODE = booleanPreferencesKey("dark_mode")

val darkMode: Flow<Boolean> = context.settings.data.map { it[DARK_MODE] ?: false }
suspend fun setDarkMode(on: Boolean) = context.settings.edit { it[DARK_MODE] = on }
```

**Common mistake:** Creating more than one DataStore instance for the same file.

**Follow-ups:**

- *When would you use Room instead of DataStore?* For larger or relational data, queries or partial updates. DataStore suits small sets of settings.

### 7.5 Offline-first repositories and sync

**In one line:** in an offline-first app the UI always reads from the local database, the network only updates the database, and local changes are queued and synced later.

**Say this in the interview:** "For reads, the repository exposes Room as a Flow and refreshes from the network in the background, so cached data shows instantly. For writes, I save the change locally with a 'pending' flag, so the UI updates immediately, and a WorkManager job pushes pending changes when there's a connection. Each change carries an idempotency key, so a retry never applies it twice, and I resolve conflicts with timestamps or versions, choosing a strategy like last-write-wins per field."

**Example:**

```kotlin
override suspend fun setBookmarked(id: String, on: Boolean) {
    dao.setBookmarked(id, on, syncState = SyncState.PENDING)   // UI updates through Room's Flow
    syncScheduler.requestSync()                                // WorkManager, network constraint
}
```

**Common mistake:** Updating the UI from the network response and treating the database as a second copy.

**Follow-ups:**

- *How do you avoid duplicate requests when two screens ask for the same data?* Share the in-flight request: keep a `Deferred` behind a `Mutex`, launched in an application scope so one caller leaving doesn't cancel it for the others.

### 7.6 Caching strategies

**In one line:** choose a cache strategy per kind of data, based on how fresh it must be.

**Say this in the interview:** "For feeds I show the database first and refresh in the background. For prices or balances I try the network first and fall back to the cache. For config I store a fetched-at time and refresh when it's older than a TTL. Static resources use the HTTP cache with ETags. And hot data within a session can sit in an in-memory LRU cache."

**Example:**

| Strategy | How | Good for |
| --- | --- | --- |
| Cache, then network | Show DB, refresh in background | Feeds, lists |
| Network first | Try network, fall back to DB | Prices, balances |
| TTL | Refresh if older than N minutes | Config, profiles |
| HTTP cache | OkHttp `Cache` + `Cache-Control`/`ETag` | Images, static data |
| In memory | `LruCache` or a map in the repository | Hot data in one session |

**Common mistake:** Using one caching rule for all data, however fresh each kind must be.

**Follow-ups:**

- *What does stale-while-revalidate mean?* Show the cached data at once, then refresh it in the background and update the screen.

### 7.7 Paging 3

**In one line:** Paging 3 loads large lists page by page, with loading and error states, retries and caching built in.

**Say this in the interview:** "For a network-plus-database list I use a `RemoteMediator`, which writes pages from the API into Room, and Room's `PagingSource` feeds the UI. That keeps the database as the source of truth, even for paged data. `cachedIn(viewModelScope)` keeps loaded pages across rotation. On the backend I prefer cursor pagination over offsets, because new items at the top shift offsets and cause duplicates."

**Example:**

```kotlin
val articles: Flow<PagingData<Article>> = Pager(
    config = PagingConfig(pageSize = 20),
    remoteMediator = ArticleRemoteMediator(api, db),
    pagingSourceFactory = { db.articleDao().pagingSource() }
).flow.map { it.map(ArticleEntity::toDomain) }.cachedIn(viewModelScope)
```

**Common mistake:** Invalidating or recreating the pager on every recomposition, so pages reload and scroll position is lost.

**Follow-ups:**

- *What does `RemoteMediator` do?* It loads more data from the network into the local database when paging needs it. The UI still pages from the database.

### 7.8 Choosing where to store data

**In one line:** private app data goes in app-specific storage, Room or DataStore; media the user should see goes through `MediaStore`; documents they own go through the system file picker.

**Say this in the interview:** "Since Android 10, apps have scoped storage: they see their own app-specific directory and the media they created. App-specific files need no permission and are removed on uninstall. To save a photo into the gallery, I insert it through `MediaStore`, which needs no permission for my own media. For documents like an exported PDF, I let the user choose the location with the Storage Access Framework. To pick images, I use the Photo Picker, which needs no storage permission at all."

**Example:**

| Data | Where | Permission | Removed on uninstall |
| --- | --- | --- | --- |
| Private files, cache | `filesDir`, `cacheDir` | None | Yes |
| Settings | DataStore | None | Yes |
| Records you query | Room | None | Yes |
| Photos and videos for the gallery | `MediaStore` | None for your own media | No |
| User documents | Storage Access Framework (`CreateDocument`) | None | No |

**Common mistake:** Saving files to shared storage and requesting broad access when app-specific storage is enough.

**Follow-ups:**

- *What happens to app-specific files on uninstall?* They are removed. Files added to shared collections such as `MediaStore` normally stay.

### 7.9 Network connectivity

**In one line:** use `ConnectivityManager` with a `NetworkCallback` to react to network changes; the old broadcast and `NetworkInfo` APIs are deprecated.

**Say this in the interview:** "I register a `NetworkCallback` for networks with internet capability and wrap it in a `callbackFlow`. I handle `onCapabilitiesChanged` too, because a network can switch between metered and unmetered while staying connected. Being connected doesn't mean the internet works, so I check the validated capability and still treat every request as able to fail. I use connectivity for UX, like an offline banner, not as a gate before requests."

**Example:**

```kotlin
fun Context.isOnline(): Flow<Boolean> = callbackFlow {
    val cm = getSystemService(ConnectivityManager::class.java)
    val cb = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(n: Network) { trySend(true) }
        override fun onLost(n: Network) { trySend(false) }
    }
    cm.registerNetworkCallback(NetworkRequest.Builder().addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET).build(), cb)
    awaitClose { cm.unregisterNetworkCallback(cb) }
}.distinctUntilChanged()
```

**Common mistake:** Treating a connected network as proof that a request will succeed.

**Follow-ups:**

- *How do you check whether a network has working internet?* Look for the validated network capability, and still handle request failures.

### Interview questions

1. **Why use kotlinx.serialization or Moshi instead of Gson?** Gson uses reflection and ignores Kotlin nullability and default values, so a missing field can put `null` into a non-null property. The others are Kotlin-aware and generate code. {Medium}
2. **How do you refresh an expired token when several requests fail with 401 at once?** Use an OkHttp `Authenticator` with a lock: the first thread refreshes, the others see the token changed and simply retry. Give up after one retry and sign out if the refresh fails. {Hard}
3. **How do you make an API call survive the user leaving the screen?** Don't tie it to `viewModelScope`. Use an injected application scope for short work, or WorkManager for work that must finish. {Medium}
4. **Why is DataStore preferred over SharedPreferences?** SharedPreferences can block the main thread and has no error handling. DataStore is asynchronous, transactional and exposes data as a Flow. {Easy}
5. **How does an offline-first write work?** Save the change locally with a pending flag so the UI updates at once, then a WorkManager job syncs it with an idempotency key when the network is available, and resolves conflicts with versions or timestamps. {Medium}
6. **How do you avoid two screens sending the same request?** Share the in-flight request: keep one `Deferred` behind a `Mutex`, or expose one hot flow from the repository with `shareIn`. {Medium}
7. **How do you handle a Room migration safely?** Export schemas, write a migration (or `@AutoMigration` for simple changes), test it with `MigrationTestHelper` in CI, and never use destructive migration for user data. {Medium}
8. **Why prefer cursor pagination over offset pagination?** New items arriving at the top shift offsets, causing duplicates or skipped items. A cursor points at a specific item, so pages stay stable. {Medium}
9. **Where would you save an exported PDF, a thumbnail cache and a photo for the gallery?** The PDF where the user chooses, through the Storage Access Framework; the thumbnail in `cacheDir`; the photo through `MediaStore`. None of these needs a storage permission. {Medium}
10. **How do you know the device is online?** Register a `NetworkCallback` for internet capability, react to `onAvailable`, `onLost` and `onCapabilitiesChanged`, and still treat every request as able to fail. {Easy}
