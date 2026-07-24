# Setup notes — JDK compatibility and install decisions

Date: 2026-07-24. For the audit / main loop. Not part of the headline evidence.

## The JDK-26 block (FINDING-01 raw)

The host default JDK is **OpenJDK 26.0.1** (Homebrew `openjdk`). The first real Nutch
job (`bin/nutch inject`, which starts a Hadoop LocalJobRunner) fails at init:

```
java.lang.UnsupportedOperationException: getSubject is not supported
    at java.base/javax.security.auth.Subject.getSubject(Subject.java:277)
    at org.apache.hadoop.security.UserGroupInformation.getCurrentUser(UserGroupInformation.java:588)
    at org.apache.hadoop.fs.FileSystem$Cache$Key.<init>(FileSystem.java:3888)
    ...
    at org.apache.nutch.crawl.Injector.inject(Injector.java:473)
```

Adding `-Djava.security.manager=allow` (the pre-JDK-24 bridge) does not help — the VM
refuses to start:

```
Error occurred during initialization of VM
java.lang.Error: A command line option has attempted to allow or enable the Security
Manager. Enabling a Security Manager is not supported.
    at java.lang.System.initPhase3(java.base@26.0.1/System.java:1970)
```

Root cause = JEP 486 (permanent SecurityManager removal, JDK 24). `Subject.getSubject`
now throws unconditionally. Fixed upstream in **Hadoop 3.4.3 / 3.5.0** (HADOOP-19212,
HADOOP-19486, HDFS-17778). **Nutch 1.22 bundles Hadoop 3.4.2** — one patch below.

## Install decision (openjdk@17)

Because the task explicitly enumerated `openjdk@11/@17/@21` as an acceptable fallback
and Nutch's own CI targets Java 17, I installed **`openjdk@17` (17.0.20) keg-only** via
Homebrew:

```
brew install openjdk@17
# keg-only: NOT symlinked into system Java wrappers; host default JDK unchanged.
# used only via NUTCH_JAVA_HOME=/opt/homebrew/opt/openjdk@17
```

On JDK 17 the full local-mode cycle (`inject → generate → fetch → parse → updatedb`)
runs cleanly. This is a **reversible, user-scoped** install; the system default JDK
(26) was not touched.

## Not blocked by Solr / Hadoop cluster

Local mode runs Hadoop's in-process LocalJobRunner — no cluster, no HDFS daemon. Solr
indexing (`bin/nutch index`) was intentionally skipped (out of the discovery/cost
scope). The fetch/parse/updatedb core all run in local mode.

## What is NOT committed

The Nutch 1.22 distribution (~395 MB), all crawldb/segments, and every `*.jar` were
kept in an OS temp dir outside this pack and are `.gitignore`d. Only harness source +
redacted JSON summaries are in the pack.
