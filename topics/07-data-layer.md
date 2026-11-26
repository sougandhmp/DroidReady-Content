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

### Interview questions

1. **How do you avoid duplicate network calls when two screens request the same data?** Share the in-flight request: a `Mutex` with a cached `Deferred`, or expose one hot flow from the repository via `shareIn` in an application scope. {Hard}
2. **How would you make an API call survive the user leaving the screen?** Don't tie it to `viewModelScope`. Use an application-scoped `CoroutineScope` for short work, or WorkManager for work that must complete. {Medium}
3. **Room `Flow` emits on every table change, even unrelated rows. How do you fix it?** Add `distinctUntilChanged()` after mapping, or narrow the query. {Medium}
4. **How do you handle a schema migration that fails in production?** Test migrations in CI with exported schemas. Avoid `fallbackToDestructiveMigration()` for user data; ship a migration, and only allow destructive fallback for pure cache tables. {Hard}
