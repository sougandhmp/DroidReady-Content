# Data layer: networking, persistence, offline-first

### 7.1 Retrofit and OkHttp

- **OkHttp** is the HTTP client: connection pooling, HTTP/2, GZIP, caching, interceptors.
- **Retrofit** turns an interface into HTTP calls; supports `suspend` functions directly.
- Use **kotlinx.serialization** or Moshi (codegen) rather than Gson (reflection, ignores Kotlin nullability and default values).

```kotlin
interface ArticleApi {
    @GET("articles")
    suspend fun getArticles(@Query("page") page: Int, @Query("size") size: Int = 20): List<ArticleDto>

    @POST("articles/{id}/like")
    suspend fun like(@Path("id") id: String): Response<Unit>
}
```

**Interceptors** - application interceptors (`addInterceptor`, run once, see the original request) vs network interceptors (`addNetworkInterceptor`, see redirects and real network traffic).

```kotlin
class AuthInterceptor @Inject constructor(private val tokens: TokenStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val req = chain.request().newBuilder()
            .header("Authorization", "Bearer ${tokens.accessToken()}").build()
        return chain.proceed(req)
    }
}
```

**Token refresh:** use OkHttp's `Authenticator`, which is called on a 401. Synchronise it so 10 parallel 401s trigger **one** refresh (a `Mutex` or `synchronized` block, re-check whether the token already changed), then retry. Give up after one retry to avoid loops.

**Error handling:** map exceptions into a domain result type at the repository boundary.

```kotlin
sealed interface NetworkResult<out T> {
    data class Success<T>(val data: T) : NetworkResult<T>
    data class HttpError(val code: Int, val body: String?) : NetworkResult<Nothing>
    data class NetworkError(val cause: IOException) : NetworkResult<Nothing>
}
```

### 7.2 Room

```kotlin
@Entity(tableName = "articles", indices = [Index("topic")])
data class ArticleEntity(
    @PrimaryKey val id: String,
    val title: String,
    val topic: String,
    val publishedAt: Long,
    val isBookmarked: Boolean = false
)

@Dao
interface ArticleDao {
    @Query("SELECT * FROM articles ORDER BY publishedAt DESC")
    fun observeAll(): Flow<List<ArticleEntity>>           // re-emits when the table changes

    @Upsert suspend fun upsertAll(items: List<ArticleEntity>)

    @Transaction
    suspend fun replaceAll(items: List<ArticleEntity>) { deleteAll(); upsertAll(items) }

    @Query("DELETE FROM articles") suspend fun deleteAll()
}
```

Things to know: migrations (`Migration(1, 2)` or `@AutoMigration`), export schemas and test migrations with `MigrationTestHelper`; `@Relation` for one-to-many; `@TypeConverter` for custom types; FTS tables for search; WAL mode is on by default; never call DB on main (Room throws). Room 2.7+ supports Kotlin Multiplatform.

### 7.3 DataStore vs SharedPreferences

- `SharedPreferences`: synchronous reads on first access, `apply()` can still block on `onPause`/`onStop` (a known ANR source), no error signalling, not type-safe.
- **Preferences DataStore:** async Flow API, transactional, coroutine-based.
- **Proto DataStore:** typed schema with protobuf.
- Only **one** DataStore instance per file per process (create it as a top-level `by preferencesDataStore` delegate or a singleton).

```kotlin
val Context.settings by preferencesDataStore(name = "settings")
val DARK_MODE = booleanPreferencesKey("dark_mode")

val darkMode: Flow<Boolean> = context.settings.data.map { it[DARK_MODE] ?: false }
suspend fun setDarkMode(on: Boolean) = context.settings.edit { it[DARK_MODE] = on }
```

### 7.4 Offline-first repository

The UI reads from the database; the network refreshes the database. A complete pattern:

