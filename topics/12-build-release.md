# Build, Gradle, CI/CD, release and observability

Seniors often own build health and the release train. Expect questions on slow builds, safe rollouts and production monitoring.

### 12.1 Gradle essentials

- **Phases:** initialization (which projects) → configuration (build the task graph; must be fast and side-effect free) → execution.
- **Kotlin DSL + version catalog:**

```toml
# gradle/libs.versions.toml
[versions]
kotlin = "2.2.0"
room = "2.7.2"
[libraries]
room-runtime = { module = "androidx.room:room-runtime", version.ref = "room" }
room-compiler = { module = "androidx.room:room-compiler", version.ref = "room" }
[plugins]
ksp = { id = "com.google.devtools.ksp", version = "2.2.0-2.0.2" }
```

(Version numbers are illustrative; check current releases.)

- **Convention plugins** in `build-logic` share `compileSdk`, Kotlin options, lint and test setup across modules.
- **Build variants:** build types (`debug`, `release`) × product flavours (`free`/`paid`, `staging`/`prod`). Use `buildConfigField` or resource values per variant.
- **KSP** over **kapt**: KSP is up to \~2x faster and works with K2; migrate Room, Hilt and Moshi to KSP.

### 12.2 Making builds faster

1. Enable the **configuration cache** and **build cache** (local + remote).
2. Modularise so changes recompile fewer modules; use `implementation` instead of `api`.
3. Use KSP, avoid kapt; enable non-transitive R classes.
4. Run `./gradlew assembleDebug --scan` (Build Scan) or the Build Analyzer to find slow tasks and configuration time.
5. Give Gradle enough heap (`org.gradle.jvmargs`), and keep AGP, Kotlin and Gradle up to date.

### 12.3 CI/CD pipeline

A typical pipeline (GitHub Actions, Bitrise, GitLab CI, Jenkins):

1. On every PR: static analysis (Android Lint, Detekt, ktlint/Spotless), unit tests, screenshot tests, build debug, dependency checks.
2. On merge to main: instrumented tests on Gradle Managed Devices or Firebase Test Lab, build release AAB, upload to an internal track.
3. Release: signed AAB (Play App Signing; upload key kept in CI secrets), versionCode auto-incremented, release notes, Fastlane or Gradle Play Publisher to promote tracks.

### 12.4 Safe releases

- **Staged rollout:** 1% → 5% → 20% → 50% → 100%, gated on crash-free users and ANR rate. Halt the rollout if vitals regress.
- **Feature flags / remote config:** ship dark, enable gradually, kill switch for risky features. Decouple deploy from release.
- **Release trains:** e.g. weekly or bi-weekly cut, code freeze, regression testing, hotfix branch policy.
- **In-app updates API:** flexible or immediate updates; force-update for critical security fixes through a minimum-version check.
- **Backward compatibility:** old app versions stay in use for months, so APIs must stay compatible (versioned endpoints, additive changes).

### 12.5 Observability

- **Crash and ANR reporting:** Firebase Crashlytics, Sentry, Play Console vitals. Upload R8 mapping files.
- **Performance monitoring:** Firebase Performance, custom traces around key journeys, JankStats.
- **Analytics and logging:** structured events, funnels, non-fatal error logging with context (no PII).
- **Alerting:** dashboards per release; alert on crash-free rate dropping below target (e.g. 99.8% users).

### 12.6 Deeper dive: a convention plugin

Without convention plugins, 30 modules each repeat the same 40 lines of Gradle. With one, a feature module's build file shrinks to a few lines.

```kotlin
// build-logic/convention/src/main/kotlin/AndroidFeatureConventionPlugin.kt
class AndroidFeatureConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) = with(target) {
        pluginManager.apply("com.android.library")
        pluginManager.apply("org.jetbrains.kotlin.android")
        pluginManager.apply("com.google.devtools.ksp")
        pluginManager.apply("com.google.dagger.hilt.android")

        extensions.configure<LibraryExtension> {
            compileSdk = 36
            defaultConfig { minSdk = 26; testInstrumentationRunner = "com.example.testing.HiltTestRunner" }
        }
        val libs = extensions.getByType<VersionCatalogsExtension>().named("libs")
        dependencies {
            add("implementation", project(":core:designsystem"))
            add("implementation", project(":core:data"))
            add("implementation", libs.findLibrary("hilt.android").get())
            add("ksp", libs.findLibrary("hilt.compiler").get())
            add("testImplementation", project(":core:testing"))
        }
    }
}
```

```kotlin
// feature/settings/build.gradle.kts - the whole file
plugins { id("example.android.feature") }
android { namespace = "com.example.feature.settings" }
```

