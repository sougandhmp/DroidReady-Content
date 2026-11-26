# Build, release and SDKs

Seniors often own build health and the release process. Expect questions on slow builds, safe rollouts, monitoring in production, and building libraries other teams depend on.

### 12.1 Gradle essentials

**In one line:** Gradle builds in three phases, initialization, configuration and execution, and a modern setup uses the Kotlin DSL, a version catalog and convention plugins.

**Say this in the interview:** "Gradle first decides which projects are in the build, then configures every task, then runs the tasks it needs. Configuration must be fast and free of side effects, which is what the configuration cache relies on. I keep dependency versions in `libs.versions.toml`, share module setup through convention plugins so a feature module's build file is a few lines, and use build types and flavours for debug/release and staging/production. I use KSP instead of kapt, because it's faster and works with the K2 compiler."

**Example:**

```kotlin
// feature/settings/build.gradle.kts: everything shared lives in the convention plugin
plugins { id("example.android.feature") }
android { namespace = "com.example.feature.settings" }
```

**Common mistake:** Doing slow work during the configuration phase, which delays every build.

**Follow-ups:**

- *`api` vs `implementation`?* `api` exposes a dependency to consumers, so they recompile when it changes; `implementation` keeps it internal. Default to `implementation`.

### 12.2 Making builds faster

**In one line:** profile first, then turn on caching, avoid kapt, and split modules so a change recompiles less.

**Say this in the interview:** "I start with a Build Scan or the Build Analyzer to see whether time goes into configuration or execution. Then I enable the configuration cache and build cache, including a remote cache for CI, replace kapt with KSP, use non-transitive R classes, give Gradle enough memory, and split large modules so a change recompiles fewer of them. I track build time as a team metric."

**Common mistake:** Changing many settings at once without profiling, so you can't tell what helped.

**Follow-ups:**

- *What is the difference between the build cache and the configuration cache?* The build cache reuses task outputs. The configuration cache reuses the result of the configuration phase.

### 12.3 CI/CD

**In one line:** every pull request runs static analysis, unit tests and a build; merges to main run slower tests and produce a signed release build.

**Say this in the interview:** "On each PR I run lint, Detekt and formatting checks, unit and screenshot tests, and an assemble, aiming for under about 15 minutes, cancelling outdated runs and caching Gradle. On merge I run instrumented tests on managed emulators or Firebase Test Lab and build a signed App Bundle that goes to an internal track. Releases are promoted with Fastlane or Gradle Play Publisher. Play App Signing keeps the signing key; CI only has the upload key, as a secret."

**Example:**

```yaml
on: pull_request
concurrency: { group: pr-${{ github.ref }}, cancel-in-progress: true }
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: gradle/actions/setup-gradle@v4
      - run: ./gradlew lintDebug detekt testDebugUnitTest assembleDebug
```

**Common mistake:** Keeping signing keys or passwords in the repository.

**Follow-ups:**

- *What should block a pull request?* Fast, reliable checks such as lint, unit tests and a build. Unreliable checks train people to ignore failures.

### 12.4 Safe releases and feature flags

**In one line:** release gradually, watch the numbers, and use feature flags so you can turn features off without a new release.

**Say this in the interview:** "I use staged rollouts on Play, for example 1, 5, 20, 50 and 100 percent, and halt if crash-free users or ANR rates get worse. Risky features ship behind remote feature flags, so deploying code and releasing a feature are separate decisions, and there's a kill switch. Each flag has an owner and a removal date. Because old app versions stay in use for months, APIs must stay backwards-compatible, and for critical fixes I use Play's in-app updates or a minimum-version check."

**Example:**

```kotlin
if (flags.isEnabled(Flag.NEW_CHECKOUT)) NewCheckoutScreen() else LegacyCheckoutScreen()
```

**Common mistake:** Releasing to everyone at once with no way to switch the feature off.

**Follow-ups:**

- *A crash hits 0.5% of users after release. What do you do?* Halt the rollout, read the de-obfuscated stack trace and affected devices, turn the feature off with a flag if possible, ship a tested hotfix, resume the rollout, and run a blameless post-mortem.

### 12.5 R8 keep rules

**In one line:** R8 removes and renames code it thinks is unused, so code reached only by reflection needs keep rules.

**Say this in the interview:** "Most release-only crashes after enabling R8 come from reflection: JSON libraries that read fields by name, classes named in XML or native code, or enums looked up with `valueOf`. I add the narrowest keep rule that fixes it, keep line numbers for readable crash reports, upload the mapping file, and prefer libraries that ship their own consumer rules. To debug, I reproduce with a local release build and check `usage.txt` and `mapping.txt`."

**Example:**

```proguard
-keep class com.example.data.network.dto.** { *; }      # DTOs read by reflection (Gson)
-keepattributes SourceFile,LineNumberTable               # readable stack traces
```