```kotlin
class OfflineFirstArticleRepository @Inject constructor(
    private val api: ArticleApi,
    private val dao: ArticleDao,
    @IoDispatcher private val io: CoroutineDispatcher
) : ArticleRepository {

    override fun observeAll(): Flow<List<Article>> =
        dao.observeAll().map { list -> list.map { it.toDomain() } }

    override suspend fun refresh(): Result<Unit> = withContext(io) {
        runCatching {
            val remote = api.getArticles(page = 0)
            dao.upsertAll(remote.map { it.toEntity() })
        }.onFailure { if (it is CancellationException) throw it }
    }
}
```

**Writes offline:** store the change locally with a `syncState = PENDING` flag (or an outbox table), update the UI immediately (optimistic update), and let a WorkManager job push pending changes when connected. Resolve conflicts with timestamps / version numbers, "last write wins", or server-side merge, and say which you chose and why.

### 7.5 Caching strategies

| Strategy | How | Good for |
| --- | --- | --- |
| Cache-then-network | Show DB, refresh in background | Feeds, lists |
| Network-first with fallback | Try network, fall back to DB on failure | Prices, balances |
| TTL / stale-while-revalidate | Store `fetchedAt`; refresh if older than N minutes | Config, profiles |
| HTTP cache | OkHttp `Cache` + `Cache-Control` / `ETag` headers | Static resources, images |
| In-memory | `LruCache` or a `Map` in the repository with a `Mutex` | Hot data within a session |

### 7.6 Paging 3

Loads large lists in pages with built-in loading/error states, retry and placeholders.

```kotlin
// Network + DB: RemoteMediator writes pages into Room; Room's PagingSource feeds the UI
val articles: Flow<PagingData<Article>> = Pager(
    config = PagingConfig(pageSize = 20, prefetchDistance = 5, enablePlaceholders = false),
    remoteMediator = ArticleRemoteMediator(api, db),
    pagingSourceFactory = { db.articleDao().pagingSource() }
).flow.map { it.map(ArticleEntity::toDomain) }.cachedIn(viewModelScope)

// Compose
val items = viewModel.articles.collectAsLazyPagingItems()
LazyColumn {
    items(count = items.itemCount, key = items.itemKey { it.id }) { i -> items[i]?.let { ArticleRow(it) } }
}
```

`cachedIn` keeps loaded pages across configuration changes. Prefer **cursor/keyset pagination** on the backend over offset pagination (stable under inserts).

### 7.7 Images and real-time

- **Coil** (Kotlin-first, coroutine-based, Compose support) or Glide: memory + disk cache, downsampling to view size, lifecycle-aware requests.
- **Real-time:** WebSockets (OkHttp), Server-Sent Events, or FCM push to trigger a sync. Polling only as a fallback. Reconnect with exponential backoff and jitter.

### 7.8 Deeper dive: a token-refresh Authenticator

OkHttp calls an `Authenticator` when a response is 401. The tricky part is that several requests can fail at the same moment.

```kotlin
class TokenAuthenticator @Inject constructor(
    private val tokens: TokenStore,
    private val authApi: Provider<AuthApi>   // Provider avoids a dependency cycle with OkHttpClient
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.priorResponse != null) return null          // already retried once: give up

        synchronized(this) {
            val current = tokens.accessToken()
            val sent = response.request.header("Authorization")?.removePrefix("Bearer ")
            if (sent != current) {
                // another thread refreshed while we waited: just retry with the new token
                return response.request.withToken(current)
            }
            val refreshed = runCatching { authApi.get().refreshBlocking(tokens.refreshToken()) }.getOrNull()
                ?: run { tokens.clear(); return null }             // refresh failed: user must sign in again
            tokens.save(refreshed)
            return response.request.withToken(refreshed.accessToken)
        }
    }

    private fun Request.withToken(t: String) = newBuilder().header("Authorization", "Bearer $t").build()
}
```

Walk through it: five requests get 401 together. The first thread enters the lock and refreshes. The other four wait, then see the token changed and retry without refreshing again. If refresh fails, return `null` and emit a "session expired" event so the UI goes to sign-in.

### 7.9 Deeper dive: Room relations and a migration