Changing the minimum SDK or adding a lint rule now happens in one place for every module.

### 12.7 Deeper dive: a pull-request CI workflow

```yaml
# .github/workflows/pr.yml
name: PR checks
on: pull_request
concurrency: { group: pr-${{ github.ref }}, cancel-in-progress: true }   # stop outdated runs
jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: 17 }
      - uses: gradle/actions/setup-gradle@v4        # caches Gradle between runs
      - run: ./gradlew spotlessCheck detekt lintDebug
      - run: ./gradlew testDebugUnitTest verifyRoborazziDebug
      - run: ./gradlew assembleDebug
      - uses: actions/upload-artifact@v4
        if: failure()
        with: { name: reports, path: "**/build/reports/**" }
```

Talking points: cancel superseded runs to save CI minutes, cache Gradle, upload reports only on failure, keep the PR check under about 15 minutes, and run slower instrumented tests on merge or nightly instead.

### 12.8 Deeper dive: feature flags in code

```kotlin
interface FeatureFlags {
    fun isEnabled(flag: Flag): Boolean
}

enum class Flag(val key: String, val default: Boolean) {
    NEW_CHECKOUT("new_checkout", false),
    OFFLINE_MODE("offline_mode", true)
}

class RemoteConfigFlags @Inject constructor(private val rc: FirebaseRemoteConfig) : FeatureFlags {
    override fun isEnabled(flag: Flag) = rc.getBoolean(flag.key)   // defaults set from Flag.default
}

// Call site
if (flags.isEnabled(Flag.NEW_CHECKOUT)) NewCheckoutScreen() else LegacyCheckoutScreen()
```

Good practice: every flag has an owner and a removal date; tests use a `FakeFeatureFlags`; a debug menu lets QA flip flags locally; once a feature is at 100% for a release or two, delete the flag and the old code path.

### 12.9 Deeper dive: R8 keep rules that actually matter

```proguard
# Keep classes used by reflection-based JSON (Gson); not needed for kotlinx.serialization with its plugin
-keep class com.example.data.network.dto.** { *; }

# Keep a class referenced only from native code or from XML by name
-keep class com.example.NativeBridge { native <methods>; }

# Keep enum values used via valueOf(String) from a server response
-keepclassmembers enum com.example.model.** { public static **[] values(); public static ** valueOf(java.lang.String); }

# Keep line numbers so crash reports are readable, and hide original file names
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
```

How to debug a release-only crash caused by R8: reproduce with a release build locally, check `build/outputs/mapping/release/usage.txt` (what was removed) and `mapping.txt` (renames), add the narrowest keep rule, and add a test that runs against the minified build so it cannot happen again. Prefer libraries that ship their own consumer rules.

### 12.10 App Bundles, Play Feature Delivery, in-app updates and reviews

**Android App Bundle (AAB).** You upload one `.aab`; Google Play builds and serves optimised APKs for each device (only its screen density, CPU architecture and languages). This makes downloads smaller than a universal APK. New apps on Play must be published as bundles, and Play App Signing holds the app signing key while you keep an upload key.

**Play Feature Delivery** splits rarely used features into dynamic feature modules:

| Delivery option | When the module is installed | Example |
| --- | --- | --- |
| Install-time | With the app | Default; useful to split code while keeping it always present |
| Conditional | At install, if the device matches (country, features, SDK) | AR feature only on ARCore devices |
| On-demand | When the app requests it at runtime | A rarely used video editor |

```kotlin
val splitInstall = SplitInstallManagerFactory.create(context)
val request = SplitInstallRequest.newBuilder().addModule("video_editor").build()
splitInstall.startInstall(request)
    .addOnSuccessListener { openEditor() }
    .addOnFailureListener { showError(it) }
```

Trade-offs to mention: dynamic modules depend on the base app (the reverse of normal modules), cross-module navigation needs reflection or a service-loader pattern, and testing needs `bundletool` or internal app sharing. Many teams use normal Gradle modules for build speed and save dynamic features for large, rarely used parts.

**In-app updates.** The Play Core library can prompt users to update without leaving the app.

```kotlin
val updateManager = AppUpdateManagerFactory.create(context)
updateManager.appUpdateInfo.addOnSuccessListener { info ->
    val critical = info.updatePriority() >= 4                       // priority set when you publish
    if (info.updateAvailability() == UpdateAvailability.UPDATE_AVAILABLE &&
        info.isUpdateTypeAllowed(if (critical) AppUpdateType.IMMEDIATE else AppUpdateType.FLEXIBLE)) {
        updateManager.startUpdateFlowForResult(
            info, updateLauncher,
            AppUpdateOptions.defaultOptions(if (critical) AppUpdateType.IMMEDIATE else AppUpdateType.FLEXIBLE)
        )
    }
}
```