**Common mistake:** Keeping whole packages to silence a crash, which gives up much of R8's benefit.

**Follow-ups:**

- *Why does code work in debug but crash in release?* R8 may have removed or renamed something that is reached only by reflection. Check the stack trace with the mapping file.

### 12.6 App Bundles, dynamic features, in-app updates and reviews

**In one line:** you upload an App Bundle and Play generates per-device APKs; dynamic feature modules can be installed on demand; Play also offers in-app update and review prompts.

**Say this in the interview:** "With an App Bundle, each device downloads only its density, CPU architecture and languages, so installs are smaller, and bundles are required for new apps on Play. For a large, rarely used feature I can use an on-demand dynamic feature module, accepting more complex navigation and testing. The in-app updates API gives flexible updates in the background or immediate full-screen updates for critical fixes. The in-app review API shows Play's rating sheet, but Play limits how often it appears, so I ask after a positive moment and never from a 'rate us' button."

**Common mistake:** Assuming a module downloaded on demand is always available. The download can fail.

**Follow-ups:**

- *APK vs App Bundle?* An APK can be installed on a device. An App Bundle is uploaded to Play, which generates APKs from it.

### 12.7 Building and versioning an SDK

**In one line:** an SDK needs a small, deliberate public API, semantic versioning, binary-compatibility checks and good manners inside the host app.

**Say this in the interview:** "When other teams or companies depend on my library, I can't change their code, so I'm careful. I turn on Kotlin explicit API mode so nothing becomes public by accident, keep one small entry point, avoid exposing third-party types, and make it Java-friendly. I version with semantic versioning and deprecate before removing. The binary-compatibility-validator plugin fails CI if the public API changes unexpectedly. Inside the host app, I ship consumer R8 rules, keep dependencies minimal, never block the main thread in `initialize`, never crash the host, and let the app control data collection."

**Example:**

```kotlin
public object Analytics {
    @JvmStatic public fun initialize(context: Context, config: AnalyticsConfig) { /* lazy, off the main thread */ }
    @JvmStatic public fun track(event: String, properties: Map<String, Any> = emptyMap()) { }
}
```

**Common mistake:** Making more of the API public than needed, then being unable to change it safely.

**Follow-ups:**

- *Which changes break binary compatibility even though they compile?* Adding a parameter with a default value, changing a return type, or removing a public member. That's why an API check in CI matters.

### 12.8 Observability

**In one line:** measure the app in production: crashes, ANRs, performance and key user journeys.

**Say this in the interview:** "I use Crashlytics or Sentry for crashes and non-fatal errors with context, Play vitals for ANRs and startup, custom traces around key journeys, and structured analytics events. Each release has a dashboard, and we alert when crash-free users drop below our target, for example 99.8 percent."

**Common mistake:** Collecting logs and crashes with no alerts or owner, or putting personal data in them.

**Follow-ups:**

- *Why upload the R8 mapping file?* It turns obfuscated names in crash stack traces back into readable ones.

### Interview questions

1. **Your clean build takes 12 minutes. What do you do?** Profile with a Build Scan, check configuration vs execution time, enable configuration and remote build caches, replace kapt with KSP, split large modules and cache Gradle in CI. {Medium}
2. **What does your CI pipeline look like?** On PRs: lint, static analysis, unit and screenshot tests and a build. On merge: instrumented tests and a signed bundle to an internal track. Releases promoted through staged rollout. {Medium}
3. **How do you release safely?** Staged rollout watching crash and ANR rates, features behind remote flags with a kill switch, backwards-compatible APIs, and a rollback or hotfix plan. {Medium}
4. **A crash appears in 0.5% of users after a release. What's your process?** Halt the rollout, triage the de-obfuscated trace and affected devices, disable via flag if possible, ship a tested hotfix, resume, and run a blameless post-mortem. {Medium}
5. **Why does an app crash only in release builds?** Usually R8 removed or renamed something used through reflection. Reproduce with a release build, check the mapping and usage files, and add the narrowest keep rule. {Medium}
6. **APK or App Bundle?** An APK is the installable file. An App Bundle is the publishing format from which Play generates per-device APKs, so users download less. Bundles are required for new apps on Play. {Easy}
7. **When would you use an on-demand dynamic feature module?** For a large, rarely used feature where the install-size saving is worth the extra complexity in navigation, testing and release. {Hard}
8. **How do you avoid breaking apps that use your SDK?** Semantic versioning, explicit API mode, a binary-compatibility check in CI, deprecation before removal, consumer R8 rules, and no third-party types in the public API. {Hard}
9. **`api` or `implementation` in Gradle?** `implementation` by default, so dependencies stay internal and changes recompile fewer modules; `api` only when a dependency is part of your module's public API. {Easy}