```kotlin
@Entity data class AuthorEntity(@PrimaryKey val id: String, val name: String)

@Entity(foreignKeys = [ForeignKey(entity = AuthorEntity::class, parentColumns = ["id"], childColumns = ["authorId"], onDelete = ForeignKey.CASCADE)],
        indices = [Index("authorId")])
data class PostEntity(@PrimaryKey val id: String, val authorId: String, val title: String)

data class AuthorWithPosts(
    @Embedded val author: AuthorEntity,
    @Relation(parentColumn = "id", entityColumn = "authorId") val posts: List<PostEntity>
)

@Dao interface AuthorDao {
    @Transaction   // Room runs 2 queries; the transaction keeps them consistent
    @Query("SELECT * FROM AuthorEntity WHERE id = :id")
    fun observeWithPosts(id: String): Flow<AuthorWithPosts>
}
```

Adding a column in version 2:

```kotlin
val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("ALTER TABLE PostEntity ADD COLUMN likes INTEGER NOT NULL DEFAULT 0")
    }
}

Room.databaseBuilder(context, AppDb::class.java, "app.db").addMigrations(MIGRATION_1_2).build()
```

Test it with `MigrationTestHelper`: create the DB at version 1, insert rows, run the migration, and check the data survived. Simple changes (new column, new table) can use `@AutoMigration(from = 1, to = 2)`; renames and deletions need an `AutoMigrationSpec`.

### 7.10 Deeper dive: an outbox sync worker

```kotlin
@HiltWorker
class PushPendingChangesWorker @AssistedInject constructor(
    @Assisted ctx: Context, @Assisted params: WorkerParameters,
    private val dao: ArticleDao, private val api: ArticleApi
) : CoroutineWorker(ctx, params) {

    override suspend fun doWork(): Result {
        val pending = dao.pendingBookmarks()                  // rows with syncState = PENDING
        for (row in pending) {
            try {
                api.setBookmark(row.id, row.isBookmarked, idempotencyKey = row.changeId)
                dao.markSynced(row.id, row.changeId)          // only if no newer change happened meanwhile
            } catch (e: HttpException) {
                if (e.code() in 400..499) dao.markFailed(row.id) else return Result.retry()
            } catch (e: IOException) {
                return Result.retry()                         // offline again: back off and retry
            }
        }
        return Result.success()
    }
}
```

Details worth saying out loud: the `changeId` makes retries idempotent on the server; `markSynced` checks the `changeId` so a newer local edit made during the upload is not marked as synced; client errors (4xx) are not retried forever.

### 7.11 Deeper dive: de-duplicating in-flight requests

Two screens open at once and both ask for the user profile. Without care you send two identical requests.

```kotlin
class ProfileRepository @Inject constructor(
    private val api: ProfileApi,
    @ApplicationScope private val scope: CoroutineScope
) {
    private val mutex = Mutex()
    private var inFlight: Deferred<Profile>? = null

    suspend fun refresh(): Profile {
        val job = mutex.withLock {
            inFlight?.takeIf { it.isActive } ?: scope.async { api.getProfile() }.also { inFlight = it }
        }
        return job.await()   // all callers share one network call
    }
}
```

The request runs in the application scope, so one caller being cancelled (leaving a screen) does not cancel the request for the others.

### Interview questions

1. **How do you avoid duplicate network calls when two screens request the same data?** Share the in-flight request: a `Mutex` with a cached `Deferred`, or expose one hot flow from the repository via `shareIn` in an application scope. {Hard}
2. **How would you make an API call survive the user leaving the screen?** Don't tie it to `viewModelScope`. Use an application-scoped `CoroutineScope` for short work, or WorkManager for work that must complete. {Medium}
3. **Room `Flow` emits on every table change, even unrelated rows. How do you fix it?** Add `distinctUntilChanged()` after mapping, or narrow the query. {Medium}
4. **How do you handle a schema migration that fails in production?** Test migrations in CI with exported schemas. Avoid `fallbackToDestructiveMigration()` for user data; ship a migration, and only allow destructive fallback for pure cache tables. {Hard}