**Flexible** downloads in the background while the user keeps working; you then ask them to restart. **Immediate** is a full-screen flow for critical fixes. For a hard minimum version (e.g. a breaking API change), also check a minimum version from your own remote config.

**In-app reviews.** `ReviewManager` shows the Play rating sheet inside your app. Play applies a quota, so the sheet may not appear, and your app is not told whether the user rated. Ask after a positive moment (an order delivered, a task completed), never from a "Rate us" button, and never offer rewards for ratings.

### 12.11 Building and versioning an Android library or SDK

Senior roles often include building an internal SDK or a library other teams or companies consume. The bar is higher than app code, because you can't change your callers.

**Design the public API on purpose.**

- Turn on Kotlin **explicit API mode** (`kotlin { explicitApi() }`) so every public declaration needs a visibility modifier and a return type. Nothing becomes public by accident.
- Keep the surface small: one entry point (`Analytics.initialize(context, config)`), immutable config objects built with a builder or DSL, and `internal` for everything else.
- Avoid exposing third-party types (OkHttp, Retrofit, RxJava) in your API, so you can replace them later.
- Make it Java-friendly if Java apps may use it (`@JvmStatic`, `@JvmOverloads`, see 1.17).

```kotlin
public object Analytics {
    @JvmStatic
    public fun initialize(context: Context, config: AnalyticsConfig) { /* ... */ }

    @JvmStatic
    public fun track(event: String, properties: Map<String, Any> = emptyMap()) { /* ... */ }
}

public class AnalyticsConfig private constructor(public val apiKey: String, public val flushIntervalSec: Int) {
    public class Builder(private val apiKey: String) {
        private var flush = 30
        public fun flushIntervalSec(value: Int): Builder = apply { flush = value }
        public fun build(): AnalyticsConfig = AnalyticsConfig(apiKey, flush)
    }
}
```

**Version with semantic versioning (MAJOR.MINOR.PATCH).** PATCH for fixes, MINOR for backwards-compatible additions, MAJOR for breaking changes. Deprecate before removing: `@Deprecated(message, ReplaceWith(...), level = WARNING)` in one release, `ERROR` in the next, removal in the next major.

**Protect binary compatibility.** A change that compiles for you can still break apps built against the old version (for example adding a parameter with a default value, or changing a return type from `List` to `Collection`). Use the Kotlin **binary-compatibility-validator** Gradle plugin: it writes the public API to an `.api` file, and CI fails if the API changes without the file being updated in the same pull request.

**Be a good guest in the host app.**

- Ship **consumer ProGuard/R8 rules** inside the AAR (`consumerProguardFiles`) so apps that minify don't break your SDK.
- Keep dependencies few and use `implementation`, so you don't force versions on the app; document the minimum `minSdk` and Kotlin version.
- Never block the main thread in `initialize`; do work lazily or in the background.
- Don't crash the host: catch your own failures and report them through a callback or logs.
- Let the app control data collection (consent, opt-out) and declare what you collect for the Play Data safety form.

**Publish and support.** Publish AARs to Maven Central or an internal repository (with a sources JAR and KDoc), keep a changelog and migration guides, and test against a sample app on several API levels in CI.

### Interview questions

1. **Your clean build takes 12 minutes. What do you do?** Profile with a Build Scan, check configuration time vs execution, enable configuration and remote build caches, replace kapt with KSP, split large modules, parallelise CI, and cache Gradle in CI. {Medium}
2. **A crash appears in 0.5% of users after release. What is your process?** Halt the staged rollout, triage the stack trace (de-obfuscated), check which devices/OS versions, disable via feature flag if possible, hotfix with a test reproducing it, resume the rollout, then run a blameless post-mortem. {Medium}
3. **`api` vs `implementation`?** `api` leaks the dependency to consumers (they recompile when it changes); `implementation` keeps it internal. Default to `implementation`. {Easy}
4. **APK vs App Bundle?** An APK is the installable file. An AAB is a publishing format: Play generates per-device APKs from it, so users download only the code and resources their device needs. Bundles are required for new apps on Play. {Easy}
5. **When would you use an on-demand dynamic feature module?** For a large, rarely used feature (an editor, an AR mode) where the saving in install size is worth the extra complexity in navigation, testing and release. {Hard}
6. **How do you avoid breaking apps that use your SDK?** Semantic versioning, explicit API mode, a binary-compatibility check in CI, deprecation cycles before removal, consumer R8 rules in the AAR, and no third-party types in the public API. {Hard}
