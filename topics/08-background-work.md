# Background work

Android limits background execution to save battery. Interviewers want to see that you pick the right tool for each job and understand the system's restrictions.

### 8.1 Choosing the right tool

**In one line:** pick the API by three questions: must the work finish, must it run at an exact time, and does the user know it's happening?

**Say this in the interview:** "If the work only matters while the screen is open, a coroutine in `viewModelScope` is enough. If it must finish even if the app is closed or the phone restarts, like an upload or a sync, I use WorkManager. If it's long-running and the user is aware of it, like music or navigation, I use a foreground service with a notification. If it must happen at an exact time, like an alarm clock, I use `AlarmManager`. And if the server needs to wake the app, I use a push message that schedules WorkManager."

**Example:**

| Need | Use | Example |
| --- | --- | --- |
| Work while the screen is open | Coroutine in `viewModelScope` | Load a screen |
| Must finish, can wait | WorkManager | Upload photos, sync, send logs |
| Long, user-visible, now | Foreground service | Music, navigation, workout tracking |
| Exact time | `AlarmManager.setExactAndAllowWhileIdle` | Alarm clock, calendar reminder |
| Server-triggered | Push message, then WorkManager | New messages to sync |

**Common mistake:** Using a foreground service for work that could simply be deferred with WorkManager.

**Follow-ups:**

- *Which do you use to refresh data while the user watches the screen?* A coroutine tied to the ViewModel or the screen. The work doesn't need to outlive it.

### 8.2 WorkManager

**In one line:** WorkManager runs deferrable work that must finish: it respects constraints, retries with backoff, and survives app restarts and reboots.

**Say this in the interview:** "WorkManager stores work in its own database, so it runs even after the app is killed or the device reboots. I set constraints like 'unmetered network' or 'battery not low', a backoff policy for retries, and use unique work so the same job isn't queued twice. Workers can be chained, report progress, and run as expedited work for important short jobs. With Hilt I use `@HiltWorker` to inject dependencies."

**Example:**

```kotlin
@HiltWorker
class SyncWorker @AssistedInject constructor(
    @Assisted ctx: Context, @Assisted params: WorkerParameters, private val repo: ArticleRepository
) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result =
        if (repo.sync().isSuccess) Result.success() else if (runAttemptCount < 3) Result.retry() else Result.failure()
}

val request = PeriodicWorkRequestBuilder<SyncWorker>(6, TimeUnit.HOURS)        // minimum interval is 15 minutes
    .setConstraints(Constraints(requiredNetworkType = NetworkType.UNMETERED))
    .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
    .build()
WorkManager.getInstance(context).enqueueUniquePeriodicWork("sync", ExistingPeriodicWorkPolicy.KEEP, request)
```

**Common mistake:** Enqueuing the same job again and again instead of using unique work.

**Follow-ups:**

- *Does WorkManager run at an exact time?* No. It guarantees the work runs eventually when constraints are met; periodic work can drift.
- *What if the user force-stops the app?* Scheduled work is cancelled until the app is opened again.
- *How do you chain work?* `beginUniqueWork(...).then(upload).then(cleanup).enqueue()`; if one step fails, the rest are marked failed.

### 8.3 Foreground services

**In one line:** a foreground service runs ongoing, user-visible work and must show a notification while it runs.

**Say this in the interview:** "I use a foreground service only for work the user is actively aware of, like playing music or recording a run. It must show a notification within a few seconds of starting, and since Android 14 it must declare a type, such as `mediaPlayback` or `location`, with a matching permission, which Play reviews. Apps generally can't start one from the background, and Android 15 limits `dataSync` services to about 6 hours a day, so syncing belongs in WorkManager."

**Example:**

```xml
<service android:name=".TrackingService" android:foregroundServiceType="location" android:exported="false" />
```

```kotlin
ServiceCompat.startForeground(this, NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
```

**Common mistake:** Starting a foreground service from the background without checking that this case is allowed.

**Follow-ups:**

- *What must a foreground service show?* A notification, so the user can see that the app is doing ongoing work.

