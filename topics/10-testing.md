# Testing strategy

A senior defines the testing strategy for the team, not just writes tests. Know the pyramid, what each layer catches, and how to keep tests fast and reliable.

### 10.1 The pyramid

| Level | Runs on | Speed | What to test | Tools |
| --- | --- | --- | --- | --- |
| Unit (\~70%) | JVM | ms | ViewModels, use cases, repositories, mappers | JUnit, kotlinx-coroutines-test, Turbine, MockK, Truth |
| Integration (\~20%) | JVM (Robolectric) or device | s | Room DAOs, repository + DB, navigation | Robolectric, in-memory Room, MockWebServer |
| UI / E2E (\~10%) | Device / emulator | s-min | Critical user journeys | Compose test, Espresso, UI Automator, Gradle Managed Devices |
| Screenshot | JVM | s | Visual regressions in components | Paparazzi, Roborazzi, Compose Preview Screenshot Testing |

### 10.2 Fakes vs mocks

- **Fake:** a working lightweight implementation (in-memory repository). Tests behaviour, survives refactors. Google recommends fakes.
- **Mock:** records and verifies calls (`verify { api.get() }`). Useful for checking interactions with things you do not own; over-use couples tests to implementation.

```kotlin
class FakeArticleRepository : ArticleRepository {
    private val articles = MutableStateFlow<List<Article>>(emptyList())
    var shouldFail = false
    fun emit(list: List<Article>) { articles.value = list }
    override fun observeAll() = articles
    override suspend fun refresh() = if (shouldFail) Result.failure(IOException()) else Result.success(Unit)
}
```

### 10.3 ViewModel test with coroutines

```kotlin
class MainDispatcherRule(val dispatcher: TestDispatcher = UnconfinedTestDispatcher()) : TestWatcher() {
    override fun starting(d: Description) = Dispatchers.setMain(dispatcher)
    override fun finished(d: Description) = Dispatchers.resetMain()
}

class ArticlesViewModelTest {
    @get:Rule val mainRule = MainDispatcherRule()
    private val repo = FakeArticleRepository()

    @Test fun `shows error when refresh fails`() = runTest {
        repo.shouldFail = true
        val vm = ArticlesViewModel(GetArticlesUseCase(repo), RefreshArticlesUseCase(repo))
        vm.uiState.test {
            val state = expectMostRecentItem()
            assertThat(state.errorMessage).isNotNull()
        }
    }
}
```

### 10.4 Room and network integration tests

```kotlin
@RunWith(AndroidJUnit4::class)
class ArticleDaoTest {
    private lateinit var db: AppDb
    @Before fun setUp() {
        db = Room.inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext(), AppDb::class.java).build()
    }
    @After fun tearDown() = db.close()

    @Test fun upsertThenObserve() = runTest {
        db.articleDao().upsertAll(listOf(entity("1")))
        assertThat(db.articleDao().observeAll().first()).hasSize(1)
    }
}
```

For network code, use **MockWebServer** to return canned JSON, error codes and slow responses, testing the real Retrofit + serializer setup.

### 10.5 Compose UI test

```kotlin
@get:Rule val compose = createComposeRule()

@Test fun showsArticlesAndHandlesClick() {
    var clicked: String? = null
    compose.setContent {
        ArticlesScreen(state = ArticlesUiState(articles = listOf(ArticleUi("1", "Hello"))), onClick = { clicked = it })
    }
    compose.onNodeWithText("Hello").assertIsDisplayed().performClick()
    assertEquals("1", clicked)
}
```

### 10.6 Flaky tests and CI

- Causes: real time / `Thread.sleep`, shared state between tests, animations, network, unordered async work.
- Fixes: inject dispatchers and clocks, `runTest` virtual time, idling resources / `waitUntil`, disable animations, hermetic tests with fakes, Gradle Managed Devices for consistent emulators, test orchestrator to isolate state.
- Quarantine and track flaky tests rather than retrying silently.

### 10.7 Deeper dive: test dispatchers explained

| Dispatcher | Behaviour | Use when |
| --- | --- | --- |
| `StandardTestDispatcher` | Queues coroutines; they run only when the test advances (`advanceUntilIdle`, `runCurrent`, or the test suspends) | You want to check intermediate states, e.g. "loading" before "loaded" |
| `UnconfinedTestDispatcher` | Starts coroutines eagerly, like `Dispatchers.Main.immediate` | Simple tests where only the final state matters; collectors that must start immediately |

```kotlin
@Test fun `shows loading then content`() = runTest {
    Dispatchers.setMain(StandardTestDispatcher(testScheduler))
    val vm = FeedViewModel(FakeFeedRepository(delayMs = 1_000))

    assertTrue(vm.state.value.isLoading)        // init's launch has not finished yet
    advanceTimeBy(1_001)                         // virtual time: returns instantly
    runCurrent()
    assertFalse(vm.state.value.isLoading)
    assertEquals(3, vm.state.value.items.size)
}
```

Share the same `testScheduler` between `Main` and any injected dispatcher, so one call to `advanceTimeBy` moves all of them together.

### 10.8 Deeper dive: MockWebServer against the real Retrofit stack

