Measurements acquired using Quarkus and GraalVM build from source

Quarkus SHA: 90bae5bb14c
GraalVM SHA: 38548661f31

Frequency fixed using

```shell
sudo cpupower frequency-set --min 4.5GHz && sudo cpupower frequency-set --max 4.5GHz
sudo cpupower idle-set -d 3  # Disables the deepest state (C3)
sudo cpupower idle-set -d 2  # Disables C2
```

Governor set to `performance`

Benchmarks ran with:

```shell
for i in none run-time-initialize-jdk class-for-name-respects-class-loader run-time-initialize-security-providers run-time-initialize-file-system-providers run-time-initialize-resource-bundles all; do ./run-benchmarks.sh --drop-fs-caches --graalvm-home ~/code/graal-oracle/sdk/latest_graalvm_home --host LOCAL --java-home ~/jvms/jdk-21.0.9+10 --runtimes quarkus3-native --quarkus-version 999-SNAPSHOT --output-dir ../../20260311/$i --tests measure-build-times,measure-time-to-first-request,measure-rss,run-load-test --iterations 10 --native-quarkus-build-options -Dquarkus.native.additional-build-args-append=--future-defaults=$i; done
```