### 8.4 Exact alarms

**In one line:** `AlarmManager` can fire at an exact time, but exact alarms need a special permission and are for user-facing, time-critical features only.

**Say this in the interview:** "For an alarm clock or a calendar reminder I use `setExactAndAllowWhileIdle`, which also fires in Doze. Since Android 12 that needs the `SCHEDULE_EXACT_ALARM` permission, which the user can revoke, so I check `canScheduleExactAlarms()` first. Alarms are cleared on reboot, so I listen for `BOOT_COMPLETED` and reschedule from the database. Anything that doesn't need an exact time uses inexact alarms or WorkManager."

**Common mistake:** Using exact alarms for routine syncing.

**Follow-ups:**

- *What do you do if exact alarm permission is not granted?* Explain why it is needed, or fall back to an inexact alarm or WorkManager if the feature can allow some delay.

### 8.5 Doze and App Standby

**In one line:** when the phone is idle, Doze delays network, jobs and alarms to maintenance windows, and App Standby Buckets limit rarely used apps.

**Say this in the interview:** "When the device is unplugged and still, Doze batches background work into short maintenance windows, and normal alarms are delayed. App Standby Buckets give apps fewer jobs the less the user opens them. This is why I let WorkManager decide when to run, and use high-priority push messages only for truly urgent, user-visible events. I test with `adb shell dumpsys deviceidle force-idle`."

**Common mistake:** Testing only on a charging, active phone, so delays from Doze never show up.

**Follow-ups:**

- *Why test with forced idle?* Normal development devices are often charging and active, so Doze delays are otherwise hard to see.

### 8.6 Push-triggered sync

**In one line:** use a push message as a signal to sync, not as the data itself.

**Say this in the interview:** "Push payloads have size limits and messages can be delayed, duplicated or lost. So my push only says 'something changed', and the handler schedules a unique WorkManager job that fetches the real data since the last sync cursor. Because the sync is idempotent, missed or duplicate pushes do no harm."

**Example:**

```kotlin
override fun onMessageReceived(message: RemoteMessage) {
    if (message.data["type"] == "sync") {
        WorkManager.getInstance(this).enqueueUniqueWork(
            "sync", ExistingWorkPolicy.REPLACE,
            OneTimeWorkRequestBuilder<SyncWorker>().setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST).build()
        )
    }
}
```

**Common mistake:** Putting the real data in the push payload and assuming every message arrives once and in order.

**Follow-ups:**

- *What if two pushes arrive for the same change?* Run the sync as unique work and make it idempotent, so the repeat is harmless.

### Interview questions

1. **How do you choose between a coroutine, WorkManager, a foreground service and AlarmManager?** Coroutine for work tied to a screen; WorkManager for work that must finish but can wait; foreground service for long, user-visible work; AlarmManager for an exact time. {Medium}
2. **Why not use a plain background Service for syncing?** Since Android 8, background services are stopped soon after the app leaves the foreground. WorkManager is the supported, battery-friendly way. {Easy}
3. **Does WorkManager guarantee exact timing?** No. It guarantees the work eventually runs when constraints are met; periodic work has a 15-minute minimum and can drift. {Easy}
4. **How do you stop the same upload from being queued twice?** Use unique work (`enqueueUniqueWork` with a stable name and `KEEP`), and make the upload idempotent on the server. {Medium}
5. **What changed for foreground services in Android 14?** Every foreground service must declare a type with a matching permission, and Play reviews the declared types. {Medium}
6. **How does Doze affect your app?** Network access, jobs and normal alarms are deferred to maintenance windows while the device is idle. Use WorkManager, and high-priority push only for urgent user-visible events. {Medium}
7. **How would you sync data when the server has new content?** Send a small push that only signals a change; its handler schedules a unique WorkManager job that fetches changes since the last cursor. {Medium}
8. **How do you show progress of a long upload in the UI?** Call `setProgress` in the worker and observe `WorkInfo` as a Flow from the UI; for long work, use `setForeground` to show a notification. {Easy}