```kotlin
class ArticleApiTest {
    private val server = MockWebServer()
    private lateinit var api: ArticleApi

    @Before fun setUp() {
        server.start()
        api = Retrofit.Builder().baseUrl(server.url("/"))
            .addConverterFactory(Json { ignoreUnknownKeys = true }.asConverterFactory("application/json".toMediaType()))
            .build().create(ArticleApi::class.java)
    }
    @After fun tearDown() = server.shutdown()

    @Test fun `parses articles and sends page param`() = runTest {
        server.enqueue(MockResponse().setBody("""[{"id":"1","title":"Hello","topic":"android","publishedAt":0}]"""))
        val result = api.getArticles(page = 2)
        assertEquals("Hello", result.single().title)
        assertEquals("/articles?page=2&size=20", server.takeRequest().path)
    }

    @Test fun `maps 500 to server error`() = runTest {
        server.enqueue(MockResponse().setResponseCode(500))
        val repo = OfflineFirstArticleRepository(api, FakeArticleDao(), UnconfinedTestDispatcher(testScheduler))
        assertTrue(repo.refresh().isFailure)
    }
}
```

This catches real bugs that fakes cannot: wrong JSON field names, missing query parameters, broken converters.

### 10.9 Deeper dive: MockK when you need it

```kotlin
val analytics = mockk<Analytics>(relaxed = true)        // relaxed: unstubbed calls return defaults
val repo = mockk<CartRepository> {
    coEvery { checkout(any()) } returns Result.success(OrderId("42"))
}

val vm = CartViewModel(repo, analytics)
vm.onCheckout()

coVerify(exactly = 1) { repo.checkout(any()) }
verify { analytics.log(match { it.name == "checkout_success" }) }
```

Use mocks for collaborators whose only observable effect is a call (analytics, loggers). For repositories and data sources, a fake usually gives clearer, less brittle tests.

### 10.10 Deeper dive: screenshot tests

Screenshot tests catch visual regressions (padding, colours, dark mode, font scaling) that assertions miss.

```kotlin
// Roborazzi (runs on the JVM with Robolectric)
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class ArticleCardScreenshotTest {
    @get:Rule val compose = createComposeRule()

    @Test fun articleCard_dark_largeFont() {
        compose.setContent {
            CompositionLocalProvider(LocalDensity provides Density(density = 2f, fontScale = 1.5f)) {
                AppTheme(darkTheme = true) { ArticleCard(sampleArticle) }
            }
        }
        compose.onRoot().captureRoboImage()   // compared with the recorded golden image in CI
    }
}
```

Record golden images once (`./gradlew recordRoborazziDebug`), commit them, and verify on every PR (`verifyRoborazziDebug`). Cover each design-system component in light, dark and large-font variants.

### 10.11 Deeper dive: testing process death

Automated: `SavedStateHandle` is a plain class, so you can simulate restoration directly.

```kotlin
@Test fun `restores step after process death`() {
    val handle = SavedStateHandle(mapOf("step" to 2, "email" to "a@b.com"))
    val vm = SignUpViewModel(handle)
    assertEquals(2, vm.step.value)
    assertEquals("a@b.com", vm.email.value)
}
```

For `rememberSaveable`, use `StateRestorationTester` in Compose tests: `tester.setContent { ... }`, change state, call `tester.emulateSavedInstanceStateRestore()`, and assert the state is back.

Manual: put the app in the background, run `adb shell am kill com.example.app`, then reopen it from Recents. Do this for every screen with user input before a release.

### 10.12 Test-driven development in practice

**Learn:** TDD is a short loop: write a failing test (**red**), write the least code to pass it (**green**), then clean up with the tests as a safety net (**refactor**). It works best for logic with clear inputs and outputs: validators, reducers, mappers, pricing rules and ViewModel state changes.

**Example: a password rule, built test-first.**

```kotlin
// RED: describe the behaviour before the code exists
class PasswordValidatorTest {
    private val validator = PasswordValidator()

    @Test fun `rejects passwords shorter than 8 characters`() =
        assertEquals(PasswordError.TooShort, validator.validate("abc12"))

    @Test fun `requires at least one digit`() =
        assertEquals(PasswordError.NoDigit, validator.validate("abcdefgh"))

    @Test fun `accepts a valid password`() =
        assertNull(validator.validate("abcdefg1"))
}

// GREEN: the simplest code that passes
class PasswordValidator {
    fun validate(p: String): PasswordError? = when {
        p.length < 8 -> PasswordError.TooShort
        p.none { it.isDigit() } -> PasswordError.NoDigit
        else -> null
    }
}

// REFACTOR: e.g. make the rules a list so product can add one without touching validate()
```

Then drive the ViewModel the same way: write `onPasswordChanged("abc") shows TooShort error` first, then add the code.

**Senior view, for the interview:**

- TDD pays off most in domain logic and bug fixes: write a test that reproduces the bug first, so it can never come back.
- It is less useful for UI layout and exploratory spikes; there, write tests after the design settles.
- Tests written first push you toward injectable, small classes, which is often the main benefit.
- Say what you actually do. For example: "I write tests first for business rules and reducers, and add UI tests for the critical journeys after the screen stabilises."

### Interview questions

1. **What makes code testable?** Constructor injection, interfaces at boundaries, no hidden statics, injected dispatchers/clocks, pure functions for logic, stateless UI. {Easy}
2. **How do you test a Flow that emits several values over time?** Turbine (`test { awaitItem() }`) inside `runTest`; or collect into a list in `backgroundScope`. {Medium}
3. **What is your target code coverage?** Coverage is a signal, not a goal. Aim for high coverage on domain and ViewModel logic, test critical journeys end to end, and use coverage to find untested branches, not to hit a number. {Easy}
4. **Robolectric vs instrumented tests?** Robolectric runs Android framework code on the JVM (fast, good for CI); instrumented tests run on a real device (accurate, slower). Use both: Robolectric for most, a small device suite for critical paths. {Medium}
5. **Do you practise TDD?** Give an honest, specific answer. For example: test-first for business rules, reducers and every bug fix (the reproducing test comes first), and tests after the design settles for UI layout. {Easy}
